from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record_event
from apps.inventory.models import InventoryMovement
from apps.inventory.services import record_movement

from .models import CashSession, Expense, PaymentRecord, Sale, SaleLine


class SalesError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "La operación comercial no es válida."
    default_code = "sales_conflict"


class InvalidSaleState(SalesError):
    default_detail = "La venta no permite esta acción en su estado actual."
    default_code = "invalid_sale_state"


class InvalidCashState(SalesError):
    default_detail = "La caja no permite esta acción en su estado actual."
    default_code = "invalid_cash_state"


def _decimal(value):
    return Decimal(str(value))


def _ensure_company(value, company, field):
    if value is None or value.company_id != company.id:
        raise ValidationError({field: "El recurso debe pertenecer a la empresa activa."})
    return value


def _validate_branch(branch, company):
    _ensure_company(branch, company, "branch")
    if not branch.active:
        raise ValidationError({"branch": "La sucursal está inactiva."})
    return branch


def _normalize_sale_lines(lines, company):
    if not lines:
        raise ValidationError({"lines": "Agrega al menos una línea."})
    seen, normalized = set(), []
    for raw in lines:
        product, service = raw.get("product"), raw.get("service")
        if (product is None) == (service is None):
            raise ValidationError({"lines": "Cada línea debe tener un producto o un servicio, no ambos."})
        quantity = _decimal(raw["quantity"])
        if quantity <= 0:
            raise ValidationError({"lines": "Las cantidades deben ser mayores que cero."})

        if product is not None:
            _ensure_company(product, company, "product")
            if not product.active:
                raise ValidationError({"lines": f"El producto {product.sku} está inactivo."})
            if product.kind != "stock":
                raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
            key = ("product", product.pk)
            price = raw.get("unit_price")
            price = product.price if price is None else _decimal(price)
            entry = {
                "kind": SaleLine.Kind.PRODUCT, "product": product, "service": None,
                "description": product.name, "sku": product.sku,
            }
        else:
            _ensure_company(service, company, "service")
            if not service.active:
                raise ValidationError({"lines": f"El servicio {service.name} está inactivo."})
            key = ("service", service.pk)
            price = raw.get("unit_price")
            price = service.price if price is None else _decimal(price)
            entry = {
                "kind": SaleLine.Kind.SERVICE, "product": None, "service": service,
                "description": service.name, "sku": "",
            }

        if price < 0:
            raise ValidationError({"lines": "Los precios no pueden ser negativos."})
        if key in seen:
            raise ValidationError({"lines": "No repitas productos o servicios en las líneas."})
        seen.add(key)
        entry.update({"quantity": quantity, "unit_price": price})
        normalized.append(entry)
    return normalized


def _subtotal_of(lines):
    return sum((
        (line["quantity"] * line["unit_price"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        for line in lines
    ), Decimal("0"))


def _validate_discount(discount, subtotal):
    discount = _decimal(discount or 0)
    if discount < 0:
        raise ValidationError({"discount": "El descuento no puede ser negativo."})
    if discount > subtotal:
        raise ValidationError({"discount": "El descuento no puede superar el subtotal."})
    return discount


def create_sale(*, company, branch, lines, customer=None, warehouse=None, discount=0,
                notes="", actor=None):
    _validate_branch(branch, company)
    if customer is not None:
        _ensure_company(customer, company, "customer")
        if not customer.active:
            raise ValidationError({"customer": "El cliente está inactivo."})
    normalized = _normalize_sale_lines(lines, company)
    has_products = any(line["kind"] == SaleLine.Kind.PRODUCT for line in normalized)
    if has_products:
        if warehouse is None:
            raise ValidationError({"warehouse": "Selecciona una bodega para vender productos."})
        _ensure_company(warehouse, company, "warehouse")
        if not warehouse.active:
            raise ValidationError({"warehouse": "La bodega está inactiva."})
    elif warehouse is not None:
        _ensure_company(warehouse, company, "warehouse")
        if not warehouse.active:
            raise ValidationError({"warehouse": "La bodega está inactiva."})

    discount = _validate_discount(discount, _subtotal_of(normalized))
    with transaction.atomic():
        sale = Sale.objects.create(
            company=company, branch=branch, customer=customer, warehouse=warehouse,
            discount=discount, notes=notes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        SaleLine.objects.bulk_create([
            SaleLine(company=company, sale=sale, **line) for line in normalized
        ])
        record_event(company=company, actor=actor, action="sale.created", instance=sale,
                     metadata={"lines": len(normalized), "total": str(sale.total)})
    return sale


def update_sale(*, sale, actor=None, **changes):
    with transaction.atomic():
        current = (Sale.objects.select_for_update()
                   .select_related("customer", "warehouse", "branch").get(pk=sale.pk))
        if current.status != Sale.Status.DRAFT:
            raise InvalidSaleState("Solo se puede editar una venta en borrador.")
        if "lines" in changes:
            raise ValidationError({"lines": "Anula la venta y crea una nueva para cambiar las líneas."})

        customer = changes.get("customer", current.customer)
        warehouse = changes.get("warehouse", current.warehouse)
        if customer is not None:
            _ensure_company(customer, current.company, "customer")
            if not customer.active:
                raise ValidationError({"customer": "El cliente está inactivo."})
        if warehouse is not None:
            _ensure_company(warehouse, current.company, "warehouse")
            if not warehouse.active:
                raise ValidationError({"warehouse": "La bodega está inactiva."})
        if current.lines.filter(kind=SaleLine.Kind.PRODUCT).exists() and warehouse is None:
            raise ValidationError({"warehouse": "Selecciona una bodega para vender productos."})

        discount = _validate_discount(changes.get("discount", current.discount), current.subtotal)
        current.customer = customer
        current.warehouse = warehouse
        current.discount = discount
        if "notes" in changes:
            current.notes = changes["notes"]
        current.save()
        record_event(company=current.company, actor=actor, action="sale.updated",
                     instance=current, metadata={"fields": sorted(changes)})
    return current


def _lock_open_session(session, company, branch):
    locked = (CashSession.objects.select_for_update()
              .select_related("branch").get(pk=session.pk))
    if locked.company_id != company.id:
        raise ValidationError({"cash_session": "La caja debe pertenecer a la empresa activa."})
    if locked.branch_id != branch.id:
        raise ValidationError({"cash_session": "La caja debe pertenecer a la sucursal de la venta."})
    if locked.status != CashSession.Status.OPEN:
        raise InvalidCashState("La caja está cerrada; no admite nuevos pagos en efectivo.")
    return locked


def _normalize_payments(payments, *, company, branch, total):
    normalized = []
    for raw in payments:
        method = raw.get("method")
        if method not in PaymentRecord.Method.values:
            raise ValidationError({"payments": "Método de pago inválido."})
        amount = _decimal(raw["amount"])
        if amount <= 0:
            raise ValidationError({"payments": "Los montos deben ser mayores que cero."})
        session = raw.get("cash_session")
        if method == PaymentRecord.Method.CASH:
            if session is None:
                raise ValidationError({"payments": "Un pago en efectivo requiere una caja abierta."})
            session = _lock_open_session(session, company, branch)
        elif session is not None:
            _ensure_company(session, company, "cash_session")
            if session.branch_id != branch.id:
                raise ValidationError({"payments": "La caja debe pertenecer a la sucursal de la venta."})
        normalized.append({
            "method": method, "amount": amount, "cash_session": session,
            "reference": raw.get("reference", ""),
        })

    paid = sum((payment["amount"] for payment in normalized), Decimal("0"))
    if paid != total:
        raise ValidationError({
            "payments": f"Los pagos suman {paid:.2f} y el total de la venta es {total:.2f}."
        })
    return normalized


def complete_sale(*, sale, payments, actor=None):
    with transaction.atomic():
        current = (Sale.objects.select_for_update()
                   .select_related("company", "branch", "warehouse", "customer").get(pk=sale.pk))
        if current.status == Sale.Status.COMPLETED:
            return current
        if current.status != Sale.Status.DRAFT:
            raise InvalidSaleState("Solo se puede completar una venta en borrador.")

        lines = list(current.lines.select_related("product").order_by("product_id"))
        if not lines:
            raise SalesError("La venta no tiene líneas.")
        total = current.total
        if total < 0:
            raise SalesError("El total de la venta no puede ser negativo.")

        normalized_payments = _normalize_payments(
            payments, company=current.company, branch=current.branch, total=total,
        )

        product_lines = [line for line in lines if line.kind == SaleLine.Kind.PRODUCT]
        if product_lines:
            if current.warehouse is None:
                raise ValidationError({"warehouse": "Selecciona una bodega para vender productos."})
            if not current.warehouse.active:
                raise InvalidSaleState("La bodega de la venta está inactiva.")
            for line in product_lines:
                movement = record_movement(
                    company=current.company, warehouse=current.warehouse,
                    product=line.product, kind=InventoryMovement.Kind.SALE,
                    direction=InventoryMovement.Direction.OUT, quantity=line.quantity,
                    reference_type="sale", reference_id=current.id,
                    note=f"Venta {current.number}", actor=actor,
                )
                line.unit_cost = movement.unit_cost
                line.save(update_fields=["unit_cost", "updated_at"])

        for payment in normalized_payments:
            PaymentRecord.objects.create(
                company=current.company, sale=current,
                cash_session=payment["cash_session"], method=payment["method"],
                amount=payment["amount"], reference=payment["reference"],
                created_by=actor if getattr(actor, "is_authenticated", False) else None,
            )

        current.status = Sale.Status.COMPLETED
        current.completed_at = timezone.now()
        current.save(update_fields=["status", "completed_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="sale.completed",
                     instance=current, metadata={
                         "total": str(total),
                         "payments": len(normalized_payments),
                         "lines": len(lines),
                     })
    return current


def cancel_sale(*, sale, actor=None, reason=""):
    with transaction.atomic():
        current = (Sale.objects.select_for_update()
                   .select_related("company", "branch", "warehouse").get(pk=sale.pk))
        if current.status == Sale.Status.CANCELED:
            return current

        if current.status == Sale.Status.COMPLETED:
            payments = list(current.payments.select_related("cash_session"))
            for payment in payments:
                session = payment.cash_session
                if (payment.method == PaymentRecord.Method.CASH and session is not None
                        and session.status == CashSession.Status.CLOSED):
                    raise InvalidCashState(
                        "No se puede anular una venta con efectivo de una caja ya cerrada."
                    )

            product_lines = list(
                current.lines.select_related("product")
                .filter(kind=SaleLine.Kind.PRODUCT).order_by("product_id")
            )
            if product_lines and current.warehouse is None:
                raise SalesError("La venta no tiene bodega para restaurar el stock.")
            for line in product_lines:
                record_movement(
                    company=current.company, warehouse=current.warehouse,
                    product=line.product, kind=InventoryMovement.Kind.SALE_CANCEL,
                    direction=InventoryMovement.Direction.IN, quantity=line.quantity,
                    unit_cost=line.unit_cost, reference_type="sale", reference_id=current.id,
                    note=f"Anulación {current.number}", actor=actor,
                )
            for payment in payments:
                if payment.status == PaymentRecord.Status.COMPLETED:
                    payment.status = PaymentRecord.Status.REFUNDED
                    payment.refunded_at = timezone.now()
                    payment.save(update_fields=["status", "refunded_at", "updated_at"])

        current.status = Sale.Status.CANCELED
        current.canceled_at = timezone.now()
        current.canceled_reason = reason[:240]
        current.save(update_fields=["status", "canceled_at", "canceled_reason", "updated_at"])
        record_event(company=current.company, actor=actor, action="sale.canceled",
                     instance=current, metadata={"reason": reason})
    return current


def open_cash_session(*, company, branch, opening_amount, notes="", actor=None):
    _validate_branch(branch, company)
    opening_amount = _decimal(opening_amount)
    if opening_amount < 0:
        raise ValidationError({"opening_amount": "El monto inicial no puede ser negativo."})
    try:
        with transaction.atomic():
            cash_session = CashSession.objects.create(
                company=company, branch=branch, opening_amount=opening_amount, notes=notes,
                opened_by=actor if getattr(actor, "is_authenticated", False) else None,
            )
            record_event(company=company, actor=actor, action="cash_session.opened",
                         instance=cash_session, metadata={"opening_amount": str(opening_amount)})
    except IntegrityError as error:
        raise InvalidCashState("Ya existe una caja abierta para esta sucursal.") from error
    return cash_session


def close_cash_session(*, cash_session, closing_amount, closing_notes="", actor=None):
    with transaction.atomic():
        current = (CashSession.objects.select_for_update()
                   .select_related("company", "branch").get(pk=cash_session.pk))
        if current.status == CashSession.Status.CLOSED:
            return current
        closing_amount = _decimal(closing_amount)
        if closing_amount < 0:
            raise ValidationError({"closing_amount": "El monto contado no puede ser negativo."})

        expected = current.expected_cash
        current.closing_amount = closing_amount
        current.expected_amount = expected
        current.difference = closing_amount - expected
        current.closing_notes = closing_notes
        current.status = CashSession.Status.CLOSED
        current.closed_at = timezone.now()
        current.closed_by = actor if getattr(actor, "is_authenticated", False) else None
        current.save(update_fields=[
            "closing_amount", "expected_amount", "difference", "closing_notes",
            "status", "closed_at", "closed_by", "updated_at",
        ])
        record_event(company=current.company, actor=actor, action="cash_session.closed",
                     instance=current, metadata={
                         "expected": str(expected), "counted": str(closing_amount),
                         "difference": str(current.difference),
                     })
    return current


def create_expense(*, company, branch, category, amount, method, cash_session=None,
                   description="", reference="", incurred_at=None, actor=None):
    _validate_branch(branch, company)
    amount = _decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": "El monto debe ser mayor que cero."})
    if method not in Expense.Method.values:
        raise ValidationError({"method": "Método de pago inválido."})

    with transaction.atomic():
        if method == Expense.Method.CASH:
            if cash_session is None:
                raise ValidationError({"cash_session": "Un gasto en efectivo requiere una caja abierta."})
            cash_session = _lock_open_session(cash_session, company, branch)
        elif cash_session is not None:
            _ensure_company(cash_session, company, "cash_session")
            if cash_session.branch_id != branch.id:
                raise ValidationError({"cash_session": "La caja debe pertenecer a la sucursal del gasto."})

        expense = Expense.objects.create(
            company=company, branch=branch, cash_session=cash_session, category=category,
            description=description, amount=amount, method=method, reference=reference,
            incurred_at=incurred_at or timezone.now(),
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        record_event(company=company, actor=actor, action="expense.created", instance=expense,
                     metadata={"amount": str(amount), "method": method})
    return expense


def cancel_expense(*, expense, actor=None, reason=""):
    with transaction.atomic():
        current = (Expense.objects.select_for_update()
                   .select_related("cash_session", "company").get(pk=expense.pk))
        if current.status == Expense.Status.CANCELED:
            return current
        if (current.method == Expense.Method.CASH and current.cash_session is not None
                and current.cash_session.status == CashSession.Status.CLOSED):
            raise InvalidCashState(
                "No se puede anular un gasto en efectivo de una caja ya cerrada."
            )
        current.status = Expense.Status.CANCELED
        current.canceled_at = timezone.now()
        current.canceled_reason = reason[:240]
        current.save(update_fields=["status", "canceled_at", "canceled_reason", "updated_at"])
        record_event(company=current.company, actor=actor, action="expense.canceled",
                     instance=current, metadata={"reason": reason})
    return current
