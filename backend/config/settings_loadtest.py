"""Ajustes para pruebas de carga locales con Locust. No usar en producción."""
import os

from .settings import *  # noqa: F401,F403

DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("AGENDA_LOADTEST_DB", BASE_DIR / "loadtest.sqlite3"),
        "OPTIONS": {"timeout": 30},
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
# El login con PBKDF2 cuesta ~1 s de CPU por hash y distorsiona las pruebas;
# el coste real se mide aparte. Solo para la base de carga.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        scope: "1000000/minute" for scope in REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    },
}
LOGGING = {
    **LOGGING,
    "loggers": {
        **LOGGING["loggers"],
        "agenda.security": {**LOGGING["loggers"]["agenda.security"], "level": "WARNING"},
    },
}
