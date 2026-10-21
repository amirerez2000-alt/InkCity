"""הגדרות לוח הניהול — מאפשרות מודרציה יעילה של תוכן."""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
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


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'chapter_count', 'kudos_count', 'created_at')
    list_filter = ('status', 'is_deleted', 'created_at')
    search_fields = ('title', 'summary', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('author',)
    date_hierarchy = 'created_at'
    actions = ('restore_books',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author')

    @admin.display(description='פרקים')
    def chapter_count(self, obj):
        return obj.chapters.filter(is_deleted=False).count()

    @admin.display(description='קודוסים')
    def kudos_count(self, obj):
        return obj.kudos.count()

    @admin.action(description='שחזור הספרים שנבחרו')
    def restore_books(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} ספרים שוחזרו.")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'book', 'chapter_number', 'author_name', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('title', 'content', 'book__title')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('book',)
    actions = ('restore_chapters',)

    @admin.display(description='מחבר')
    def author_name(self, obj):
        return obj.book.author.username

    @admin.action(description='שחזור הפרקים שנבחרו')
    def restore_chapters(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} פרקים שוחזרו.")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'followers_count', 'is_verified', 'last_active', 'created_at')
    list_filter = ('is_verified', 'last_active')
    search_fields = ('user__username', 'bio')
    readonly_fields = ('created_at', 'updated_at', 'last_active')
    list_select_related = ('user',)

    @admin.display(description='עוקבים')
    def followers_count(self, obj):
        return obj.followers.count()


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('short_content', 'author', 'chapter', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('author', 'chapter')
    actions = ('restore_comments',)

    @admin.display(description='תוכן')
    def short_content(self, obj):
        text = obj.content[:60]
        return format_html('{}…', text) if len(obj.content) > 60 else text

    @admin.action(description='שחזור התגובות שנבחרו')
    def restore_comments(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} תגובות שוחזרו.")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'thread_count', 'created_at')
    search_fields = ('name', 'description')
    list_select_related = ()

    @admin.display(description='דיונים')
    def thread_count(self, obj):
        return obj.threads.filter(is_deleted=False).count()


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'author', 'post_count', 'updated_at')
    list_filter = ('category', 'is_deleted', 'updated_at')
    search_fields = ('title', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('category', 'author')
    actions = ('restore_threads',)

    @admin.display(description='הודעות')
    def post_count(self, obj):
        return obj.posts.filter(is_deleted=False).count()

    @admin.action(description='שחזור הדיונים שנבחרו')
    def restore_threads(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} דיונים שוחזרו.")


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ('short_content', 'author', 'thread', 'created_at')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('author', 'thread')
    actions = ('restore_posts',)

    @admin.display(description='תוכן')
    def short_content(self, obj):
        text = obj.content[:60]
        return format_html('{}…', text) if len(obj.content) > 60 else text

    @admin.action(description='שחזור ההודעות שנבחרו')
    def restore_posts(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} הודעות שוחזרו.")


@admin.register(SiteUpdate)
class SiteUpdateAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(GlobalChatMsg)
class GlobalChatMsgAdmin(admin.ModelAdmin):
    list_display = ('author', 'content', 'created_at')
    search_fields = ('content', 'author__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('author',)
    actions = ('delete_messages',)

    @admin.action(description='מחיקת ההודעות שנבחרו')
    def delete_messages(self, request, queryset):
        deleted = queryset.delete()[0]
        self.message_user(request, f"{deleted} הודעות נמחקו.")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'short_message', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('message', 'recipient__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('recipient', 'sender')

    @admin.display(description='הודעה')
    def short_message(self, obj):
        return obj.message[:70]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'object_id', 'reason', 'reporter', 'status', 'created_at')
    list_filter = ('status', 'reason', 'content_type', 'created_at')
    search_fields = ('reporter__username', 'details')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('reporter', 'handled_by')
    actions = ('mark_resolved', 'mark_dismissed')

    @admin.action(description='סימון כטופל')
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status='resolved', handled_by=request.user)
        self.message_user(request, f"{updated} דיווחים סומנו כטופלו.")

    @admin.action(description='סימון כנדחה')
    def mark_dismissed(self, request, queryset):
        updated = queryset.update(status='dismissed', handled_by=request.user)
        self.message_user(request, f"{updated} דיווחים נדחו.")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('blocker', 'blocked', 'reason', 'created_at')
    search_fields = ('blocker__username', 'blocked__username')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('blocker', 'blocked')
