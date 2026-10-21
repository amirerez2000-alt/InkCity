from django.urls import path
from . import views

urlpatterns = [
    # עמודים ציבוריים
    path('', views.home, name='home'),
    path('health/', views.health_check, name='health_check'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path(
        'book/<int:book_id>/chapter/<int:chapter_number>/',
        views.chapter_detail,
        name='chapter_detail',
    ),

    # הרשמה ואימות
    path('register/', views.register, name='register'),
    path('verify-code/', views.verify_code, name='verify_code'),
    path('resend-code/', views.resend_code, name='resend_code'),

    # יצירת תוכן
    path('create-book/', views.create_book, name='create_book'),
    path('book/<int:book_id>/add-chapter/', views.create_chapter, name='create_chapter'),
    path(
        'book/<int:book_id>/chapter/<int:chapter_number>/comment/',
        views.add_comment,
        name='add_comment',
    ),

    # פרופילים וחברתיות
    path('user/<str:username>/', views.profile_detail, name='profile_detail'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('book/<int:book_id>/kudos/', views.toggle_kudos, name='toggle_kudos'),
    path('profile/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('profile/<str:username>/block/', views.block_user, name='block_user'),
    path('profile/<str:username>/unblock/', views.unblock_user, name='unblock_user'),
    path('notifications/', views.notifications_page, name='notifications'),
    path('notifications/read-all/', views.mark_notifications_read, name='mark_notifications_read'),
    path('following/', views.following_list, name='following_list'),

    # חיפוש
    path('search/', views.search_results, name='search'),

    # דפים משפטיים
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),

    # עריכה ומחיקה
    path('book/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('book/<int:book_id>/delete/', views.delete_book, name='delete_book'),
    path(
        'book/<int:book_id>/chapter/<int:chapter_number>/edit/',
        views.edit_chapter,
        name='edit_chapter',
    ),
    path(
        'book/<int:book_id>/chapter/<int:chapter_number>/delete/',
        views.delete_chapter,
        name='delete_chapter',
    ),

    # דיווח על תוכן
    path(
        'report/<str:content_type>/<int:object_id>/',
        views.report_content,
        name='report_content',
    ),

    # פורום
    path('forum/', views.forum_home, name='forum_home'),
    path(
        'forum/category/<int:category_id>/',
        views.category_detail,
        name='category_detail',
    ),
    path(
        'forum/category/<int:category_id>/create/',
        views.create_thread,
        name='create_thread',
    ),
    path(
        'forum/thread/<int:thread_id>/',
        views.thread_detail,
        name='thread_detail',
    ),
]
