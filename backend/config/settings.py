"""Django settings for the AGENDA SaaS API."""
import os
from pathlib import Path

from corsheaders.defaults import default_headers
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "agenda-local-throttle"}}
if os.getenv("DJANGO_TESTING") == "true":
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host]
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
ADMIN_PATH = os.getenv("DJANGO_ADMIN_PATH", "admin").strip("/") or "admin"
CSRF_TRUSTED_ORIGINS = [
    origin for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin
]
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
TRUST_PROXY_HEADERS = os.getenv("DJANGO_TRUST_PROXY_HEADERS", "false").lower() == "true"
TRUSTED_PROXY_COUNT = max(int(os.getenv("DJANGO_TRUSTED_PROXY_COUNT", "1")), 0)

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt", "apps.identity", "apps.tenancy", "apps.audit",
    "rest_framework_simplejwt.token_blacklist",
    "apps.customers", "apps.catalog", "apps.workforce",
    "apps.notifications", "apps.bookings", "apps.inventory", "apps.sales", "apps.reports",
    "apps.billing",
    "apps.mobile",
    "corsheaders",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.SecurityEventsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
              "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

if os.getenv("AGENDA_USE_POSTGRES") == "true" and os.getenv("DATABASE_URL"):
    import dj_database_url
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=not DEBUG)}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "identity.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60
EMAIL_VERIFICATION_TIMEOUT = 60 * 60 * 48
AGENDA_WEB_BASE_URL = os.getenv("AGENDA_WEB_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@agenda.local")
MOBILE_PUSH_PROVIDER = os.getenv("AGENDA_PUSH_PROVIDER", "console")
MOBILE_PUSH_WEBHOOK_URL = os.getenv("AGENDA_PUSH_WEBHOOK_URL", "")
MOBILE_PUSH_TOKEN = os.getenv("AGENDA_PUSH_TOKEN", "")
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    origin for origin in os.getenv("DJANGO_CORS_ORIGINS", "").split(",") if origin
]
CORS_ALLOW_HEADERS = (*default_headers, "x-tenant-context")
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = Path(
    os.environ.get("AGENDA_PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media")
)
if os.getenv("DJANGO_TESTING") == "true":
    PRIVATE_MEDIA_ROOT = Path(
        os.environ.get("AGENDA_TEST_PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media-test")
    )
PUBLIC_BASE_URL = os.getenv("AGENDA_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.tenancy.authentication.TenantJWTAuthentication", "apps.identity.authentication.RevocableJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ["rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/minute", "user": "300/minute", "login": "5/minute", "password_reset": "3/hour", "password_reset_confirm": "10/hour", "registration": "5/hour", "email_verification": "10/hour", "resend_verification": "3/hour", "public": "30/minute", "password_change": "10/hour"},
    "NUM_PROXIES": int(os.getenv("DJANGO_NUM_PROXIES", "0")) or None,
}
BOOKING_SLOT_STEP_MINUTES = 15
PUBLIC_RESCHEDULE_CUTOFF_HOURS = int(os.getenv("AGENDA_RESCHEDULE_CUTOFF_HOURS", "2"))
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=15), "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
              "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True,
              "CHECK_USER_IS_ACTIVE": True, "UPDATE_LAST_LOGIN": True}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "security": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "security"},
    },
    "loggers": {
        "agenda.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise RuntimeError("Configura un backend de correo real antes de activar producción.")

if not DEBUG:
    if SECRET_KEY == "local-development-only-change-me":
        raise RuntimeError("DJANGO_SECRET_KEY debe configurarse en producción.")
    if any(host in {"localhost", "127.0.0.1", "*"} for host in ALLOWED_HOSTS):
        raise RuntimeError("Configura DJANGO_ALLOWED_HOSTS explícitamente en producción.")
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    if not CSRF_TRUSTED_ORIGINS:
        raise RuntimeError("Configura DJANGO_CSRF_TRUSTED_ORIGINS con el dominio HTTPS del panel.")
    if "*" in CORS_ALLOWED_ORIGINS:
        raise RuntimeError("DJANGO_CORS_ORIGINS no admite comodines en producción.")
