import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import send_mail
from django.core import signing

logger = logging.getLogger("agenda.security")
SALT = "identity.email-verification"


def make_verification_token(user, plan=None):
    return signing.dumps(
        {"uid": str(user.pk), "plan": plan.code if plan else ""}, salt=SALT,
    )


def send_verification_email(user, plan=None):
    token = quote(make_verification_token(user, plan), safe="")
    link = f"{settings.AGENDA_WEB_BASE_URL}/verificar?token={token}"
    greeting = f"Hola {user.first_name}:" if user.first_name else "Hola:"
    body = (
        f"{greeting}\n\n"
        "Tu cuenta de AGENDA está casi lista. Confirma tu correo para activarla:\n\n"
        f"{link}\n\n"
        "El enlace vence en 48 horas. Si no creaste esta cuenta, ignora este mensaje.\n"
    )
    try:
        send_mail("Activa tu cuenta de AGENDA", body, None, [user.email])
    except Exception:
        # El alta ya se confirmó al visitante; el reenvío es la vía de recuperación.
        logger.exception("verification_email_failed user_id=%s", user.pk)
