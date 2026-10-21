from django.apps import AppConfig


class BooksConfig(AppConfig):
    name = 'books'
    verbose_name = 'ספרים וקהילה'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # טעינת האותות (יצירת פרופיל אוטומטית)
        from . import signals  # noqa: F401
