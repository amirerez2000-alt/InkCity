from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
import datetime

# משך תוקף קוד האימות בדקות
VERIFICATION_CODE_TTL_MINUTES = 15


class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="כותרת הספר")
    summary = models.TextField(verbose_name="תקציר", max_length=5000)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    kudos = models.ManyToManyField(User, related_name='kudos_books', blank=True)
    cover = models.ImageField(upload_to='covers/', blank=True, null=True, verbose_name="כריכת הספר")
    STATUS_CHOICES = (
        ('draft', 'טיוטה (מוסתר)'),
        ('published', 'מפורסם (גלוי לכולם)'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')
    is_deleted = models.BooleanField(default=False, verbose_name="נמחק (שחזור אפשרי)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='book_status_created_idx'),
            models.Index(fields=['author', '-created_at'], name='book_author_created_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'title'],
                condition=models.Q(is_deleted=False),
                name='unique_book_title_per_author',
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == 'published'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('book_detail', kwargs={'book_id': self.pk})


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200, verbose_name="שם הפרק")
    content = models.TextField(verbose_name="תוכן הפרק", max_length=200000)
    chapter_number = models.PositiveIntegerField(
        verbose_name="מספר פרק",
        validators=[MinValueValidator(1)],
    )
    is_deleted = models.BooleanField(default=False, verbose_name="נמחק (שחזור אפשרי)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['chapter_number']
        indexes = [
            models.Index(fields=['book', 'chapter_number'], name='chapter_book_number_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['book', 'chapter_number'],
                condition=models.Q(is_deleted=False),
                name='unique_chapter_number_per_book',
            ),
        ]

    def __str__(self):
        return f"{self.book.title} - פרק {self.chapter_number}: {self.title}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('chapter_detail', kwargs={
            'book_id': self.book_id,
            'chapter_number': self.chapter_number,
        })


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    banner = models.ImageField(upload_to='banners/', blank=True, null=True)
    followers = models.ManyToManyField(User, related_name='following', blank=True)
    last_active = models.DateTimeField(auto_now=True)
    custom_css = models.TextField(blank=True, null=True, max_length=20000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # אבטחת אימות מייל
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_created_at = models.DateTimeField(blank=True, null=True)
    verification_attempts = models.PositiveIntegerField(default=0, verbose_name="ניסיונות אימות")
    is_verified = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['is_verified', '-last_active'], name='profile_verified_active_idx'),
        ]

    def is_code_valid(self):
        """בודק אם קוד האימות קיים ולא עברו יותר מ-15 דקות מאז יצירתו"""
        if not self.verification_code or not self.verification_code_created_at:
            return False
        expiration_time = self.verification_code_created_at + datetime.timedelta(
            minutes=VERIFICATION_CODE_TTL_MINUTES
        )
        return timezone.now() <= expiration_time

    def issue_verification_code(self, code):
        """מנפיק קוד אימות חדש ומאפס את מונח הניסיונות."""
        self.verification_code = code
        self.verification_code_created_at = timezone.now()
        self.verification_attempts = 0
        self.save(update_fields=[
            'verification_code', 'verification_code_created_at', 'verification_attempts',
        ])

    def clear_verification_code(self):
        """מבטל את קוד האימות הקיים."""
        self.verification_code = None
        self.verification_code_created_at = None
        self.verification_attempts = 0
        self.save(update_fields=[
            'verification_code', 'verification_code_created_at', 'verification_attempts',
        ])

    def __str__(self):
        return f"Profile of {self.user.username}"


class Comment(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name="תוכן התגובה", max_length=5000)
    is_deleted = models.BooleanField(default=False, verbose_name="נמחק (שחזור אפשרי)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chapter', 'created_at'], name='comment_chapter_created_idx'),
            models.Index(fields=['author', '-created_at'], name='comment_author_created_idx'),
        ]

    def __str__(self):
        return f"תגובה מאת {self.author.username} בפרק {self.chapter.title}"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="שם הקטגוריה")
    description = models.TextField(blank=True, verbose_name="תיאור הקטגוריה", max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Thread(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name='threads'
    )
    title = models.CharField(max_length=200, verbose_name="כותרת הדיון")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='threads'
    )
    is_deleted = models.BooleanField(default=False, verbose_name="נמחק (שחזור אפשרי)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['category', '-updated_at'], name='thread_category_updated_idx'),
            models.Index(fields=['author', '-created_at'], name='thread_author_created_idx'),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('thread_detail', kwargs={'thread_id': self.pk})


class ForumPost(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name='posts'
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='forum_posts'
    )
    content = models.TextField(verbose_name="תוכן ההודעה", max_length=10000)
    is_deleted = models.BooleanField(default=False, verbose_name="נמחק (שחזור אפשרי)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['thread', 'created_at'], name='post_thread_created_idx'),
        ]

    def __str__(self):
        return (
            f"הודעה מאת {self.author.username} בשרשור {self.thread.title}"
        )


class SiteUpdate(models.Model):
    title = models.CharField(max_length=200, verbose_name="כותרת העדכון")
    content = models.TextField(verbose_name="תוכן העדכון", max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class GlobalChatMsg(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    content = models.CharField(max_length=255, verbose_name="תוכן ההודעה")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username}: {self.content}"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('new_book', 'ספר חדש'),
        ('new_chapter', 'פרק חדש'),
        ('new_comment', 'תגובה חדשה'),
        ('new_kudos', 'קודוס חדש'),
        ('new_follower', 'עוקב חדש'),
        ('report', 'דיווח'),
    )

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications', verbose_name="מקבל התראה"
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications',
        verbose_name="שולח התראה"
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, verbose_name="סוג התראה", db_index=True
    )
    message = models.CharField(max_length=255, verbose_name="תוכן ההתראה")
    link = models.CharField(max_length=255, blank=True, verbose_name="קישור לפעולה")
    is_read = models.BooleanField(default=False, verbose_name="נקרא?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at'], name='notif_recipient_read_idx'),
        ]

    def __str__(self):
        return f"התראה ל-{self.recipient.username}: {self.message}"


class Report(models.Model):
    """דיווח על תוכן לא תקין — מופיע בתור המודרציה של האדמין."""

    REASON_CHOICES = (
        ('spam', 'ספאם'),
        ('abuse', 'הטרדה'),
        ('offensive', 'תוכן פוגע'),
        ('copyright', 'הפרת זכויות יוצרים'),
        ('other', 'אחר'),
    )
    STATUS_CHOICES = (
        ('open', 'פתוח'),
        ('resolved', 'טופל'),
        ('dismissed', 'נדחה'),
    )

    reporter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='reports_filed', verbose_name="מדווח"
    )
    content_type = models.CharField(max_length=50, verbose_name="סוג התוכן")
    object_id = models.PositiveIntegerField(verbose_name="מזהה התוכן")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='other', verbose_name="סיבה")
    details = models.TextField(blank=True, max_length=2000, verbose_name="פרטים")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='open', db_index=True, verbose_name="סטטוס"
    )
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_handled',
        verbose_name="טופל על ידי"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='report_status_created_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['reporter', 'content_type', 'object_id'],
                name='unique_report_per_user_per_object',
            ),
        ]

    def __str__(self):
        return f"דיווח על {self.content_type} #{self.object_id} ({self.get_reason_display()})"

    def get_target_url(self):
        """מחזיר קישור לתוכן שדווח עליו, אם אפשר."""
        from django.urls import reverse
        if self.content_type == 'book':
            return reverse('book_detail', kwargs={'book_id': self.object_id})
        if self.content_type == 'comment':
            return reverse('chapter_detail', kwargs={
                'book_id': Comment.objects.filter(pk=self.object_id).values_list(
                    'chapter__book_id', flat=True
                ).first() or 0,
                'chapter_number': Comment.objects.filter(pk=self.object_id).values_list(
                    'chapter__chapter_number', flat=True
                ).first() or 0,
            })
        if self.content_type == 'thread':
            return reverse('thread_detail', kwargs={'thread_id': self.object_id})
        if self.content_type == 'forumpost':
            return reverse('thread_detail', kwargs={
                'thread_id': ForumPost.objects.filter(pk=self.object_id).values_list(
                    'thread_id', flat=True
                ).first() or 0,
            })
        return ''


class Block(models.Model):
    """חסימת משתמש — משתמש חסום לא יוכל לרשום תגובות או לפתוח דיונים."""

    blocker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='blocks_made', verbose_name="חוסם"
    )
    blocked = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='blocks_received', verbose_name="חסום"
    )
    reason = models.CharField(max_length=200, blank=True, verbose_name="סיבה")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_block_pair'),
            models.CheckConstraint(
                condition=~models.Q(blocker=models.F('blocked')),
                name='cannot_block_self',
            ),
        ]

    def __str__(self):
        return f"{self.blocker.username} חסם את {self.blocked.username}"
