import re

from django.conf import settings

HEX_COLOR_RE = re.compile(r"#[0-9A-Fa-f]{6}")
DEFAULT_PRIMARY = "#E50914"
DEFAULT_SECONDARY = "#8B0000"


def safe_hex_color(value, fallback):
    return value if HEX_COLOR_RE.fullmatch(value or "") else fallback


def booking_url(company):
    base = (getattr(settings, "PUBLIC_BASE_URL", "") or "").rstrip("/")
    path = f"/b/{company.slug}/"
    return f"{base}{path}" if base else path


def branding_payload(company, request=None):
    logo_url = ""
    if company.logo:
        logo_url = company.logo.url
        if request is not None:
            logo_url = request.build_absolute_uri(logo_url)
    return {
        "display_name": company.display_name or company.name,
        "logo_url": logo_url,
        "primary_color": safe_hex_color(company.primary_color, DEFAULT_PRIMARY),
        "secondary_color": safe_hex_color(company.secondary_color, DEFAULT_SECONDARY),
        "theme_mode": company.theme_mode,
        "booking_url": booking_url(company),
    }
