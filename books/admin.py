from django.contrib import admin
from .models import Book, Chapter, Profile, Comment, Category, Thread, ForumPost, SiteUpdate, GlobalChatMsg

admin.site.register(Book)
admin.site.register(Chapter)
admin.site.register(Profile)
admin.site.register(Comment)
admin.site.register(Category)
admin.site.register(Thread)
admin.site.register(ForumPost)
admin.site.register(SiteUpdate)
admin.site.register(GlobalChatMsg)