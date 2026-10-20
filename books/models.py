from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

class Book(models.Model):
    title = models.CharField(max_length=200, verbose_name="כותרת הספר")
    summary = models.TextField(verbose_name="תקציר")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    kudos = models.ManyToManyField(User, related_name='kudos_books', blank=True)
    cover = models.ImageField(upload_to='covers/', blank=True, null=True, verbose_name="כריכת הספר")
    STATUS_CHOICES = (
        ('draft', 'טיוטה (מוסתר)'),
        ('published', 'מפורסם (גלוי לכולם)'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft')

    def __str__(self):
        return self.title

class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=200, verbose_name="שם הפרק")
    content = models.TextField(verbose_name="תוכן הפרק")
    chapter_number = models.PositiveIntegerField(verbose_name="מספר פרק")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['chapter_number'] # סידור אוטומטי של הפרקים לפי המספר שלהם

    def __str__(self):
        return f"{self.book.title} - פרק {self.chapter_number}: {self.title}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    banner = models.ImageField(upload_to='banners/', blank=True, null=True)
    followers = models.ManyToManyField(User, related_name='following', blank=True)
    last_active = models.DateTimeField(auto_now=True)
    custom_css = models.TextField(blank=True, null=True)

    # אבטחת אימות מייל
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    verification_code_created_at = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    def is_code_valid(self):
        """בודק אם קוד האימות קיים ולא עברו יותר מ-15 דקות מאז יצירתו"""
        if not self.verification_code or not self.verification_code_created_at:
            return False
        now = timezone.now()
        expiration_time = self.verification_code_created_at + datetime.timedelta(minutes=15)
        return now <= expiration_time

    def __str__(self):
        return f"Profile of {self.user.username}"

class Comment(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name="תוכן התגובה")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at'] # תגובות יישמרו בסדר כרונולוגי

    def __str__(self):
        return f"תגובה מאת {self.author.username} בפרק {self.chapter.title}"

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="שם הקטגוריה")
    description = models.TextField(blank=True, verbose_name="תיאור הקטגוריה")

    class Meta:
        verbose_name_plural = "Categories"

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']  # דיונים שהגיבו בהם לאחרונה יקפצו למעלה

    def __str__(self):
        return self.title


class ForumPost(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name='posts'
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='forum_posts'
    )
    content = models.TextField(verbose_name="תוכן ההודעה")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return (
            f"הודעה מאת {self.author.username} בשרשור {self.thread.title}"
        )

class SiteUpdate(models.Model):
    title = models.CharField(max_length=200, verbose_name="כותרת העדכון")
    content = models.TextField(verbose_name="תוכן העדכון")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class GlobalChatMsg(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    content = models.CharField(max_length=255, verbose_name="תוכן ההודעה")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] # הכי חדש למעלה

    def __str__(self):
        return f"{self.author.username}: {self.content}"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('new_book', 'ספר חדש'),
        ('new_chapter', 'פרק חדש'),
        ('new_comment', 'תגובה חדשה'),
        ('new_kudos', 'קודוס חדש'),
        ('new_follower', 'עוקב חדש'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="מקבל ההתראה")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="שולח ההתראה")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name="סוג התראה")
    message = models.CharField(max_length=255, verbose_name="תוכן ההתראה")
    link = models.CharField(max_length=255, blank=True, verbose_name="קישור לפעולה")
    is_read = models.BooleanField(default=False, verbose_name="נקרא?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"התראה ל-{self.recipient.username}: {self.message}"