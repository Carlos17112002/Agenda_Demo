from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record_event

from .models import (
    InventoryMovement, Product, PurchaseLine, PurchaseOrder, StockBalance, Stocktake,
    StocktakeLine, Supplier, Transfer, TransferLine, Warehouse,
)


class InventoryError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "La operación de inventario no es válida."
    default_code = "inventory_conflict"


class InsufficientStock(InventoryError):
    default_detail = "No hay stock suficiente para completar la operación."
    default_code = "insufficient_stock"


class InvalidInventoryState(InventoryError):
    default_detail = "El documento no permite esta acción en su estado actual."
    default_code = "invalid_inventory_state"


def ensure_company(value, company, field):
    if value is None or value.company_id != company.id:
        raise ValidationError({field: "El recurso debe pertenecer a la empresa activa."})
    return value


def _decimal(value):
    return Decimal(str(value))


def _locked_balance(company, warehouse, product):
    balance, _ = StockBalance.objects.get_or_create(
        company=company, warehouse=warehouse, product=product,
        defaults={"quantity": Decimal("0"), "average_cost": Decimal("0")},
    )
    return StockBalance.objects.select_for_update().get(pk=balance.pk)


def record_movement(*, company, warehouse, product, kind, direction, quantity, unit_cost=None,
                    reference_type="", reference_id="", note="", actor=None):
    """Apply one ledger entry and update the weighted-average balance atomically."""
    if kind not in InventoryMovement.Kind.values:
        raise ValidationError({"kind": "Tipo de movimiento inválido."})
    if direction not in InventoryMovement.Direction.values:
        raise ValidationError({"direction": "Dirección de movimiento inválida."})
    quantity = _decimal(quantity)
    if quantity <= 0:
        raise ValidationError({"quantity": "La cantidad debe ser mayor que cero."})
    ensure_company(warehouse, company, "warehouse")
    ensure_company(product, company, "product")
    if product.kind != Product.Kind.STOCK:
        raise ValidationError({"product": "Los objetos no manejan stock."})

    with transaction.atomic():
        balance = _locked_balance(company, warehouse, product)
        if direction == InventoryMovement.Direction.IN:
            incoming_cost = _decimal(unit_cost) if unit_cost is not None else (balance.average_cost or product.cost)
            if incoming_cost < 0:
                raise ValidationError({"unit_cost": "El costo no puede ser negativo."})
            new_quantity = balance.quantity + quantity
            weighted = (balance.quantity * balance.average_cost) + (quantity * incoming_cost)
            new_average = (weighted / new_quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            movement_cost = incoming_cost.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        else:
            if balance.quantity < quantity:
                raise InsufficientStock(
                    f"No hay stock suficiente de {product.name} en {warehouse.name}."
                )
            new_quantity = balance.quantity - quantity
            new_average = balance.average_cost
            movement_cost = balance.average_cost

        balance.quantity = new_quantity
        balance.average_cost = new_average
        balance.save(update_fields=["quantity", "average_cost", "updated_at"])

        movement = InventoryMovement.objects.create(
            company=company, warehouse=warehouse, product=product, kind=kind,
            direction=direction, quantity=quantity, unit_cost=movement_cost,
            balance_after=new_quantity, reference_type=reference_type,
            reference_id=str(reference_id or ""), note=note[:240],
            actor=actor if getattr(actor, "is_authenticated", False) else None,
        )
    return movement


def create_manual_movement(*, company, warehouse, product, kind, quantity, unit_cost=None,
                           note="", actor=None):
    if kind not in {InventoryMovement.Kind.ENTRY, InventoryMovement.Kind.EXIT}:
        raise ValidationError({"kind": "Solo se admiten ingresos o salidas manuales."})
    ensure_company(warehouse, company, "warehouse")
    ensure_company(product, company, "product")
    if not warehouse.active:
        raise ValidationError({"warehouse": "La bodega está inactiva."})
    if not product.active:
        raise ValidationError({"product": "El producto está inactivo."})
    direction = (InventoryMovement.Direction.IN if kind == InventoryMovement.Kind.ENTRY
                 else InventoryMovement.Direction.OUT)
    with transaction.atomic():
        movement = record_movement(
            company=company, warehouse=warehouse, product=product, kind=kind,
            direction=direction, quantity=quantity, unit_cost=unit_cost,
            reference_type="manual", note=note, actor=actor,
        )
        record_event(
            company=company, actor=actor, action=f"inventory.{kind}", instance=movement,
            metadata={"warehouse_id": str(warehouse.id), "product_id": str(product.id),
                      "quantity": str(movement.quantity), "direction": direction},
        )
    return movement


def _normalize_purchase_lines(lines, company):
    if not lines:
        raise ValidationError({"lines": "Agrega al menos una línea."})
    seen, normalized = set(), []
    for raw in lines:
        product = ensure_company(raw["product"], company, "product")
        if not product.active:
            raise ValidationError({"lines": f"El producto {product.sku} está inactivo."})
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
        quantity = _decimal(raw["quantity"])
        unit_cost = _decimal(raw.get("unit_cost", 0))
        if quantity <= 0:
            raise ValidationError({"lines": "Las cantidades deben ser mayores que cero."})
        if unit_cost < 0:
            raise ValidationError({"lines": "Los costos no pueden ser negativos."})
        if product.pk in seen:
            raise ValidationError({"lines": "No repitas productos en las líneas."})
        seen.add(product.pk)
        normalized.append({"product": product, "quantity": quantity, "unit_cost": unit_cost})
    return normalized


def create_purchase_order(*, company, supplier, warehouse, lines, expected_at=None,
                          notes="", actor=None):
    ensure_company(supplier, company, "supplier")
    ensure_company(warehouse, company, "warehouse")
    if not supplier.active:
        raise ValidationError({"supplier": "El proveedor está inactivo."})
    if not warehouse.active:
        raise ValidationError({"warehouse": "La bodega está inactiva."})
    normalized = _normalize_purchase_lines(lines, company)
    total = sum((line["quantity"] * line["unit_cost"] for line in normalized), Decimal("0"))

    with transaction.atomic():
        order = PurchaseOrder.objects.create(
            company=company, supplier=supplier, warehouse=warehouse,
            expected_at=expected_at, notes=notes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        PurchaseLine.objects.bulk_create([
            PurchaseLine(company=company, purchase=order, **line) for line in normalized
        ])
        record_event(company=company, actor=actor, action="purchase_order.created", instance=order,
                     metadata={"lines": len(normalized), "total": str(total)})
    return order


def update_purchase_order(*, order, actor=None, **changes):
    with transaction.atomic():
        current = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if current.status != PurchaseOrder.Status.DRAFT:
            raise InvalidInventoryState("Solo se puede editar una orden en borrador.")
        supplier = changes.get("supplier", current.supplier)
        warehouse = changes.get("warehouse", current.warehouse)
        ensure_company(supplier, current.company, "supplier")
        ensure_company(warehouse, current.company, "warehouse")
        if not supplier.active:
            raise ValidationError({"supplier": "El proveedor está inactivo."})
        if not warehouse.active:
            raise ValidationError({"warehouse": "La bodega está inactiva."})
        for field in ("supplier", "warehouse", "expected_at", "notes"):
            if field in changes:
                setattr(current, field, changes[field])
        current.save()
        record_event(company=current.company, actor=actor, action="purchase_order.updated",
                     instance=current, metadata={"fields": sorted(changes)})
    return current


def submit_purchase_order(*, order, actor=None):
    with transaction.atomic():
        current = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if current.status == PurchaseOrder.Status.ORDERED:
            return current
        if current.status != PurchaseOrder.Status.DRAFT:
            raise InvalidInventoryState("Solo se puede pedir una orden en borrador.")
        if not current.lines.exists():
            raise InventoryError("La orden no tiene líneas.")
        current.status = PurchaseOrder.Status.ORDERED
        current.ordered_at = timezone.now()
        current.save(update_fields=["status", "ordered_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="purchase_order.submitted", instance=current)
    return current


def receive_purchase_order(*, order, actor=None):
    with transaction.atomic():
        current = (PurchaseOrder.objects.select_for_update()
                   .select_related("company", "supplier", "warehouse").get(pk=order.pk))
        if current.status == PurchaseOrder.Status.RECEIVED:
            return current
        if current.status != PurchaseOrder.Status.ORDERED:
            raise InvalidInventoryState("Solo se puede recibir una orden pedida.")
        lines = list(current.lines.select_related("product").order_by("product_id"))
        if not lines:
            raise InventoryError("La orden no tiene líneas.")
        for line in lines:
            record_movement(
                company=current.company, warehouse=current.warehouse, product=line.product,
                kind=InventoryMovement.Kind.PURCHASE_RECEIPT,
                direction=InventoryMovement.Direction.IN, quantity=line.quantity,
                unit_cost=line.unit_cost, reference_type="purchase_order",
                reference_id=current.id, note=f"Recepción {current.number}", actor=actor,
            )
            if line.product.cost != line.unit_cost:
                line.product.cost = line.unit_cost
                line.product.save(update_fields=["cost", "updated_at"])
        current.status = PurchaseOrder.Status.RECEIVED
        current.received_at = timezone.now()
        current.save(update_fields=["status", "received_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="purchase_order.received",
                     instance=current, metadata={"total": str(current.total)})
    return current


def cancel_purchase_order(*, order, actor=None, reason=""):
    with transaction.atomic():
        current = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if current.status == PurchaseOrder.Status.CANCELED:
            return current
        if current.status == PurchaseOrder.Status.RECEIVED:
            raise InvalidInventoryState("Una orden recibida no se cancela; registra una devolución.")
        current.status = PurchaseOrder.Status.CANCELED
        current.canceled_at = timezone.now()
        current.save(update_fields=["status", "canceled_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="purchase_order.canceled",
                     instance=current, metadata={"reason": reason})
    return current


def _normalize_transfer_lines(lines, company):
    if not lines:
        raise ValidationError({"lines": "Agrega al menos una línea."})
    seen, normalized = set(), []
    for raw in lines:
        product = ensure_company(raw["product"], company, "product")
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
        quantity = _decimal(raw["quantity"])
        if quantity <= 0:
            raise ValidationError({"lines": "Las cantidades deben ser mayores que cero."})
        if product.pk in seen:
            raise ValidationError({"lines": "No repitas productos en las líneas."})
        seen.add(product.pk)
        normalized.append({"product": product, "quantity": quantity})
    return normalized


def create_transfer(*, company, from_warehouse, to_warehouse, lines, notes="", actor=None):
    ensure_company(from_warehouse, company, "from_warehouse")
    ensure_company(to_warehouse, company, "to_warehouse")
    if from_warehouse.pk == to_warehouse.pk:
        raise ValidationError({"to_warehouse": "La bodega de destino debe ser distinta del origen."})
    if not from_warehouse.active or not to_warehouse.active:
        raise ValidationError({"warehouse": "Las bodegas deben estar activas."})
    normalized = _normalize_transfer_lines(lines, company)

    with transaction.atomic():
        transfer = Transfer.objects.create(
            company=company, from_warehouse=from_warehouse, to_warehouse=to_warehouse,
            notes=notes, created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        TransferLine.objects.bulk_create([
            TransferLine(company=company, transfer=transfer, **line) for line in normalized
        ])
        record_event(company=company, actor=actor, action="transfer.created", instance=transfer,
                     metadata={"lines": len(normalized)})
    return transfer


def dispatch_transfer(*, transfer, actor=None):
    with transaction.atomic():
        current = (Transfer.objects.select_for_update()
                   .select_related("company", "from_warehouse", "to_warehouse").get(pk=transfer.pk))
        if current.status == Transfer.Status.IN_TRANSIT:
            return current
        if current.status != Transfer.Status.DRAFT:
            raise InvalidInventoryState("Solo se puede despachar una transferencia en borrador.")
        if not current.from_warehouse.active or not current.to_warehouse.active:
            raise InvalidInventoryState("Las bodegas deben estar activas para despachar.")
        lines = list(current.lines.select_related("product").order_by("product_id"))
        if not lines:
            raise InventoryError("La transferencia no tiene líneas.")
        for line in lines:
            movement = record_movement(
                company=current.company, warehouse=current.from_warehouse, product=line.product,
                kind=InventoryMovement.Kind.TRANSFER_OUT,
                direction=InventoryMovement.Direction.OUT, quantity=line.quantity,
                reference_type="transfer", reference_id=current.id,
                note=f"Despacho {current.number}", actor=actor,
            )
            line.unit_cost = movement.unit_cost
            line.save(update_fields=["unit_cost", "updated_at"])
        current.status = Transfer.Status.IN_TRANSIT
        current.dispatched_at = timezone.now()
        current.save(update_fields=["status", "dispatched_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="transfer.dispatched", instance=current)
    return current


def complete_transfer(*, transfer, actor=None):
    with transaction.atomic():
        current = (Transfer.objects.select_for_update()
                   .select_related("company", "from_warehouse", "to_warehouse").get(pk=transfer.pk))
        if current.status == Transfer.Status.COMPLETED:
            return current
        if current.status != Transfer.Status.IN_TRANSIT:
            raise InvalidInventoryState("Solo se puede completar una transferencia en tránsito.")
        lines = list(current.lines.select_related("product").order_by("product_id"))
        for line in lines:
            record_movement(
                company=current.company, warehouse=current.to_warehouse, product=line.product,
                kind=InventoryMovement.Kind.TRANSFER_IN,
                direction=InventoryMovement.Direction.IN, quantity=line.quantity,
                unit_cost=line.unit_cost, reference_type="transfer", reference_id=current.id,
                note=f"Recepción {current.number}", actor=actor,
            )
        current.status = Transfer.Status.COMPLETED
        current.completed_at = timezone.now()
        current.save(update_fields=["status", "completed_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="transfer.completed", instance=current)
    return current


def cancel_transfer(*, transfer, actor=None, reason=""):
    with transaction.atomic():
        current = (Transfer.objects.select_for_update()
                   .select_related("company", "from_warehouse", "to_warehouse").get(pk=transfer.pk))
        if current.status == Transfer.Status.CANCELED:
            return current
        if current.status == Transfer.Status.COMPLETED:
            raise InvalidInventoryState("Una transferencia completada no se cancela.")
        if current.status == Transfer.Status.IN_TRANSIT:
            lines = list(current.lines.select_related("product").order_by("product_id"))
            for line in lines:
                record_movement(
                    company=current.company, warehouse=current.from_warehouse, product=line.product,
                    kind=InventoryMovement.Kind.TRANSFER_IN,
                    direction=InventoryMovement.Direction.IN, quantity=line.quantity,
                    unit_cost=line.unit_cost, reference_type="transfer", reference_id=current.id,
                    note=f"Devolución por cancelación {current.number}", actor=actor,
                )
        current.status = Transfer.Status.CANCELED
        current.canceled_at = timezone.now()
        current.save(update_fields=["status", "canceled_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="transfer.canceled",
                     instance=current, metadata={"reason": reason})
    return current


def _normalize_stocktake_lines(lines, company):
    if not lines:
        raise ValidationError({"lines": "Agrega al menos una línea."})
    seen, normalized = set(), []
    for raw in lines:
        product = ensure_company(raw["product"], company, "product")
        if product.kind != Product.Kind.STOCK:
            raise ValidationError({"lines": f"El objeto {product.sku} no maneja stock."})
        counted = _decimal(raw["counted_quantity"])
        if counted < 0:
            raise ValidationError({"lines": "Las cantidades contadas no pueden ser negativas."})
        if product.pk in seen:
            raise ValidationError({"lines": "No repitas productos en las líneas."})
        seen.add(product.pk)
        normalized.append({"product": product, "counted_quantity": counted})
    return normalized


def create_stocktake(*, company, warehouse, lines, notes="", actor=None):
    ensure_company(warehouse, company, "warehouse")
    if not warehouse.active:
        raise ValidationError({"warehouse": "La bodega está inactiva."})
    normalized = _normalize_stocktake_lines(lines, company)

    with transaction.atomic():
        stocktake = Stocktake.objects.create(
            company=company, warehouse=warehouse, notes=notes,
            created_by=actor if getattr(actor, "is_authenticated", False) else None,
        )
        StocktakeLine.objects.bulk_create([
            StocktakeLine(company=company, stocktake=stocktake, **line) for line in normalized
        ])
        record_event(company=company, actor=actor, action="stocktake.created", instance=stocktake,
                     metadata={"lines": len(normalized)})
    return stocktake


def complete_stocktake(*, stocktake, actor=None):
    with transaction.atomic():
        current = (Stocktake.objects.select_for_update()
                   .select_related("company", "warehouse").get(pk=stocktake.pk))
        if current.status == Stocktake.Status.COMPLETED:
            return current
        if current.status != Stocktake.Status.DRAFT:
            raise InvalidInventoryState("Solo se puede conciliar un conteo en borrador.")
        lines = list(current.lines.select_related("product").order_by("product_id"))
        if not lines:
            raise InventoryError("El conteo no tiene líneas.")
        adjustments = 0
        for line in lines:
            balance = _locked_balance(current.company, current.warehouse, line.product)
            expected = balance.quantity
            difference = line.counted_quantity - expected
            line.expected_quantity = expected
            line.difference = difference
            line.save(update_fields=["expected_quantity", "difference", "updated_at"])
            if difference == 0:
                continue
            adjustments += 1
            record_movement(
                company=current.company, warehouse=current.warehouse, product=line.product,
                kind=InventoryMovement.Kind.STOCKTAKE,
                direction=(InventoryMovement.Direction.IN if difference > 0
                           else InventoryMovement.Direction.OUT),
                quantity=abs(difference), unit_cost=balance.average_cost,
                reference_type="stocktake", reference_id=current.id,
                note=f"Conteo {current.number}", actor=actor,
            )
        current.status = Stocktake.Status.COMPLETED
        current.completed_at = timezone.now()
        current.save(update_fields=["status", "completed_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="stocktake.completed",
                     instance=current, metadata={"adjustments": adjustments})
    return current


def cancel_stocktake(*, stocktake, actor=None, reason=""):
    with transaction.atomic():
        current = Stocktake.objects.select_for_update().get(pk=stocktake.pk)
        if current.status == Stocktake.Status.CANCELED:
            return current
        if current.status == Stocktake.Status.COMPLETED:
            raise InvalidInventoryState("Un conteo conciliado no se cancela.")
        current.status = Stocktake.Status.CANCELED
        current.canceled_at = timezone.now()
        current.save(update_fields=["status", "canceled_at", "updated_at"])
        record_event(company=current.company, actor=actor, action="stocktake.canceled",
                     instance=current, metadata={"reason": reason})
    return current
