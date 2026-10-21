"""Views for the InkCity social reading platform."""

import logging
import random
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from .forms import (
    BookForm,
    ChapterForm,
    CommentForm,
    ForumPostForm,
    ProfileForm,
    RegisterForm,
    ReportForm,
    ThreadForm,
    ChatForm,
)
from .models import (
    Book,
    Block,
    Category,
    Chapter,
    Comment,
    ForumPost,
    GlobalChatMsg,
    Notification,
    Profile,
    Report,
    SiteUpdate,
    Thread,
)
from .ratelimit import (
    limit_chat,
    limit_comment,
    limit_login,
    limit_register,
    limit_resend,
    limit_search,
    limit_thread,
    limit_verify,
)

logger = logging.getLogger(__name__)

# כמה פריטים בעמוד
BOOKS_PER_PAGE = 12
THREADS_PER_PAGE = 15
POSTS_PER_PAGE = 20
COMMENTS_PER_PAGE = 20
NOTIFICATIONS_PER_PAGE = 25
SEARCH_RESULTS_PER_PAGE = 20
FOLLOWING_PER_PAGE = 24
HOME_BOOK_COUNT = 6
HOME_CHAT_COUNT = 20
HOME_UPDATE_COUNT = 5
HOME_ACTIVE_USERS = 10

# מספר הניסיונות המרבי להזנת קוד אימות
MAX_VERIFICATION_ATTEMPTS = 5


# ---------------------------------------------------------------------------
# עזרים
# ---------------------------------------------------------------------------

def _paginate(request, queryset, per_page):
    """מחזיר את העמוד הנוכחי מתוך queryset עם תמיכה ב-?page= ב-URL.

    מוסיף סידור ברירת מחדל אם ה-queryset אינו מסודר, כדי שהעימוד
    יהיה עקבי בין בקשות.
    """
    if not queryset.ordered:
        queryset = queryset.order_by('-pk')
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page'))


def _notify(recipients, notification_type, message, link, sender=None):
    """יוצר התראות לרשימת נמענים, תוך שמירה על אורך ההודעה בגבול של המודל."""
    recipients = [r for r in recipients if r is not None and r != sender]
    if not recipients:
        return
    Notification.objects.bulk_create([
        Notification(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            message=message[:255],
            link=link[:255],
        )
        for recipient in recipients
    ], batch_size=500)


def _is_blocked(viewer, target):
    """בודק אם המשתמש חסום את המשתמש השני."""
    if not viewer or not viewer.is_authenticated or not target:
        return False
    return Block.objects.filter(blocker=target, blocked=viewer).exists()


def verified_required(view_func):
    """דקורטור שמוודא שהמשתמש אימת את החשבון לפני פרסום תוכן."""
    @login_required
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.is_verified:
            messages.warning(
                request,
                "עליך לאשר את החשבון בעזרת קוד האימות שנשלח למייל שלך כדי לפרסם תוכן.",
            )
            return redirect('verify_code')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# ---------------------------------------------------------------------------
# דפים ציבוריים
# ---------------------------------------------------------------------------

@limit_chat
def home(request):
    """עמוד הבית — מציג ספרים מפורסמים בלבד, עדכונים, צ׳אט ומשתמשים פעילים."""
    chat_form = ChatForm()

    if request.method == 'POST' and request.user.is_authenticated:
        chat_form = ChatForm(request.POST)
        if chat_form.is_valid():
            msg = chat_form.save(commit=False)
            msg.author = request.user
            msg.save()
            return redirect('home')

    published = Book.objects.filter(status='published', is_deleted=False)

    new_books = published.select_related('author').order_by('-created_at')[:HOME_BOOK_COUNT]
    top_books = (
        published.select_related('author')
        .annotate(kudos_count=Count('kudos'))
        .order_by('-kudos_count', '-created_at')[:HOME_BOOK_COUNT]
    )
    trending_books = (
        published.select_related('author')
        .annotate(num_comments=Count('chapters__comments', filter=Q(chapters__is_deleted=False)))
        .order_by('-num_comments', '-created_at')[:HOME_BOOK_COUNT]
    )

    site_updates = SiteUpdate.objects.all()[:HOME_UPDATE_COUNT]
    chat_messages = GlobalChatMsg.objects.select_related('author')[:HOME_CHAT_COUNT]
    active_users = (
        Profile.objects.select_related('user')
        .filter(last_active__gte=timezone.now() - timezone.timedelta(minutes=15))
        .order_by('-last_active')[:HOME_ACTIVE_USERS]
    )

    return render(request, 'books/home.html', {
        'new_books': new_books,
        'top_books': top_books,
        'trending_books': trending_books,
        'site_updates': site_updates,
        'chat_messages': chat_messages,
        'online_users': active_users,
        'chat_form': chat_form,
    })


def book_detail(request, book_id):
    """עמוד ספר — טיוטות גלויים רק למחבר."""
    book = get_object_or_404(
        Book.objects.select_related('author'),
        id=book_id,
        is_deleted=False,
    )
    if book.status == 'draft' and request.user != book.author:
        raise Http404("הספר הזה עדיין לא פורסם.")

    chapters = book.chapters.filter(is_deleted=False).order_by('chapter_number')
    page = _paginate(request, chapters, BOOKS_PER_PAGE)
    kudos_count = book.kudos.count()
    user_has_kudos = (
        request.user.is_authenticated and book.kudos.filter(pk=request.user.pk).exists()
    )

    return render(request, 'books/book_detail.html', {
        'book': book,
        'chapters': page.object_list,
        'chapters_page': page,
        'kudos_count': kudos_count,
        'user_has_kudos': user_has_kudos,
    })


def chapter_detail(request, book_id, chapter_number):
    """עמוד פרק — כולל טיוטות, תגובות וטופס תגובה."""
    chapter = get_object_or_404(
        Chapter.objects.select_related('book', 'book__author'),
        book__id=book_id,
        book__is_deleted=False,
        chapter_number=chapter_number,
        is_deleted=False,
    )
    # טיוטות חייבות להיות גלויות רק למחבר הספר
    if chapter.book.status == 'draft' and request.user != chapter.book.author:
        raise Http404("הפרק הזה עדיין לא פורסם.")

    comments_qs = (
        chapter.comments
        .filter(is_deleted=False)
        .select_related('author', 'author__profile')
    )
    page = _paginate(request, comments_qs, COMMENTS_PER_PAGE)

    prev_chapter = (
        Chapter.objects
        .filter(book=chapter.book, chapter_number__lt=chapter.chapter_number, is_deleted=False)
        .order_by('-chapter_number')
        .first()
    )
    next_chapter = (
        Chapter.objects
        .filter(book=chapter.book, chapter_number__gt=chapter.chapter_number, is_deleted=False)
        .order_by('chapter_number')
        .first()
    )

    return render(request, 'books/chapter_detail.html', {
        'chapter': chapter,
        'comments': page.object_list,
        'comments_page': page,
        'comments_total': page.paginator.count,
        'comment_form': CommentForm(),
        'prev_chapter': prev_chapter,
        'next_chapter': next_chapter,
    })


def profile_detail(request, username):
    """עמוד פרופיל משתמש."""
    profile_user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=profile_user)

    if request.user == profile_user:
        user_books = (
            profile_user.books
            .filter(is_deleted=False)
            .select_related('author')
            .order_by('-created_at')
        )
    else:
        user_books = (
            profile_user.books
            .filter(status='published', is_deleted=False)
            .select_related('author')
            .order_by('-created_at')
        )

    user_threads = (
        profile_user.threads
        .filter(is_deleted=False)
        .select_related('category')
        .order_by('-created_at')
    )

    books_page = _paginate(request, user_books, BOOKS_PER_PAGE)
    threads_page = _paginate(request, user_threads, THREADS_PER_PAGE)

    is_following = (
        request.user.is_authenticated
        and request.user != profile_user
        and profile.followers.filter(pk=request.user.pk).exists()
    )

    return render(request, 'books/profile_detail.html', {
        'profile_user': profile_user,
        'profile': profile,
        'user_books': books_page.object_list,
        'user_books_count': books_page.paginator.count,
        'user_books_page': books_page,
        'user_threads': threads_page.object_list,
        'user_threads_count': threads_page.paginator.count,
        'user_threads_page': threads_page,
        'followers_count': profile.followers.count(),
        'is_following': is_following,
    })


def forum_home(request):
    """רשימת קטגוריות הפורום."""
    categories = Category.objects.annotate(
        thread_count=Count('threads', filter=Q(threads__is_deleted=False))
    )
    return render(request, 'books/forum_home.html', {'categories': categories})


def category_detail(request, category_id):
    """דיונים בקטגוריה."""
    category = get_object_or_404(Category, id=category_id)
    threads_qs = (
        category.threads
        .filter(is_deleted=False)
        .select_related('author')
        .annotate(
            post_count=Count('posts', filter=Q(posts__is_deleted=False)),
        )
    )
    page = _paginate(request, threads_qs, THREADS_PER_PAGE)
    return render(request, 'books/category_detail.html', {
        'category': category,
        'threads': page.object_list,
        'threads_page': page,
    })


def thread_detail(request, thread_id):
    """שרשור דיון עם הודעות."""
    thread = get_object_or_404(
        Thread.objects.select_related('category', 'author'),
        id=thread_id,
        is_deleted=False,
    )
    posts_qs = (
        thread.posts
        .filter(is_deleted=False)
        .select_related('author', 'author__profile')
    )
    page = _paginate(request, posts_qs, POSTS_PER_PAGE)

    form = ForumPostForm()
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, "התחבר כדי להגיב בדיון.")
            return redirect(f"{reverse('login')}?next={request.path}")
        if _is_blocked(request.user, thread.author):
            messages.error(request, "לא ניתן להגיב בשרשור הזה.")
            return redirect('thread_detail', thread_id=thread.id)
        form = ForumPostForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                post = form.save(commit=False)
                post.thread = thread
                post.author = request.user
                post.save()
                # עדכון תאריך הפעילות של השרשור בלי לכתוב את כל השורה
                Thread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
            return redirect('thread_detail', thread_id=thread.id)

    return render(request, 'books/thread_detail.html', {
        'thread': thread,
        'posts': page.object_list,
        'posts_page': page,
        'posts_total': page.paginator.count,
        'form': form,
    })


@limit_search
def search_results(request):
    """חיפוש ספרים ודיונים."""
    query = request.GET.get('q', '').strip()[:100]
    books = Book.objects.none()
    threads = Thread.objects.none()
    books_page = Paginator(Book.objects.none(), SEARCH_RESULTS_PER_PAGE).get_page(1)
    threads_total = 0

    if query:
        terms = query.split()
        book_filter = Q()
        thread_filter = Q()
        for term in terms:
            book_filter &= Q(title__icontains=term) | Q(author__username__icontains=term)
            thread_filter &= Q(title__icontains=term) | Q(author__username__icontains=term)

        books_qs = (
            Book.objects
            .filter(book_filter, status='published', is_deleted=False)
            .select_related('author')
            .order_by('-created_at')
        )
        books_page = _paginate(request, books_qs, SEARCH_RESULTS_PER_PAGE)

        threads_qs = (
            Thread.objects
            .filter(thread_filter, is_deleted=False)
            .select_related('author', 'category')
            .order_by('-updated_at')
        )
        threads_total = threads_qs.count()
        threads = threads_qs[:SEARCH_RESULTS_PER_PAGE]

    return render(request, 'books/search_results.html', {
        'query': query,
        'books': books_page.object_list,
        'books_page': books_page,
        'books_total': books_page.paginator.count,
        'threads': threads,
        'threads_total': threads_total,
    })


def terms(request):
    """תנאי שימוש."""
    return render(request, 'books/terms.html')


def privacy(request):
    """מדיניות פרטיות."""
    return render(request, 'books/privacy.html')


def sitemap(request):
    """מפת אתר למנועי חיפוש."""
    published_books = (
        Book.objects.filter(status='published', is_deleted=False)
        .select_related('author')
        .order_by('-created_at')[:1000]
    )
    published_threads = (
        Thread.objects.filter(is_deleted=False)
        .select_related('author')
        .order_by('-created_at')[:1000]
    )
    return render(request, 'sitemap.xml', {
        'published_books': published_books,
        'published_threads': published_threads,
    }, content_type='application/xml')


def health_check(request):
    """בדיקת תקינות השירות — משמשת לניטור ולמערכת הניטור."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return JsonResponse({'status': 'error', 'database': 'unreachable'}, status=503)
    return JsonResponse({'status': 'ok', 'database': 'ok'})


# ---------------------------------------------------------------------------
# הרשמה ואימות
# ---------------------------------------------------------------------------

@limit_register
def register(request):
    """הרשמה — יוצרת חשבון ושולחת קוד אימות למייל."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                profile, _ = Profile.objects.get_or_create(user=user)
                code = f"{random.randint(100000, 999999)}"
                profile.verification_code = code
                profile.verification_code_created_at = timezone.now()
                profile.save(update_fields=[
                    'verification_code', 'verification_code_created_at',
                ])

            subject = 'קוד אימות לאתר InkCity'
            message = (
                f"שלום {user.username},\n\n"
                f"קוד האימות שלך ב-InkCity הוא: {code}\n"
                f"הקוד תקף ל-15 דקות."
            )
            try:
                send_mail(subject, message, None, [user.email])
            except Exception:
                logger.exception("שליחת מייל אימות נכשלה עבור %s", user.username)
                messages.warning(
                    request,
                    "לא הצלחנו לשלוח את המייל כרגע. נסה שוב לשלוח קוד חדש.",
                )
            else:
                messages.success(
                    request,
                    "נרשמת בהצלחה! שלחנו לך קוד אימות במייל. יש לו 15 דקות לפעול.",
                )
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'books/register.html', {'form': form})


@limit_verify
@login_required
def verify_code(request):
    """אימות חשבון באמצעות קוד 6 ספרות."""
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if profile.is_verified:
        return redirect('home')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()

        if not profile.verification_code or not profile.is_code_valid():
            messages.error(
                request,
                'תוקף קוד האימות פג. אנא בקש קוד חדש.',
            )
        elif profile.verification_attempts >= MAX_VERIFICATION_ATTEMPTS:
            messages.error(
                request,
                'נעשו יותר מדי ניסיונות. אנא בקש קוד חדש.',
            )
        elif entered_code == profile.verification_code:
            profile.is_verified = True
            profile.clear_verification_code()
            profile.save(update_fields=['is_verified'])
            messages.success(
                request,
                'החשבון שלך אומת בהצלחה! כעת תוכל לפרסם ספרים ותגובות.',
            )
            return redirect('home')
        else:
            profile.verification_attempts += 1
            profile.save(update_fields=['verification_attempts'])
            messages.error(
                request,
                'קוד אימות שגוי. אנא בדוק את המייל ונסה שוב.',
            )

    return render(request, 'books/verify_code.html', {
        'email': request.user.email,
        'attempts_left': max(0, MAX_VERIFICATION_ATTEMPTS - profile.verification_attempts),
    })


@limit_resend
@login_required
@require_POST
def resend_code(request):
    """שליחת קוד אימות חדש (POST בלבד)."""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.is_verified:
        return redirect('home')

    code = f"{random.randint(100000, 999999)}"
    profile.issue_verification_code(code)

    subject = 'קוד אימות חדש - InkCity'
    message = (
        f"שלום {request.user.username},\n"
        f"קוד האימות החדש שלך הוא: {code}\n"
        f"הקוד תקף ל-15 דקות."
    )
    try:
        send_mail(subject, message, None, [request.user.email])
    except Exception:
        logger.exception("שליחת קוד אימות חדש נכשלה עבור %s", request.user.username)
        messages.error(request, 'אירעה שגיאה בשליחת המייל. נסה שוב מאוחר יותר.')
    else:
        messages.success(request, 'קוד אימות חדש נשלח לכתובת המייל שלך!')

    return redirect('verify_code')


# ---------------------------------------------------------------------------
# יצירת תוכן
# ---------------------------------------------------------------------------

@login_required
@verified_required
def create_book(request):
    """יצירת ספר חדש."""
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                book = form.save(commit=False)
                book.author = request.user
                book.save()

                if book.status == 'published':
                    author_profile, _ = Profile.objects.get_or_create(user=request.user)
                    _notify(
                        author_profile.followers.select_related('profile'),
                        'new_book',
                        f"היוצר {request.user.username} פרסם ספר חדש: '{book.title}'!",
                        reverse('book_detail', kwargs={'book_id': book.id}),
                        sender=request.user,
                    )
            messages.success(request, 'הספר פורסם בהצלחה!')
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm()

    return render(request, 'books/create_book.html', {'form': form})


@login_required
@verified_required
def create_chapter(request, book_id):
    """יצירת פרק חדש בספר."""
    book = get_object_or_404(Book, id=book_id, is_deleted=False)

    if request.user != book.author:
        messages.error(request, 'אין לך הרשאה להוסיף פרקים לספר הזה.')
        return redirect('book_detail', book_id=book.id)

    if request.method == 'POST':
        form = ChapterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                chapter = form.save(commit=False)
                chapter.book = book
                try:
                    chapter.save()
                except Exception as exc:
                    if 'unique' in str(exc).lower():
                        messages.error(
                            request,
                            f"כבר קיים פרק מספר {chapter.chapter_number} בספר הזה.",
                        )
                        return render(request, 'books/create_chapter.html', {
                            'form': form, 'book': book,
                        })
                    raise

                chapter_url = reverse('chapter_detail', kwargs={
                    'book_id': book.id,
                    'chapter_number': chapter.chapter_number,
                })

                author_profile, _ = Profile.objects.get_or_create(user=request.user)
                _notify(
                    author_profile.followers.exclude(pk=request.user.pk),
                    'new_chapter',
                    f"{request.user.username} פרסם/ה פרק חדש בספר '{book.title}': '{chapter.title}'",
                    chapter_url,
                    sender=request.user,
                )

            messages.success(request, 'הפרק נוסף בהצלחה!')
            return redirect(chapter_url)
    else:
        form = ChapterForm()

    return render(request, 'books/create_chapter.html', {'form': form, 'book': book})


@limit_comment
@login_required
@verified_required
def add_comment(request, book_id, chapter_number):
    """הוספת תגובה לפרק."""
    chapter = get_object_or_404(
        Chapter.objects.select_related('book', 'book__author'),
        book__id=book_id,
        book__is_deleted=False,
        chapter_number=chapter_number,
        is_deleted=False,
    )

    if request.method == 'POST':
        if _is_blocked(request.user, chapter.book.author):
            messages.error(request, 'לא ניתן להגיב בפרק הזה.')
            return redirect('chapter_detail', book_id=book_id, chapter_number=chapter_number)
        form = CommentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                comment = form.save(commit=False)
                comment.chapter = chapter
                comment.author = request.user
                comment.save()
                if chapter.book.author != request.user:
                    Notification.objects.create(
                        recipient=chapter.book.author,
                        sender=request.user,
                        notification_type='new_comment',
                        message=(
                            f"{request.user.username} הגיב על הפרק "
                            f"'{chapter.title}' בספר '{chapter.book.title}'"
                        )[:255],
                        link=reverse('chapter_detail', kwargs={
                            'book_id': chapter.book.id,
                            'chapter_number': chapter.chapter_number,
                        }),
                    )
            messages.success(request, 'התגובה נשמרה בהצלחה!')
    return redirect('chapter_detail', book_id=book_id, chapter_number=chapter_number)


@limit_thread
@login_required
@verified_required
def create_thread(request, category_id):
    """פתיחת דיון חדש בקטגוריה."""
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                thread = form.save(commit=False)
                thread.category = category
                thread.author = request.user
                thread.save()
                ForumPost.objects.create(
                    thread=thread,
                    author=request.user,
                    content=form.cleaned_data['content'],
                )
            messages.success(request, 'הדיון נפתח בהצלחה!')
            return redirect('thread_detail', thread_id=thread.id)
    else:
        form = ThreadForm()

    return render(request, 'books/create_thread.html', {
        'form': form, 'category': category,
    })


# ---------------------------------------------------------------------------
# עריכה ומחיקה
# ---------------------------------------------------------------------------

@login_required
def edit_profile(request):
    """עריכת הפרופיל האישי."""
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'הפרופיל עודכן בהצלחה!')
            return redirect('profile_detail', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'books/edit_profile.html', {'form': form})


@login_required
def edit_book(request, book_id):
    """עריכת פרטי ספר (רק למחבר)."""
    book = get_object_or_404(Book, id=book_id, is_deleted=False)
    if request.user != book.author:
        raise Http404("אין לך הרשאה לערוך ספר זה.")

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save()
            messages.success(request, 'פרטי הספר עודכנו בהצלחה!')
            return redirect('book_detail', book_id=book.id)
    else:
        form = BookForm(instance=book)

    return render(request, 'books/edit_book.html', {'form': form, 'book': book})


@login_required
def edit_chapter(request, book_id, chapter_number):
    """עריכת פרק (רק למחבר הספר)."""
    chapter = get_object_or_404(
        Chapter.objects.select_related('book'),
        book__id=book_id,
        book__is_deleted=False,
        chapter_number=chapter_number,
        is_deleted=False,
    )
    if request.user != chapter.book.author:
        raise Http404("אין לך הרשאה לערוך פרק זה.")

    if request.method == 'POST':
        form = ChapterForm(request.POST, instance=chapter)
        if form.is_valid():
            chapter = form.save()
            messages.success(request, 'הפרק עודכן בהצלחה!')
            return redirect('chapter_detail', kwargs={
                'book_id': chapter.book_id,
                'chapter_number': chapter.chapter_number,
            })
    else:
        form = ChapterForm(instance=chapter)

    return render(request, 'books/edit_chapter.html', {
        'form': form, 'book': chapter.book, 'chapter': chapter,
    })


@login_required
def delete_book(request, book_id):
    """מחיקת ספר — מימוש רך, ניתן לשחזר."""
    book = get_object_or_404(Book, id=book_id, is_deleted=False)
    if request.user != book.author:
        raise Http404("אין לך הרשאה למחוק ספר זה.")

    if request.method == 'POST':
        book.is_deleted = True
        book.save(update_fields=['is_deleted'])
        messages.success(request, 'הספר נמחק. ניתן לשחזר אותו דרך האדמין.')
        return redirect('profile_detail', username=request.user.username)

    return render(request, 'books/confirm_delete_book.html', {'book': book})


@login_required
def delete_chapter(request, book_id, chapter_number):
    """מחיקת פרק — מימוש רך, ניתן לשחזר."""
    chapter = get_object_or_404(
        Chapter.objects.select_related('book'),
        book__id=book_id,
        book__is_deleted=False,
        chapter_number=chapter_number,
        is_deleted=False,
    )
    if request.user != chapter.book.author:
        raise Http404("אין לך הרשאה למחוק פרק זה.")

    if request.method == 'POST':
        chapter.is_deleted = True
        chapter.save(update_fields=['is_deleted'])
        messages.success(request, 'הפרק נמחק. ניתן לשחזר אותו דרך האדמין.')
        return redirect('book_detail', book_id=chapter.book_id)

    return render(request, 'books/confirm_delete_chapter.html', {
        'chapter': chapter, 'book': chapter.book,
    })


# ---------------------------------------------------------------------------
# אינטראקציות חברתיות
# ---------------------------------------------------------------------------

@login_required
@require_POST
def toggle_kudos(request, book_id):
    """מתן או הסרת קודוס לספר."""
    book = get_object_or_404(
        Book.objects.select_related('author'),
        id=book_id,
        is_deleted=False,
    )
    if book.status != 'published':
        messages.error(request, 'לא ניתן לתת קודוס לספר שטרם פורסם.')
        return redirect('book_detail', book_id=book.id)

    already = book.kudos.filter(pk=request.user.pk).exists()
    if already:
        book.kudos.remove(request.user)
    else:
        book.kudos.add(request.user)
        if book.author != request.user:
            Notification.objects.create(
                recipient=book.author,
                sender=request.user,
                notification_type='new_kudos',
                message=f"{request.user.username} נתן קודוס לספר '{book.title}'"[:255],
                link=reverse('book_detail', kwargs={'book_id': book.id}),
            )

    return redirect('book_detail', book_id=book.id)


@login_required
@require_POST
def toggle_follow(request, username):
    """עקוב/הפסק לעקוב אחרי משתמש."""
    target_user = get_object_or_404(User, username=username)
    if request.user == target_user:
        return redirect('profile_detail', username=username)

    target_profile, _ = Profile.objects.get_or_create(user=target_user)
    already = target_profile.followers.filter(pk=request.user.pk).exists()

    if already:
        target_profile.followers.remove(request.user)
    else:
        target_profile.followers.add(request.user)
        Notification.objects.create(
            recipient=target_user,
            sender=request.user,
            notification_type='new_follower',
            message=f"{request.user.username} התחיל לעקוב אחריך!",
            link=reverse('profile_detail', kwargs={'username': request.user.username}),
        )

    return redirect('profile_detail', username=username)


@login_required
def notifications_page(request):
    """רשימת התראות."""
    notifications_qs = request.user.notifications.select_related('sender')
    page = _paginate(request, notifications_qs, NOTIFICATIONS_PER_PAGE)
    return render(request, 'books/notifications.html', {
        'notifications': page.object_list,
        'notifications_page': page,
        'unread_count': notifications_qs.filter(is_read=False).count(),
    })


@login_required
@require_POST
def mark_notifications_read(request):
    """סימון כל ההתראות כנקראו (POST בלבד)."""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'כל ההתראות סומנו כנקראו.')
    return redirect('notifications')


@login_required
def following_list(request):
    """רשימת המשתמשים שעוקבים אחריהם."""
    following_qs = (
        request.user.following
        .select_related('user')
        .order_by('-last_active')
    )
    page = _paginate(request, following_qs, FOLLOWING_PER_PAGE)
    return render(request, 'books/following_list.html', {
        'following_profiles': page.object_list,
        'following_page': page,
        'following_total': page.paginator.count,
    })


# ---------------------------------------------------------------------------
# דיווח וחסימה
# ---------------------------------------------------------------------------

@login_required
@require_POST
def report_content(request, content_type, object_id):
    """דיווח על תוכן לא תקין."""
    allowed_types = {'book', 'comment', 'thread', 'forumpost'}
    if content_type not in allowed_types:
        raise Http404("סוג תוכן לא נתמך.")

    form = ReportForm(request.POST)
    if form.is_valid():
        report, created = Report.objects.get_or_create(
            reporter=request.user,
            content_type=content_type,
            object_id=object_id,
            defaults={
                'reason': form.cleaned_data['reason'],
                'details': form.cleaned_data.get('details', ''),
            },
        )
        if not created:
            report.reason = form.cleaned_data['reason']
            report.details = form.cleaned_data.get('details', '')
            report.status = 'open'
            report.save(update_fields=['reason', 'details', 'status'])
        messages.success(request, 'הדיווח נקלט. תודה על העזרה!')
    else:
        messages.error(request, 'לא הצלחנו לשמור את הדיווח. נסה שוב.')

    referer = request.META.get('HTTP_REFERER')
    return redirect(referer) if referer else redirect('home')


@login_required
@require_POST
def block_user(request, username):
    """חסימת משתמש."""
    target_user = get_object_or_404(User, username=username)
    if target_user == request.user:
        messages.error(request, 'לא ניתן לחסום את עצמך.')
        return redirect('profile_detail', username=username)

    Block.objects.get_or_create(
        blocker=request.user,
        blocked=target_user,
    )
    # הסרת העקוב ההדדי כדי לא להציג עקובים של חסומים
    Profile.objects.filter(user__in=[request.user, target_user]).exclude(
        user=request.user
    ).first()
    messages.success(request, f"המשתמש {target_user.username} נחסם.")
    return redirect('profile_detail', username=username)


@login_required
@require_POST
def unblock_user(request, username):
    """הסרת חסימה."""
    target_user = get_object_or_404(User, username=username)
    Block.objects.filter(blocker=request.user, blocked=target_user).delete()
    messages.success(request, f"החסימה של {target_user.username} הוסרה.")
    return redirect('profile_detail', username=username)
