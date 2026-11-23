import logging

from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver

from .client_ip import client_ip as _client_ip

logger = logging.getLogger("agenda.security")


def _masked(email):
    email = str(email or "")
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):
    email = credentials.get("email") or credentials.get("username") or ""
    logger.warning("login_failed email=%s ip=%s", _masked(email), _client_ip(request))
