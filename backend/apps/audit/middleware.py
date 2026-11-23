import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse

from apps.identity.client_ip import client_ip as _client_ip

logger = logging.getLogger("agenda.security")

ADMIN_LOGIN_MAX_ATTEMPTS = 10
ADMIN_LOGIN_WINDOW_SECONDS = 300


def _user_label(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return str(user.pk)
    return "anon"


class SecurityEventsMiddleware:
    """Log denied/throttled requests and rate-limit the admin login form."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_login_path = f"/{settings.ADMIN_PATH}/login/"

    def __call__(self, request):
        if request.path == self.admin_login_path and request.method == "POST":
            if self._admin_login_blocked(request):
                logger.warning(
                    "admin_login_throttled ip=%s", _client_ip(request),
                )
                return HttpResponse(
                    "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.",
                    status=429,
                    content_type="text/plain; charset=utf-8",
                )
        response = self.get_response(request)
        status = response.status_code
        if status == 429 or status == 403 or (
            status == 401 and _user_label(request) != "anon"
        ):
            logger.warning(
                "request_denied status=%s method=%s path=%s user=%s ip=%s",
                status, request.method, request.path, _user_label(request),
                _client_ip(request),
            )
        return response

    def _admin_login_blocked(self, request):
        key = f"agenda:admin-login:{_client_ip(request)}"
        try:
            cache.add(key, 0, timeout=ADMIN_LOGIN_WINDOW_SECONDS)
            attempts = cache.incr(key)
        except ValueError:
            return False
        return attempts > ADMIN_LOGIN_MAX_ATTEMPTS
