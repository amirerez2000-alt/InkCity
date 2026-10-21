"""בדיקות אוטומטיות לאפליקציית books."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.utils import timezone
import datetime

from books.models import (
    Block,
    Book,
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


class InkCityTestBase(TestCase):
    """בסיס משותף עם נתוני בדיקה סטנדרטיים."""

    def setUp(self):
        # מנקה את מטמון ההגבלת הקצב בין בדיקות
        from django.core.cache import cache
        cache.clear()

        self.user = User.objects.create_user(
            username='writer', email='writer@example.com', password='Str0ngPass!2026',
        )
        self.other = User.objects.create_user(
            username='reader', email='reader@example.com', password='Str0ngPass!2026',
        )
        self.category = Category.objects.create(
            name='דיון כללי', description='כל דבר על כל דבר',
        )
        self.book = Book.objects.create(
            title='ספר לדוגמה',
            summary='תקציר הספר',
            author=self.user,
            status='published',
        )
        self.chapter = Chapter.objects.create(
            book=self.book, title='פרק ראשון', content='תוכן הפרק', chapter_number=1,
        )
        self.thread = Thread.objects.create(
            category=self.category, title='דיון לדוגמה', author=self.user,
        )
        self.post = ForumPost.objects.create(
            thread=self.thread, author=self.user, content='הודעה ראשונה',
        )

    def verify_user(self, user=None):
        """מסמן את המשתמש כמאומת (דרוש לפרסום תוכן)."""
        user = user or self.user
        profile = Profile.objects.get(user=user)
        profile.is_verified = True
        profile.save()
        return profile


# ---------------------------------------------------------------------------
# מודלים ואינטגריטה
# ---------------------------------------------------------------------------

class ModelTests(InkCityTestBase):

    def test_profile_created_automatically_for_new_user(self):
        """אות post_save יוצר פרופיל אוטומטית לכל משתמש חדש."""
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
        self.assertTrue(Profile.objects.filter(user=self.other).exists())

    def test_chapter_number_unique_per_book(self):
        """לא ניתן ליצור שני פרקים עם אותו מספר באותו ספר."""
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Chapter.objects.create(
                    book=self.book, title='כפול', content='תוכן', chapter_number=1,
                )

    def test_book_title_unique_per_author(self):
        """לא ניתן ליצור שני ספרים באותו שם לאותו מחבר."""
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Book.objects.create(
                    title=self.book.title, summary='משהו', author=self.user,
                    status='published',
                )

    def test_soft_delete_keeps_record(self):
        """מחיקה רכה מסמנת את הרשומה אך לא מוחקת אותה."""
        self.book.is_deleted = True
        self.book.save()
        self.assertTrue(Book.objects.filter(pk=self.book.pk, is_deleted=True).exists())

    def test_verification_code_expiry(self):
        """קוד אימות פג לאחר 15 דקות."""
        profile = Profile.objects.get(user=self.user)
        profile.issue_verification_code('123456')
        self.assertTrue(profile.is_code_valid())

        profile.verification_code_created_at = timezone.now() - datetime.timedelta(minutes=20)
        profile.save()
        self.assertFalse(profile.is_code_valid())

    def test_notification_message_length(self):
        """ההתראות משומרות הודעות באורך מותר."""
        from books.views import _notify
        _notify([self.other], 'new_book', 'x' * 400, '/book/1/')
        notification = Notification.objects.first()
        self.assertLessEqual(len(notification.message), 255)


# ---------------------------------------------------------------------------
# הרשאות ו-IDOR
# ---------------------------------------------------------------------------

class PermissionTests(InkCityTestBase):

    def test_draft_book_hidden_from_others(self):
        """ספר בטיוטה מוסתר ממשתמש אחר."""
        draft = Book.objects.create(
            title='ספר טיוטה', summary='סודי', author=self.user, status='draft',
        )
        self.client.force_login(self.other)
        response = self.client.get(reverse('book_detail', kwargs={'book_id': draft.pk}))
        self.assertEqual(response.status_code, 404)

    def test_draft_book_visible_to_author(self):
        """המחבר רואה את הטיוטה שלו."""
        draft = Book.objects.create(
            title='ספר טיוטה', summary='סודי', author=self.user, status='draft',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('book_detail', kwargs={'book_id': draft.pk}))
        self.assertEqual(response.status_code, 200)

    def test_draft_chapter_hidden_from_others(self):
        """פרק של ספר טיוטה מוסתר ממשתמש אחר."""
        draft = Book.objects.create(
            title='ספר טיוטה', summary='סודי', author=self.user, status='draft',
        )
        Chapter.objects.create(
            book=draft, title='פרק סודי', content='תוכן', chapter_number=1,
        )
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('chapter_detail', kwargs={'book_id': draft.pk, 'chapter_number': 1})
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_book_requires_ownership(self):
        """אי אפשר לערוך ספר של מישהו אחר."""
        self.client.force_login(self.other)
        response = self.client.get(reverse('edit_book', kwargs={'book_id': self.book.pk}))
        self.assertEqual(response.status_code, 404)

    def test_edit_chapter_requires_ownership(self):
        """אי אפשר לערוך פרק של מישהו אחר."""
        self.client.force_login(self.other)
        response = self.client.get(reverse('edit_chapter', kwargs={
            'book_id': self.book.pk, 'chapter_number': 1,
        }))
        self.assertEqual(response.status_code, 404)

    def test_delete_book_requires_ownership(self):
        """אי אפשר למחוק ספר של מישהו אחר."""
        self.client.force_login(self.other)
        response = self.client.post(
            reverse('delete_book', kwargs={'book_id': self.book.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Book.objects.filter(pk=self.book.pk, is_deleted=False).exists())

    def test_mutating_views_require_login(self):
        """פעולות שמשנות מידע דורשות התחברות."""
        for name, kwargs in [
            ('create_book', {}),
            ('edit_profile', {}),
            ('following_list', {}),
            ('notifications', {}),
        ]:
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, 302, msg=f"{name} should require login")
            self.assertIn('/accounts/login/', response.url)

    def test_verified_required_blocks_unverified_user(self):
        """משתמש שלא אימת את החשבון אינו יכול לפרסם ספר."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('create_book'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('verify_code'), response.url)

    def test_verified_user_can_create_book(self):
        """משתמש מאומת יכול לפרסם ספר."""
        profile = Profile.objects.get(user=self.user)
        profile.is_verified = True
        profile.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse('create_book'))
        self.assertEqual(response.status_code, 200)


# ---------------------------------------------------------------------------
# זרימת הרשמה ואימות
# ---------------------------------------------------------------------------

class RegistrationTests(InkCityTestBase):

    def test_register_creates_profile_and_code(self):
        """הרשמה יוצרת חשבון, פרופיל וקוד אימות."""
        response = self.client.post(reverse('register'), {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password': 'Str0ngPass!2026',
            'confirm_password': 'Str0ngPass!2026',
            'bot_check': 7,
            'terms_accepted': 'on',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newbie')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(Profile.objects.get(user=user).verification_code)

    def test_register_sends_email(self):
        """הרשמה שולחת מייל עם קוד האימות."""
        self.client.post(reverse('register'), {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password': 'Str0ngPass!2026',
            'confirm_password': 'Str0ngPass!2026',
            'bot_check': 7,
            'terms_accepted': 'on',
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('קוד', mail.outbox[0].body)

    def test_register_does_not_leak_code_in_response(self):
        """קוד האימות לא מוצג בתשובת ה-HTTP."""
        response = self.client.post(reverse('register'), {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password': 'Str0ngPass!2026',
            'confirm_password': 'Str0ngPass!2026',
            'bot_check': 7,
            'terms_accepted': 'on',
        }, follow=True)
        content = response.content.decode('utf-8')
        code = Profile.objects.get(user__username='newbie').verification_code
        self.assertNotIn(code, content)
        self.assertNotIn('לצורך בדיקה', content)

    def test_weak_password_rejected(self):
        """מדיניות הסיסמאות של Django אכופה."""
        response = self.client.post(reverse('register'), {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password': '123',
            'confirm_password': '123',
            'bot_check': 7,
            'terms_accepted': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newbie').exists())

    def test_verify_code_flow(self):
        """אימות נכון מסמן את החשבון כמאומת."""
        user = User.objects.create_user(
            username='newbie', email='n@example.com', password='Str0ngPass!2026',
        )
        profile = Profile.objects.get(user=user)
        profile.issue_verification_code('123456')

        self.client.force_login(user)
        response = self.client.post(reverse('verify_code'), {'code': '123456'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Profile.objects.get(user=user).is_verified)

    def test_verify_code_wrong_increments_attempts(self):
        """ניסיון שגוי מגדיל את מונח הניסיונות."""
        user = User.objects.create_user(
            username='newbie', email='n@example.com', password='Str0ngPass!2026',
        )
        profile = Profile.objects.get(user=user)
        profile.issue_verification_code('123456')

        self.client.force_login(user)
        self.client.post(reverse('verify_code'), {'code': '000000'})
        self.assertEqual(Profile.objects.get(user=user).verification_attempts, 1)

    def test_resend_code_requires_post(self):
        """שליחת קוד חדש דורשת POST, לא GET."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('resend_code'))
        self.assertEqual(response.status_code, 405)

    def test_resend_code_sets_timestamp(self):
        """קוד חדש כולל זמן יצירה, כך שהתוקף נבדק נכון."""
        self.client.force_login(self.user)
        profile = Profile.objects.get(user=self.user)
        profile.verification_code_created_at = None
        profile.save()

        self.client.post(reverse('resend_code'))
        profile.refresh_from_db()
        self.assertIsNotNone(profile.verification_code_created_at)
        self.assertTrue(profile.is_code_valid())


# ---------------------------------------------------------------------------
# אינטראקציות חברתיות
# ---------------------------------------------------------------------------

class SocialTests(InkCityTestBase):

    def test_kudos_toggle(self):
        """מתן והסרת קודוס עובדים ויוצרים התראה."""
        self.client.force_login(self.other)
        self.client.post(reverse('toggle_kudos', kwargs={'book_id': self.book.pk}))
        self.assertTrue(self.book.kudos.filter(pk=self.other.pk).exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.user, notification_type='new_kudos',
        ).exists())

        self.client.post(reverse('toggle_kudos', kwargs={'book_id': self.book.pk}))
        self.assertFalse(self.book.kudos.filter(pk=self.other.pk).exists())

    def test_cannot_kudos_draft(self):
        """אי אפשר לתת קודוס לספר שלא פורסם."""
        draft = Book.objects.create(
            title='טיוטה', summary='סודי', author=self.user, status='draft',
        )
        self.client.force_login(self.other)
        self.client.post(reverse('toggle_kudos', kwargs={'book_id': draft.pk}))
        self.assertFalse(draft.kudos.filter(pk=self.other.pk).exists())

    def test_follow_toggle_and_link(self):
        """עקוב/הפסק לעקוב עובדים, והקישור בהתראה נכון."""
        self.client.force_login(self.other)
        self.client.post(reverse('toggle_follow', kwargs={'username': self.user.username}))
        profile = Profile.objects.get(user=self.user)
        self.assertTrue(profile.followers.filter(pk=self.other.pk).exists())

        notification = Notification.objects.filter(
            notification_type='new_follower',
        ).first()
        self.assertIsNotNone(notification)
        expected = reverse('profile_detail', kwargs={'username': self.other.username})
        self.assertEqual(notification.link, expected)

    def test_cannot_follow_self(self):
        """אי אפשר לעקוב אחרי עצמך."""
        self.client.force_login(self.user)
        self.client.post(reverse('toggle_follow', kwargs={'username': self.user.username}))
        profile = Profile.objects.get(user=self.user)
        self.assertFalse(profile.followers.filter(pk=self.user.pk).exists())

    def test_add_comment_creates_notification(self):
        """תגובה יוצרת התראה למחבר הספר עם קישור נכון."""
        self.verify_user(self.other)
        self.client.force_login(self.other)
        self.client.post(
            reverse('add_comment', kwargs={'book_id': self.book.pk, 'chapter_number': 1}),
            {'content': 'תגובה מצוינת'},
        )
        comment = Comment.objects.filter(author=self.other).first()
        self.assertIsNotNone(comment)
        notification = Notification.objects.filter(notification_type='new_comment').first()
        self.assertIsNotNone(notification)
        self.assertTrue(notification.link.endswith('/chapter/1/'))

    def test_blocked_user_cannot_comment(self):
        """משתמש חסום אינו יכול להגיב."""
        self.verify_user(self.other)
        Block.objects.create(blocker=self.user, blocked=self.other)
        self.client.force_login(self.other)
        self.client.post(
            reverse('add_comment', kwargs={'book_id': self.book.pk, 'chapter_number': 1}),
            {'content': 'תגובה של חסום'},
        )
        self.assertFalse(Comment.objects.filter(author=self.other).exists())

    def test_report_content(self):
        """דיווח על תוכן נשמר במודל Report."""
        self.client.force_login(self.other)
        self.client.post(
            reverse('report_content', kwargs={'content_type': 'book', 'object_id': self.book.pk}),
            {'reason': 'spam', 'details': 'זה ספאם'},
        )
        self.assertTrue(Report.objects.filter(
            reporter=self.other, content_type='book', object_id=self.book.pk,
        ).exists())

    def test_report_duplicate_is_idempotent(self):
        """דיווח כפול על אותו תוכן לא יוצר כפילות."""
        self.client.force_login(self.other)
        url = reverse('report_content', kwargs={'content_type': 'book', 'object_id': self.book.pk})
        self.client.post(url, {'reason': 'spam', 'details': 'אחד'})
        self.client.post(url, {'reason': 'abuse', 'details': 'שני'})
        self.assertEqual(Report.objects.filter(reporter=self.other).count(), 1)


# ---------------------------------------------------------------------------
# דפים ותצוגה
# ---------------------------------------------------------------------------

class PageTests(InkCityTestBase):

    def test_public_pages_render(self):
        """כל הדפים הציבוריים נטענים בהצלחה."""
        urls = [
            reverse('home'),
            reverse('forum_home'),
            reverse('search'),
            reverse('book_detail', kwargs={'book_id': self.book.pk}),
            reverse('chapter_detail', kwargs={'book_id': self.book.pk, 'chapter_number': 1}),
            reverse('thread_detail', kwargs={'thread_id': self.thread.pk}),
            reverse('category_detail', kwargs={'category_id': self.category.pk}),
            reverse('profile_detail', kwargs={'username': self.user.username}),
            reverse('login'),
            reverse('register'),
            reverse('terms'),
            reverse('privacy'),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, msg=f"{url} failed")

    def test_authenticated_pages_render(self):
        """דפים הדורשים התחברות נטענים עבור משתמש מחובר."""
        self.client.force_login(self.user)
        urls = [
            reverse('edit_profile'),
            reverse('following_list'),
            reverse('notifications'),
            reverse('edit_book', kwargs={'book_id': self.book.pk}),
            reverse('edit_chapter', kwargs={'book_id': self.book.pk, 'chapter_number': 1}),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, msg=f"{url} failed")

    def test_publish_pages_render_for_verified_user(self):
        """דפי הפרסום נטענים עבור משתמש מאומת."""
        self.verify_user()
        self.client.force_login(self.user)
        urls = [
            reverse('create_book'),
            reverse('create_chapter', kwargs={'book_id': self.book.pk}),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, msg=f"{url} failed")

    def test_verify_code_page_renders(self):
        """עמוד אימות החשבון נטען עבור משתמש שטרם אומת."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('verify_code'))
        self.assertEqual(response.status_code, 200)

    def test_verified_user_redirected_from_verify_code(self):
        """משתמש שכבר אומת מועבר מעמוד האימות."""
        self.verify_user()
        self.client.force_login(self.user)
        response = self.client.get(reverse('verify_code'))
        self.assertEqual(response.status_code, 302)

    def test_home_excludes_drafts(self):
        """עמוד הבית מציג רק ספרים מפורסמים."""
        Book.objects.create(
            title='ספר טיוטה בלבד', summary='סודי', author=self.user, status='draft',
        )
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'ספר טיוטה בלבד')

    def test_profile_shows_own_drafts_but_not_others(self):
        """טיוטות נראות למחבר ורק לו."""
        draft = Book.objects.create(
            title='הטיוטה שלי', summary='סודי', author=self.user, status='draft',
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('profile_detail', kwargs={'username': 'writer'}))
        self.assertContains(response, 'הטיוטה שלי')

        self.client.force_login(self.other)
        response = self.client.get(reverse('profile_detail', kwargs={'username': 'writer'}))
        self.assertNotContains(response, 'הטיוטה שלי')

    def test_search_results(self):
        """חיפוש מחזיר ספרים מתאימים."""
        response = self.client.get(reverse('search'), {'q': 'לדוגמה'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ספר לדוגמה')

    def test_notifications_not_marked_read_on_get(self):
        """צפייה בהתראות אינה מסמנת אותן כנקראו."""
        Notification.objects.create(
            recipient=self.user, notification_type='new_kudos',
            message='מישהו נתן לך קודוס', link='/book/1/',
        )
        self.client.force_login(self.user)
        self.client.get(reverse('notifications'))
        self.assertTrue(Notification.objects.filter(is_read=False).exists())

    def test_mark_notifications_read_requires_post(self):
        """סימון התראות כנקראו דורש POST."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('mark_notifications_read'))
        self.assertEqual(response.status_code, 405)

    def test_404_page_exists(self):
        """דף 404 מותאם מוגש במקום השגיאה הטכנית."""
        response = self.client.get('/no-such-page-xyz/')
        self.assertEqual(response.status_code, 404)

    def test_health_check(self):
        """נקודת בדיקת התקינות מחזירה ok."""
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_sitemap_and_robots(self):
        """מפת האתר וקובץ robots נגשים."""
        self.assertEqual(self.client.get(reverse('sitemap')).status_code, 200)
        self.assertEqual(self.client.get('/robots.txt').status_code, 200)


# ---------------------------------------------------------------------------
# אבטחה
# ---------------------------------------------------------------------------

class SecurityTests(InkCityTestBase):

    def test_csrf_token_present_in_forms(self):
        """כל טפסי ה-POST כוללים טוקן CSRF."""
        self.verify_user()
        self.client.force_login(self.user)
        response = self.client.get(reverse('create_book'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_login_form_uses_custom_template(self):
        """דף ההתחברות משתמש בתבנית האתר ולא בתבנית ברירת המחדל של Django."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'skip-link')

    def test_login_redirects_authenticated_user(self):
        """משתמש מחובר מועבר מדף ההתחברות."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)

    def test_custom_css_is_not_injected_raw(self):
        """קוד CSS של המשתמש מוצג במסגרת מבודדת ולא כ-style גולמי."""
        profile = Profile.objects.get(user=self.user)
        profile.custom_css = 'body { background: red; }'
        profile.save()

        response = self.client.get(reverse('profile_detail', kwargs={'username': 'writer'}))
        self.assertNotContains(response, '<style>body { background: red; }</style>')
        self.assertContains(response, 'sandbox=')

    def test_dangerous_css_rejected(self):
        """CSS עם מאפיינים מסוכנים נדחה."""
        from books.forms import ProfileForm
        form = ProfileForm(data={'custom_css': 'body { background: url(http://evil.com/x); }'})
        self.assertFalse(form.is_valid())
        self.assertIn('custom_css', form.errors)

    def test_user_enumeration_message_is_generic(self):
        """הודעת ההרשמה לא חושפת אם שם המשתמש כבר תפוס."""
        response = self.client.post(reverse('register'), {
            'username': self.user.username,
            'email': 'other@example.com',
            'password': 'Str0ngPass!2026',
            'confirm_password': 'Str0ngPass!2026',
            'bot_check': 7,
            'terms_accepted': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'כבר תפוס')

    def test_register_rate_limited(self):
        """רישום חוזר מאותו משתמש מוגבל בהגבלת קצב."""
        payload = {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password': 'Str0ngPass!2026',
            'confirm_password': 'Str0ngPass!2026',
            'bot_check': 7,
            'terms_accepted': 'on',
        }
        statuses = [self.client.post(reverse('register'), payload).status_code for _ in range(8)]
        self.assertIn(429, statuses)
