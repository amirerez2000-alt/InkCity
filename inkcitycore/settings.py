"""
Django settings for inkcitycore project.

Configuration is read from environment variables so that secrets never live
in the repository. Copy `.env.example` to `.env` and fill in the values
before running in production.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    """Reads a boolean environment variable."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    """Reads a comma-separated environment variable into a list."""
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

# SECURITY WARNING: keep the secret key used in production secret!
# In production the key MUST be provided via the SECRET_KEY environment
# variable — the project refuses to start without it.
SECRET_KEY = os.environ.get('SECRET_KEY', '')

DEBUG = env_bool('DEBUG', False)

# Allow DEBUG=True for local development only.
if DEBUG:
    SECRET_KEY = SECRET_KEY or 'django-insecure-local-development-key-only'
    ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
else:
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY environment variable is required when DEBUG is False. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    if SECRET_KEY.startswith('django-insecure-'):
        raise RuntimeError(
            "SECRET_KEY must not use the insecure default value in production."
        )
    ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
    if not ALLOWED_HOSTS:
        raise RuntimeError(
            "ALLOWED_HOSTS environment variable is required when DEBUG is False."
        )

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'books.apps.BooksConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'inkcitycore.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'books.context_processors.unread_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'inkcitycore.wsgi.application'
ASGI_APPLICATION = 'inkcitycore.asgi.application'


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'he'

TIME_ZONE = 'Asia/Jerusalem'

USE_I18N = True

USE_TZ = True

# התאמת תאריכים לפורמט עברי
DATE_FORMAT = 'j F Y'
DATETIME_FORMAT = 'j F Y, H:i'
SHORT_DATE_FORMAT = 'd/m/Y'
SHORT_DATETIME_FORMAT = 'd/m/Y H:i'
FIRST_DAY_OF_WEEK = 0  # יום ראשון
DECIMAL_SEPARATOR = '.'
THOUSAND_SEPARATOR = ','


# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# מגבלת גודל להעלאת קבצים (10MB) — מגביל גם את קבצי התמונה
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# הגבלת מספר הקבצים בבקשה אחת
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'InkCity <noreply@inkcity.com>')
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 10))


# ---------------------------------------------------------------------------
# Sessions & authentication
# ---------------------------------------------------------------------------

LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # שבועיים
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = False

# מגבלת ניסיונות כניסה (django-axes מומלץ להגנה מלאה)
AXES_ENABLED = env_bool('AXES_ENABLED', False)
AXES_FAILURE_LIMIT = int(os.environ.get('AXES_FAILURE_LIMIT', 5))
AXES_COOLOFF_TIME = int(os.environ.get('AXES_COOLOFF_TIME', 30))

# הגבלת קצב לפעולות רגישות — מיושמת ב-books/ratelimit.py
RATELIMIT_ENABLE = env_bool('RATELIMIT_ENABLE', True)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

CACHES = {
    'default': {
        'BACKEND': os.environ.get(
            'CACHE_BACKEND',
            'django.core.cache.backends.locmem.LocMemCache',
        ),
        'LOCATION': os.environ.get('CACHE_LOCATION', 'inkcity-default'),
        'TIMEOUT': int(os.environ.get('CACHE_TIMEOUT', 300)),
    }
}


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# יוצר את תיקיית הלוגים אם אינה קיימת
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.environ.get('LOG_FILE', str(BASE_DIR / 'logs' / 'inkcity.log')),
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'delay': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'books': {
            'handlers': ['console'],
            'level': os.environ.get('BOOKS_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}


# ---------------------------------------------------------------------------
# Production security
# ---------------------------------------------------------------------------

if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'
    # מאחורי reverse proxy (nginx / Cloudflare) — מאפשר לזהות HTTPS
    if os.environ.get('SECURE_PROXY_SSL_HEADER'):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    if CSRF_TRUSTED_ORIGINS:
        CSRF_COOKIE_SECURE = True
    # הגבלת תוכן מאתגר למנוע הזרקת סקריפטים דרך שדות משתמש
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )
    SECURE_CROSS_ORIGIN_RESOURCE_POLICY = 'same-origin'


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------

# מספר הניסיונות המרבי להזנת קוד אימות
MAX_VERIFICATION_ATTEMPTS = int(os.environ.get('MAX_VERIFICATION_ATTEMPTS', 5))

# משך תוקף קוד האימות בדקות
VERIFICATION_CODE_TTL_MINUTES = int(os.environ.get('VERIFICATION_CODE_TTL_MINUTES', 15))

# משך תוקף קישור האקטיבציה (שעות)
PASSWORD_RESET_TIMEOUT = int(os.environ.get('PASSWORD_RESET_TIMEOUT', 48 * 3600))
