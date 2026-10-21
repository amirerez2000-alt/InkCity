"""הגבלת קצב פעולות רגישות, מבוססת על מטמון Django.

ההגבלה נשמרת לפי מפתח (משתמש או כתובת IP) בתוך המטמון, כך שהיא עובדת
גם בסביבה מרובת תהליכים כל עוד מוגדר מטמון משותף (Redis).
"""

from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect

DEFAULT_LIMIT = 10          # כמה בקשות
DEFAULT_WINDOW = 60         # באיזה חלון (בשניות)


def _client_ip(request):
    """מחזיר את כתובת ה-IP של הלקוח, תוך התחשבות ב-proxy."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _key(request, scope):
    if request.user.is_authenticated:
        return f"ratelimit:{scope}:user:{request.user.pk}"
    return f"ratelimit:{scope}:ip:{_client_ip(request)}"


def rate_limit(scope, limit=DEFAULT_LIMIT, window=DEFAULT_WINDOW, message=None):
    """דקורטור שמגביל את מספר הבקשות בחלון זמן.

    מחזיר 429 עם הודעה בבקשות POST, ומציג הודעה ומפנה בבקשות GET.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            key = _key(request, scope)
            count = cache.get(key, 0)
            if count >= limit:
                text = message or 'עשית כמה פעולות רבות מדי. נסה שוב בעוד רגע.'
                if request.method == 'POST':
                    return HttpResponse(
                        text, status=429, content_type='text/plain; charset=utf-8'
                    )
                messages.warning(request, text)
                return redirect(request.path)

            cache.set(key, count + 1, timeout=window)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# --- מגבלות מוכנות לפי תחום ---------------------------------------------

def limit_login(view_func):
    return rate_limit(
        'login', limit=10, window=300,
        message='יותר מדי ניסיונות כניסה. נסה שוב בעוד כמה דקות.',
    )(view_func)


def limit_register(view_func):
    return rate_limit(
        'register', limit=5, window=3600,
        message='נרשמת יותר מדי חשבונים. נסה שוב מאוחר יותר.',
    )(view_func)


def limit_verify(view_func):
    return rate_limit(
        'verify', limit=10, window=900,
        message='יותר מדי ניסיונות אימות. נסה שום מאוחר יותר.',
    )(view_func)


def limit_resend(view_func):
    return rate_limit(
        'resend', limit=3, window=900,
        message='ביקשת יותר מדי קודי אימות. נסה שוב בעוד כמה דקות.',
    )(view_func)


def limit_comment(view_func):
    return rate_limit(
        'comment', limit=20, window=60,
        message='אתה כותב תגובות מהר מדי. נסה שוב בעוד רגע.',
    )(view_func)


def limit_chat(view_func):
    return rate_limit(
        'chat', limit=15, window=60,
        message='אתה שולח הודעות מהר מדי. נסה שוב בעוד רגע.',
    )(view_func)


def limit_thread(view_func):
    return rate_limit(
        'thread', limit=10, window=300,
        message='אתה פותח יותר מדי דיונים. נסה שוב מאוחר יותר.',
    )(view_func)


def limit_search(view_func):
    return rate_limit(
        'search', limit=60, window=60,
        message='מבצע יותר מדי חיפושים. נסה שוב בעוד רגע.',
    )(view_func)
