import json
import logging
import urllib.request
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tenancy.permissions import has_tenant_permission

from .models import DeviceInstallation, PushMessage

logger = logging.getLogger(__name__)

BOOKING_TITLES = {
    PushMessage.Kind.BOOKING_CREATED: "Nueva reserva",
    PushMessage.Kind.BOOKING_CONFIRMED: "Reserva confirmada",
    PushMessage.Kind.BOOKING_RESCHEDULED: "Reserva reprogramada",
    PushMessage.Kind.BOOKING_CANCELED: "Reserva cancelada",
}


def enqueue_push(*, company, user, kind, title, body="", data=None):
    message = PushMessage.objects.create(
        company=company, user=user, kind=kind, title=title[:160], body=body,
        data=data or {},
    )
    transaction.on_commit(lambda: deliver_push(message.pk))
    return message


def active_tokens(company, user):
    return list(
        DeviceInstallation.objects
        .filter(company=company, user=user, active=True)
        .exclude(push_token="")
        .values_list("push_token", flat=True)
    )


def _send(message, tokens):
    provider = getattr(settings, "MOBILE_PUSH_PROVIDER", "console")
    if provider == "console":
        logger.info("push console %s -> %s: %s", message.user_id, tokens, message.title)
        return provider, None
    url = getattr(settings, "MOBILE_PUSH_WEBHOOK_URL", "")
    if not url:
        return provider, "AGENDA_PUSH_WEBHOOK_URL no está configurada."
    payload = {
        "tokens": tokens,
        "notification": {"title": message.title, "body": message.body},
        "data": message.data,
    }
    headers = {"Content-Type": "application/json"}
    token = getattr(settings, "MOBILE_PUSH_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if 200 <= response.status < 300:
                return provider, None
            return provider, f"HTTP {response.status}"
    except Exception as exc:  # provider outage must not break the request flow
        return provider, str(exc)[:500]


def deliver_push(message_id):
    message = PushMessage.objects.filter(pk=message_id, status=PushMessage.Status.PENDING).first()
    if message is None:
        return
    tokens = active_tokens(message.company_id, message.user_id)
    if not tokens:
        message.status = PushMessage.Status.SKIPPED
        message.error = "Sin dispositivos activos con token."
        message.save(update_fields=["status", "error", "updated_at"])
        return
    provider, error = _send(message, tokens)
    message.provider = provider
    if error is None:
        message.status = PushMessage.Status.SENT
        message.sent_at = timezone.now()
    else:
        message.status = PushMessage.Status.FAILED
        message.error = error
    message.save(update_fields=["status", "provider", "error", "sent_at", "updated_at"])


def _local_range(booking):
    tz = ZoneInfo(booking.branch.timezone or settings.TIME_ZONE)
    start = booking.start_at.astimezone(tz)
    end = booking.end_at.astimezone(tz)
    return f"{start:%d-%m-%Y %H:%M} a {end:%H:%M}"


def push_booking_event(booking, kind):
    recipients = []
    membership = getattr(booking.worker, "membership", None)
    if membership is not None and membership.active:
        recipients.append(membership.user)
    if booking.created_by_id:
        recipients.append(booking.created_by)
    seen = set()
    title = f"{BOOKING_TITLES.get(kind, 'Reserva')} · {booking.service_name}"
    body = (
        f"{booking.customer} · {_local_range(booking)} · "
        f"{booking.worker} ({booking.branch.name})"
    )
    data = {
        "type": kind,
        "booking_id": str(booking.id),
        "public_code": booking.public_code,
        "status": booking.status,
        "start_at": booking.start_at.isoformat(),
        "worker_id": str(booking.worker_id),
    }
    for user in recipients:
        if user.id in seen:
            continue
        seen.add(user.id)
        enqueue_push(
            company=booking.company, user=user, kind=kind,
            title=title, body=body, data=data,
        )


def push_low_stock_event(movement):
    product = movement.product
    if not product.reorder_point or movement.balance_after > product.reorder_point:
        return
    recipients = (
        movement.company.memberships
        .filter(active=True)
        .select_related("user")
        .order_by("user_id")
    )
    data = {
        "type": PushMessage.Kind.LOW_STOCK,
        "product_id": str(product.id),
        "warehouse_id": str(movement.warehouse_id),
        "balance": str(movement.balance_after),
        "reorder_point": str(product.reorder_point),
    }
    title = f"Stock bajo · {product.name}"
    body = (
        f"{product.sku} quedó en {movement.balance_after} unidades en "
        f"{movement.warehouse.name} (mínimo {product.reorder_point})."
    )
    for membership in recipients:
        if not has_tenant_permission(membership, "inventory.write"):
            continue
        enqueue_push(
            company=movement.company, user=membership.user,
            kind=PushMessage.Kind.LOW_STOCK, title=title, body=body, data=data,
        )
