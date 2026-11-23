import json

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from rest_framework.exceptions import (
    APIException, NotFound, PermissionDenied, ValidationError,
)

from apps.billing.gating import enforce_tenant_billing
from apps.bookings.models import Booking
from apps.bookings.serializers import BookingCreateSerializer, BookingSerializer
from apps.bookings.services import (
    BookingConflict, create_booking, reschedule_booking, transition_booking,
)
from apps.audit.services import record_event
from apps.identity.models import Membership
from apps.inventory.models import Document, Product
from apps.inventory.serializers import (
    InventoryMovementSerializer, ManualMovementSerializer, ProductSerializer,
)
from apps.inventory.services import create_manual_movement
from apps.tenancy.permissions import has_tenant_permission

from .models import MobileOperation
from .serializers import (
    BookingCancelPayloadSerializer, BookingReschedulePayloadSerializer,
)

OPERATION_TYPES = {
    "booking.create", "booking.cancel", "booking.reschedule", "inventory.movement",
    "inventory.asset.create", "inventory.asset.update", "inventory.document.delete",
}


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def _error_payload(exc):
    detail = exc.detail if getattr(exc, "detail", None) is not None else str(exc)
    return {"detail": detail}


def _as_result(*, client_id, operation_type, outcome, http_status, data=None, error=None):
    result = {
        "client_id": str(client_id),
        "type": operation_type,
        "status": outcome,
        "http_status": http_status,
    }
    if data is not None:
        result["data"] = data
    if error is not None:
        result["error"] = error
    return result


def _booking_permission(membership):
    if membership.role == Membership.Role.WORKER:
        return "bookings.own.write"
    return "bookings.write"


def _ensure_permission(membership, permission, branch_id=None):
    if not has_tenant_permission(membership, permission, branch_id):
        raise PermissionDenied("No tienes permiso para ejecutar esta operación.")


def _load_booking(company, booking_id):
    try:
        return (Booking.objects.select_related("company", "branch", "worker")
                .get(pk=booking_id, company=company))
    except Booking.DoesNotExist:
        raise NotFound("La reserva no existe en la empresa activa.")


def _ensure_own_booking(membership, booking):
    if (membership.role == Membership.Role.WORKER
            and booking.worker.membership_id != membership.id):
        raise PermissionDenied("Solo puedes operar sobre tus propias reservas.")


def _stale(booking, expected_start_at):
    expected = expected_start_at
    if timezone.is_naive(expected):
        expected = timezone.make_aware(expected, timezone.get_current_timezone())
    return booking.start_at != expected


def _create_booking(*, company, membership, user, payload, request):
    serializer = BookingCreateSerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    branch = data["branch"]
    _ensure_permission(membership, _booking_permission(membership), branch.id)
    worker = data["worker"]
    if membership.role == Membership.Role.WORKER and worker.membership_id != membership.id:
        raise PermissionDenied("Solo puedes agendar tus propias reservas.")
    booking = create_booking(
        company=company, branch=branch, service=data["service"],
        worker=worker, customer=data["customer"], start_at=data["start_at"],
        actor=user, notes=data.get("notes", ""),
    )
    return BookingSerializer(booking).data


def _cancel_booking(*, company, membership, user, payload, request):
    serializer = BookingCancelPayloadSerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    booking = _load_booking(company, data["booking"])
    _ensure_own_booking(membership, booking)
    _ensure_permission(membership, _booking_permission(membership), booking.branch_id)
    booking = transition_booking(
        booking=booking, action="cancel", actor=user, reason=data.get("reason", ""),
    )
    return BookingSerializer(booking).data


def _reschedule_booking(*, company, membership, user, payload, request):
    serializer = BookingReschedulePayloadSerializer(
        data=payload, context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    booking = _load_booking(company, data["booking"])
    _ensure_own_booking(membership, booking)
    _ensure_permission(membership, _booking_permission(membership), booking.branch_id)
    if data.get("expected_start_at") and _stale(booking, data["expected_start_at"]):
        raise BookingConflict(
            "La reserva cambió desde la última sincronización; actualiza la agenda."
        )
    worker = data.get("worker")
    if membership.role == Membership.Role.WORKER and worker and worker.membership_id != membership.id:
        raise PermissionDenied("Solo puedes reprogramar tus propias reservas.")
    booking = reschedule_booking(
        booking=booking, start_at=data["start_at"], worker=worker,
        actor=user, reason=data.get("reason", ""),
    )
    return BookingSerializer(booking).data


def _inventory_movement(*, company, membership, user, payload, request):
    serializer = ManualMovementSerializer(data=payload, context={"request": request})
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    warehouse = data["warehouse"]
    _ensure_permission(membership, "inventory.write", warehouse.branch_id)
    movement = create_manual_movement(
        company=company, warehouse=warehouse, product=data["product"],
        kind=data["kind"], quantity=data["quantity"],
        unit_cost=data.get("unit_cost"), note=data.get("note", ""), actor=user,
    )
    return InventoryMovementSerializer(movement).data


def _asset_create(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    data = {key: value for key, value in payload.items() if key != "company"}
    data["kind"] = Product.Kind.ASSET
    serializer = ProductSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    product = serializer.save(company=company)
    record_event(
        company=company, actor=user, action="inventory.asset.created",
        instance=product, metadata={"sku": product.sku},
    )
    return ProductSerializer(product).data


def _asset_update(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    product = Product.objects.filter(
        company=company, pk=payload.get("product"), kind=Product.Kind.ASSET,
    ).first()
    if product is None:
        raise NotFound("El objeto no existe en la empresa activa.")
    data = {
        key: value for key, value in payload.items()
        if key not in {"company", "product"}
    }
    serializer = ProductSerializer(
        product, data=data, partial=True, context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    product = serializer.save()
    record_event(
        company=company, actor=user, action="inventory.asset.updated",
        instance=product, metadata={"sku": product.sku},
    )
    return ProductSerializer(product).data


def _document_delete(*, company, membership, user, payload, request):
    _ensure_permission(membership, "inventory.write")
    document = Document.objects.filter(
        company=company, pk=payload.get("document"),
    ).first()
    if document is None:
        raise NotFound("El documento no existe en la empresa activa.")
    record_event(
        company=company, actor=user, action="inventory.document.deleted",
        instance=document, metadata={"name": document.name},
    )
    document.file.delete(save=False)
    document.delete()
    return {"deleted": True}


HANDLERS = {
    "booking.create": _create_booking,
    "booking.cancel": _cancel_booking,
    "booking.reschedule": _reschedule_booking,
    "inventory.movement": _inventory_movement,
    "inventory.asset.create": _asset_create,
    "inventory.asset.update": _asset_update,
    "inventory.document.delete": _document_delete,
}


def _replay(existing):
    stored = existing.response or {}
    return _as_result(
        client_id=existing.client_id, operation_type=existing.operation,
        outcome=existing.status, http_status=stored.get("http_status", 200),
        data=stored.get("data"), error=stored.get("error"),
    )


def _persist(*, company, user, client_id, operation_type, payload, result):
    record = MobileOperation.objects.create(
        company=company, client_id=client_id, operation=operation_type,
        status=result["status"], request=_json_safe(payload),
        response=_json_safe({
            key: result[key] for key in ("http_status", "data", "error") if key in result
        }),
        created_by=user,
    )
    return record


def execute_operation(*, company, membership, user, operation_type, payload, request):
    if operation_type not in OPERATION_TYPES:
        return _as_result(
            client_id=None, operation_type=operation_type, outcome="rejected",
            http_status=400, error={"detail": "Tipo de operación desconocido."},
        )
    handler = HANDLERS[operation_type]
    try:
        enforce_tenant_billing_operation(company, membership, operation_type)
        data = handler(
            company=company, membership=membership, user=user,
            payload=payload, request=request,
        )
        return _as_result(
            client_id=None, operation_type=operation_type, outcome="applied",
            http_status=200, data=data,
        )
    except APIException as exc:
        outcome = "conflict" if exc.status_code == 409 else "rejected"
        return _as_result(
            client_id=None, operation_type=operation_type, outcome=outcome,
            http_status=exc.status_code, error=_error_payload(exc),
        )


def enforce_tenant_billing_operation(company, membership, operation_type):
    permission = (
        "inventory.write" if operation_type.startswith("inventory.")
        else _booking_permission(membership)
    )
    enforce_tenant_billing(company, permission)


def process_operations(*, company, membership, user, operations, request):
    results = []
    for raw in operations:
        client_id = raw["client_id"]
        operation_type = raw["type"]
        payload = raw["payload"]
        existing = MobileOperation.objects.filter(
            company=company, client_id=client_id,
        ).first()
        if existing is not None:
            if existing.operation != operation_type:
                result = _as_result(
                    client_id=client_id, operation_type=operation_type,
                    outcome="rejected", http_status=409,
                    error={"detail": "client_id ya fue usado por otra operación."},
                )
            else:
                result = _replay(existing)
            result["client_id"] = str(client_id)
            results.append(result)
            continue

        result = execute_operation(
            company=company, membership=membership, user=user,
            operation_type=operation_type, payload=payload, request=request,
        )
        result["client_id"] = str(client_id)
        if operation_type in OPERATION_TYPES:
            _persist(
                company=company, user=user, client_id=client_id,
                operation_type=operation_type, payload=payload, result=result,
            )
        results.append(result)
    return results
