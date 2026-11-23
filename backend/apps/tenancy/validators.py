import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError

RESERVED_COMPANY_SLUGS = frozenset({
    "admin", "agenda", "api", "app", "auth", "b", "health", "login", "media",
    "mobile", "public", "register", "saas", "static",
})


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError("Usa una zona horaria IANA válida, por ejemplo America/Santiago.")


def validate_hex_color(value):
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value or ""):
        raise ValidationError("Usa un color hexadecimal con formato #RRGGBB.")


def validate_company_slug(value):
    if value in RESERVED_COMPANY_SLUGS:
        raise ValidationError("Este identificador está reservado por la plataforma.")
