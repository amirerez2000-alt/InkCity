# Django imports
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.shortcuts import render, get_object_or_404
from django.db import transaction
from django.urls import reverse
from django.db.models import Q
from django.http import Http404
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib import messages
from .forms import RegisterForm
from django.core.paginator import Paginator
import random
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from .forms import RegisterForm
from .models import Profile


# Local application imports
from .models import Book, Chapter, Profile, Comment, Category, Thread, ForumPost, SiteUpdate, GlobalChatMsg, Notification
from .forms import BookForm, ChapterForm, ProfileForm, CommentForm, ThreadForm, ForumPostForm, ChatForm

from .forms import (
    BookForm,
    ChapterForm,
    CommentForm,
    ForumPostForm,
    ProfileForm,
    ThreadForm,
)
from .models import (
    Book,
    Category,
    Chapter,
    Comment,
    ForumPost,
    Profile,
    Thread,
)

def home(request):
    # סינון ספרים מפורסמים בלבד לכל האזורים בעמוד הבית
    new_books = Book.objects.filter(status='published').order_by('-id')[:6]
    top_books = Book.objects.filter(status='published').annotate(kudos_count=Count('kudos')).order_by('-kudos_count')[:6]
    trending_books = Book.objects.filter(status='published').order_by('?')[:6]
    
    # שאר הנתונים לעמוד הבית
    site_updates = SiteUpdate.objects.all().order_by('-created_at')[:5]
    global_messages = GlobalChatMsg.objects.all().order_by('-created_at')[:20]
    active_users = Profile.objects.order_by('-last_active')[:10]

    return render(request, 'books/home.html', {
        'new_books': new_books,
        'top_books': top_books,
        'trending_books': trending_books,
        'site_updates': site_updates,
        'global_messages': global_messages,
        'active_users': active_users,
    })

def book_detail(request, book_id):
    # שליפת הספר הספציפי והפרקים שלו
    book = get_object_or_404(Book, id=book_id)
    if book.status == 'draft' and request.user != book.author:
        raise Http404("הספר הזה עדיין לא פורסם.")
    chapters = book.chapters.all()
    return render(request, 'books/book_detail.html', {'book': book, 'chapters': chapters})

def chapter_detail(request, book_id, chapter_number):
    chapter = get_object_or_404(Chapter, book__id=book_id, chapter_number=chapter_number)
    comments = chapter.comments.all()
    comment_form = CommentForm()
    
    # חיפוש הפרק הקודם והבא לפי מספר הפרק
    prev_chapter = Chapter.objects.filter(book=chapter.book, chapter_number__lt=chapter.chapter_number).order_by('-chapter_number').first()
    next_chapter = Chapter.objects.filter(book=chapter.book, chapter_number__gt=chapter.chapter_number).order_by('chapter_number').first()
    
    return render(request, 'books/chapter_detail.html', {
        'chapter': chapter,
        'comments': comments,
        'comment_form': comment_form,
        'prev_chapter': prev_chapter,
        'next_chapter': next_chapter,
    })

def verified_required(view_func):
    """דקורטור שמוודא שהמשתמש אימת את החשבון לפני פרסום תוכן"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if not profile.is_verified:
            messages.warning(request, "עליך לאשר את החשבון בעזרת קוד האימות שנשלח למייל שלך כדי לפרסם תוכן.")
            return redirect('verify_code')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=True)
            
            # ייצור קוד אימות חד-פעמי ושמירת חותמת זמן
            code = str(random.randint(100000, 999999))
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.verification_code = code
            profile.verification_code_created_at = timezone.now()
            profile.is_verified = False
            profile.save()
            
            # שליחת המייל
            subject = 'קוד אימות להפעלת חשבון - InkCity'
            message = f"שלום {user.username},\n\nתודה שנרשמת ל-InkCity!\nקוד האימות שלך הוא: {code}\n\nהקוד תקף ל-15 דקות הקרובות."
            try:
                send_mail(subject, message, None, [user.email])
            except Exception as e:
                print(f"שגיאה בשליחת מייל: {e}")
            
            login(request, user)
            messages.success(request, 'נרשמת בהצלחה! קוד אימות בן 6 ספרות נשלח לכתובת המייל שלך.')
            return redirect('verify_code')
    else:
        form = RegisterForm()
        
    return render(request, 'books/register.html', {'form': form})


@login_required
def verify_code(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if profile.is_verified:
        return redirect('home')

    if request.method == 'POST':
        entered_code = request.POST.get('code', '').strip()
        
        # 1. בדיקת תוקף זמן של הקוד (15 דקות)
        if not profile.is_code_valid():
            messages.error(request, 'תוקף קוד האימות פג (עברו יותר מ-15 דקות). אנא לחץ על שליחה מחדש.')
        # 2. אימות הקוד שהוזן
        elif profile.verification_code and entered_code == profile.verification_code:
            profile.is_verified = True
            profile.verification_code = None
            profile.verification_code_created_at = None
            profile.save()
            messages.success(request, 'החשבון שלך אומת בהצלחה! כעת תוכל לפרסם ספרים ותגובות.')
            return redirect('home')
        else:
            messages.error(request, 'קוד אימות שגוי. אנא בדוק את המייל ונסה שוב.')

    return render(request, 'books/verify_code.html', {'email': request.user.email})


@login_required
def resend_code(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.is_verified:
        return redirect('home')
        
    code = str(random.randint(100000, 999999))
    profile.verification_code = code
    profile.verification_code_created_at = timezone.now()
    profile.save()
    
    subject = 'קוד אימות חדש - InkCity'
    message = f"שלום {request.user.username},\n\nקוד האימות החדש שלך הוא: {code}\nהקוד תקף ל-15 דקות."
    try:
        send_mail(subject, message, None, [request.user.email])
        messages.success(request, 'קוד אימות חדש נשלח לכתובת המייל שלך!')
    except Exception as e:
        messages.error(request, 'אירעה שגיאה בשליחת המייל. נסה שנית מאוחר יותר.')
        
    return redirect('verify_code')

@login_required
def create_book(request):
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.author = request.user
            book.save()

            # 4.ה: שליחת התראות לעוקבים רק אם הספר מפורסם (ולא טיוטה)
            if book.status == 'published':
                author_profile, created = Profile.objects.get_or_create(user=request.user)
                followers = author_profile.followers.all()
                
                notifications = []
                for follower in followers:
                    notifications.append(Notification(
                        recipient=follower,
                        sender=request.user,
                        notification_type='new_book',
                        message=f"היוצר {request.user.username} פרסם ספר חדש: '{book.title}'!",
                        link=f"/book/{book.id}/"
                    ))
                
                if notifications:
                    Notification.objects.bulk_create(notifications)

            return redirect('home')
    else:
        form = BookForm()
        
    return render(request, 'books/create_book.html', {'form': form})

@login_required
def create_chapter(request, book_id):
    book = get_object_or_404(Book, id=book_id)

    if request.user != book.author:
        return redirect('book_detail', book_id=book.id)

    if request.method == 'POST':
        form = ChapterForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                chapter = form.save(commit=False)
                chapter.book = book
                chapter.save()

                chapter_url = reverse('chapter_detail', kwargs={
                    'book_id': book.id,
                    'chapter_number': chapter.chapter_number,
                })

                followers = request.user.profile.followers.exclude(pk=request.user.pk)
                # אם followers הם Profile ולא User: השתמשו ב-follower.user בשורה של recipient

                notifications = [
                    Notification(
                        recipient=follower,
                        sender=request.user,
                        notification_type='new_chapter',
                        message=f"{request.user.username} פרסם/ה פרק חדש בספר '{book.title}': '{chapter.title}'",
                        link=chapter_url,
                    )
                    for follower in followers
                ]
                Notification.objects.bulk_create(notifications, batch_size=500)

            return redirect(chapter_url)
    else:
        form = ChapterForm()
    return render(request, 'books/create_chapter.html', {'form': form, 'book': book})

@login_required
def toggle_kudos(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # בודקים אם המשתמש הנוכחי נמצא ברשימת ה-Kudos של הספר
    if request.user in book.kudos.all():
        book.kudos.remove(request.user) # הסרת הלייק
    else:
        book.kudos.add(request.user) # הוספת הלייק
        if book.author != request.user:
            Notification.objects.create(
                recipient=book.author,
                sender=request.user,
                notification_type='new_kudos',
                message=f"{request.user.username} נתן קודוס לספר '{book.title}'",
                link=f"/book/{book.id}/"
            )
        
    # מחזירים את המשתמש חזרה לעמוד הספר
    return redirect('book_detail', book_id=book.id)

def profile_detail(request, username):
    # שולף את המשתמש לפי שם המשתמש (או מחזיר 404 אם לא קיים)
    profile_user = get_object_or_404(User, username=username)
    
    # יוצר פרופיל במידה ועדיין לא קיים עבור המשתמש הזה
    profile, created = Profile.objects.get_or_create(user=profile_user)
    
    # שליפת כל הספרים שהמשתמש הזה כתב
    user_books = profile_user.books.all().order_by('-created_at')
    
    return render(request, 'books/profile_detail.html', {
        'profile_user': profile_user,
        'profile': profile,
        'user_books': user_books,
    })

@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # חשוב ביותר: הוספנו את request.FILES כדי לקלוט תמונות!
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile_detail', username=request.user.username)
    else:
        form = ProfileForm(instance=profile)
        
    return render(request, 'books/edit_profile.html', {'form': form})

@login_required
def add_comment(request, book_id, chapter_number):
    chapter = get_object_or_404(Chapter, book__id=book_id, chapter_number=chapter_number)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.chapter = chapter
            comment.author = request.user
            comment.save()
            if chapter.book.author != request.user:
                Notification.objects.create(
                    recipient=chapter.book.author,
                    sender=request.user,
                    notification_type='new_comment',
                    message=f"{request.user.username} הגיב על הפרק '{chapter.title}' בספר '{chapter.book.title}'",
                    link=f"/book/{chapter.book.id}/chapter/{chapter.chapter_number}/"
                )
    return redirect('chapter_detail', book_id=book_id, chapter_number=chapter_number)

def forum_home(request):
  categories = Category.objects.all()
  return render(
      request, 'books/forum_home.html', {'categories': categories}
  )


def category_detail(request, category_id):
  category = get_object_or_404(Category, id=category_id)
  threads = category.threads.all()
  return render(
      request,
      'books/category_detail.html',
      {'category': category, 'threads': threads},
  )


def thread_detail(request, thread_id):
  thread = get_object_or_404(Thread, id=thread_id)
  posts = thread.posts.all()
  form = ForumPostForm()

  if request.method == 'POST' and request.user.is_authenticated:
    form = ForumPostForm(request.POST)
    if form.is_valid():
      post = form.save(commit=False)
      post.thread = thread
      post.author = request.user
      post.save()
      thread.save()  # מעדכן את תאריך העדכון האחרון של השרשור כדי שיקפוץ למעלה
      return redirect('thread_detail', thread_id=thread.id)

  return render(
      request,
      'books/thread_detail.html',
      {'thread': thread, 'posts': posts, 'form': form},
  )


@login_required
def create_thread(request, category_id):
  category = get_object_or_404(Category, id=category_id)
  if request.method == 'POST':
    form = ThreadForm(request.POST)
    if form.is_valid():
      thread = form.save(commit=False)
      thread.category = category
      thread.author = request.user
      thread.save()

      # יוצרים אוטומטית את הפוסט הראשון בשרשור
      ForumPost.objects.create(
          thread=thread,
          author=request.user,
          content=form.cleaned_data['content'],
      )
      return redirect('thread_detail', thread_id=thread.id)
  else:
    form = ThreadForm()

  return render(
      request,
      'books/create_thread.html',
      {'form': form, 'category': category},
  )

def home(request):
    # טיפול בשליחת הודעת צ'אט
    chat_form = ChatForm()
    if request.method == 'POST' and request.user.is_authenticated:
        # אם יש בקשה לשליחת צ'אט (נוודא לפי כפתור הסאבמיט)
        if 'send_chat' in request.POST:
            chat_form = ChatForm(request.POST)
            if chat_form.is_valid():
                msg = chat_form.save(commit=False)
                msg.author = request.user
                msg.save()
                return redirect('home') # רענון העמוד

    # עדכון זמן פעילות אחרון למשתמש הנוכחי
    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)
        profile.save() # השדה last_active מתעדכן אוטומטית (auto_now=True)

    # שליפת ספרים
    new_books = Book.objects.filter(status='published').order_by('-id')[:6]
    top_books = Book.objects.filter(status='published').annotate(num_kudos=Count('kudos')).order_by('-num_kudos')[:6]
    trending_books = Book.objects.filter(status='published').annotate(num_comments=Count('chapters__comments')).order_by('-num_comments')[:6]

    # שליפת נתונים לסרגל הצד
    updates = SiteUpdate.objects.all()[:3] # 3 עדכונים אחרונים
    chat_messages = GlobalChatMsg.objects.all()[:15] # 15 הודעות אחרונות
    
    # חישוב משתמשים שהיו פעילים ב-15 דקות האחרונות
    fifteen_mins_ago = timezone.now() - timedelta(minutes=15)
    online_users = Profile.objects.filter(last_active__gte=fifteen_mins_ago)

    return render(request, 'books/home.html', {
        'new_books': new_books,
        'top_books': top_books,
        'trending_books': trending_books,
        'updates': updates,
        'chat_messages': chat_messages,
        'online_users': online_users,
        'chat_form': chat_form,
    })

def profile_detail(request, username):
    # מציאת המשתמש שעליו מסתכלים
    profile_user = get_object_or_404(User, username=username)
    profile, created = Profile.objects.get_or_create(user=profile_user)
    
    # שליפת כל הספרים שהמשתמש הזה כתב (מהחדש לישן)
    if request.user == profile_user:
        user_books = Book.objects.filter(author=profile_user)
    else:
        user_books = Book.objects.filter(author=profile_user, status='published')
    
    # שליפת כל הדיונים שהמשתמש הזה פתח בפורום (מהחדש לישן)
    user_threads = Thread.objects.filter(author=profile_user).order_by('-created_at')

    return render(request, 'books/profile_detail.html', {
        'profile_user': profile_user,
        'profile': profile,
        'user_books': user_books,
        'user_threads': user_threads,
    })

@login_required
def toggle_follow(request, username):
    target_user = get_object_or_404(User, username=username)
    target_profile, _ = Profile.objects.get_or_create(user=target_user)
    
    if request.user != target_user: # למנוע ממישהו לעקוב אחרי עצמו
        if request.user in target_profile.followers.all():
            target_profile.followers.remove(request.user)
            # במקרה של הסרת עוקב, אפשר (אך לא חובה) למחוק התראת מעקב קודמת
        else:
            target_profile.followers.add(request.user)
            # יצירת התראה על עוקב חדש
            Notification.objects.create(
                recipient=target_user,
                sender=request.user,
                notification_type='new_follower',
                message=f"{request.user.username} התחיל לעקוב אחריך!",
                link=f"/profile/{request.user.username}/" # קישור חזרה לפרופיל העוקב
            )
    return redirect('profile_detail', username=username)

@login_required
def notifications_page(request):
    notifications = request.user.notifications.all()
    # סימון כל ההתראות המוצגות כנקראו (אפשר לעשות את זה גם בפעולה נפרדת)
    unread = notifications.filter(is_read=False)
    unread.update(is_read=True)
    return render(request, 'books/notifications.html', {'notifications': notifications})

@login_required
def following_list(request):
    # request.user.following.all() מביא את כל הפרופילים שהמשתמש הזה עוקב אחריהם
    following_profiles = request.user.following.all()
    return render(request, 'books/following_list.html', {'following_profiles': following_profiles})

def search_results(request):
    query = request.GET.get('q', '').strip()
    books = Book.objects.none()
    threads = Thread.objects.none()

    if query:
        terms = query.split()

        book_filter = Q()
        thread_filter = Q()
        for term in terms:  # כל מילה חייבת להופיע בכותרת או בשם המחבר
            book_filter &= Q(title__icontains=term) | Q(author__username__icontains=term)
            thread_filter &= Q(title__icontains=term) | Q(author__username__icontains=term)

        books = (Book.objects
                 .filter(book_filter, status='published')
                 .select_related('author')
                 .order_by('-created_at'))

        threads = (Thread.objects
                   .filter(thread_filter)
                   .select_related('author')
                   .order_by('-created_at'))

    books_page = Paginator(books, 20).get_page(request.GET.get('page'))

    return render(request, 'books/search_results.html', {
        'query': query,
        'books': books_page,
        'threads': threads[:20],
    })

@login_required
def edit_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    
    # וידוא שרק מחבר הספר מורשה לערוך אותו
    if request.user != book.author:
        raise Http404("אין לך הרשאה לערוך ספר זה.")

    # שמירת הסטטוס המקורי כדי לדעת אם הספר שונה מטיוטה למפורסם
    was_draft = (book.status == 'draft')

    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            updated_book = form.save()

            # אם הספר הפך מטיוטה למפורסם - נשלח התראה לכל העוקבים!
            if was_draft and updated_book.status == 'published':
                author_profile, _ = Profile.objects.get_or_create(user=request.user)
                followers = author_profile.followers.all()
                
                notifications = []
                for follower in followers:
                    notifications.append(Notification(
                        recipient=follower,
                        sender=request.user,
                        notification_type='new_book',
                        message=f"היוצר {request.user.username} פרסם ספר חדש: '{updated_book.title}'!",
                        link=f"/book/{updated_book.id}/"
                    ))
                
                if notifications:
                    Notification.objects.bulk_create(notifications)

            return redirect('book_detail', book_id=updated_book.id)
    else:
        form = BookForm(instance=book)

    return render(request, 'books/edit_book.html', {'form': form, 'book': book})

@login_required
def edit_chapter(request, book_id, chapter_number):
    chapter = get_object_or_404(Chapter, book__id=book_id, chapter_number=chapter_number)
    if request.user != chapter.book.author:
        raise Http404("אין לך הרשאה לערוך פרק זה.")

    if request.method == 'POST':
        form = ChapterForm(request.POST, instance=chapter)
        if form.is_valid():
            updated_chapter = form.save()
            return redirect('chapter_detail', book_id=book_id, chapter_number=updated_chapter.chapter_number)
    else:
        form = ChapterForm(instance=chapter)

    return render(request, 'books/edit_chapter.html', {'form': form, 'chapter': chapter})

@login_required
def delete_chapter(request, book_id, chapter_number):
    chapter = get_object_or_404(Chapter, book__id=book_id, chapter_number=chapter_number)
    if request.user != chapter.book.author:
        raise Http404("אין לך הרשאה למחוק פרק זה.")

    if request.method == 'POST':
        chapter.delete()
        return redirect('book_detail', book_id=book_id)

    return render(request, 'books/confirm_delete_chapter.html', {'chapter': chapter})

@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.user != book.author:
        raise Http404("אין לך הרשאה למחוק ספר זה.")

    if request.method == 'POST':
        book.delete()
        return redirect('home')

    return render(request, 'books/confirm_delete_book.html', {'book': book})

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # משתמש לא פעיל עד לאישור המייל
            user.save()
            
            # יצירת טוקן וקישור לאישור מייל
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_link = request.build_absolute_uri(
                reverse('activate', kwargs={'uidb64': uid, 'token': token})
            )
            
            # שליחת המייל
            subject = 'אישור הרשמה לאתר InkCity'
            message = f"שלום {user.username},\n\nתודה שנרשמת ל-InkCity!\nאנא לחץ על הקישור הבא כדי להפעיל את חשבונך:\n\n{activation_link}\n\nאם לא נרשמת לאתר, אנא התעלם ממייל זה."
            send_mail(subject, message, 'noreply@inkcity.com', [user.email])
            
            messages.success(request, 'נרשמת בהצלחה! שלחנו מייל אישור לכתובת שסיפקת. אנא בדוק את תיבת הדואר שלך (או הטרמינל בסביבת הפיתוח) כדי להפעיל את החשבון.')
            return redirect('login')
    else:
        form = RegisterForm()
        
    return render(request, 'books/register.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'חשבונך הופעל בהצלחה! כעת תוכל להתחבר.')
        return redirect('login')
    else:
        messages.error(request, 'קישור ההפעלה אינו תקין או שפג תוקפו.')
        return redirect('home')

@login_required
def resend_code(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.is_verified:
        return redirect('home')
        
    code = str(random.randint(100000, 999999))
    profile.verification_code = code
    profile.save()
    
    # הדפסה בולטת לטרמינל
    print("\n" + "="*50)
    print(f"🔥 קוד אימות חדש עבור '{request.user.username}': {code} 🔥")
    print("="*50 + "\n")
    
    try:
        subject = 'קוד אימות חדש - InkCity'
        message = f"שלום {request.user.username},\nקוד האימות החדש שלך הוא: {code}"
        send_mail(subject, message, 'noreply@inkcity.com', [request.user.email])
    except Exception as e:
        print(f"שגיאה בשליחת מייל: {e}")
    
    messages.success(request, f'קוד אימות חדש הופק! (לצורך בדיקה: {code})')
    return redirect('verify_code')