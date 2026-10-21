"""Context processors של אפליקציית books."""

from django.core.cache import cache


def unread_notifications(request):
    """מספר ההתראות שלא נקראו, עם מטמון קצר כדי לא להריץ COUNT בכל בקשה."""
    if not request.user.is_authenticated:
        return {'unread_notifications_count': 0}

    cache_key = f"unread_notifications:{request.user.pk}"
    count = cache.get(cache_key)
    if count is None:
        count = request.user.notifications.filter(is_read=False).count()
        cache.set(cache_key, count, timeout=30)
    return {'unread_notifications_count': count}


def site_meta(request):
    """נתוני מטא נוספים הזמינים לכל התבניות."""
    return {
        'SITE_NAME': 'InkCity',
        'SITE_TAGLINE': 'קהילת הכותבים והקוראים',
    }
