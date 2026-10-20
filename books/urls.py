from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('book/<int:book_id>/chapter/<int:chapter_number>/', views.chapter_detail, name='chapter_detail'),
    path('register/', views.register, name='register'),
    path('create-book/', views.create_book, name='create_book'),
    path('book/<int:book_id>/add-chapter/', views.create_chapter, name='create_chapter'),
    path('book/<int:book_id>/kudos/', views.toggle_kudos, name='toggle_kudos'),
    path('user/<str:username>/', views.profile_detail, name='profile_detail'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('book/<int:book_id>/chapter/<int:chapter_number>/comment/', views.add_comment, name='add_comment'),
    path('forum/', views.forum_home, name='forum_home'),
    path('profile/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('notifications/', views.notifications_page, name='notifications'),
    path('following/', views.following_list, name='following_list'),
    path('search/', views.search_results, name='search'),
    path('book/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('book/<int:book_id>/delete/', views.delete_book, name='delete_book'),
    path('book/<int:book_id>/chapter/<int:chapter_number>/edit/', views.edit_chapter, name='edit_chapter'),
    path('book/<int:book_id>/chapter/<int:chapter_number>/delete/', views.delete_chapter, name='delete_chapter'),
    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
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