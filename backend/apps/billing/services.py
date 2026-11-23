from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from apps.audit.services import record_event
from apps.tenancy.models import Company

from .models import Invoice, Payment, Plan, Subscription, add_billing_period


class BillingError(APIException):
    status_code = 409
    default_detail = "No se pudo procesar la operación de facturación."
    default_code = "billing_error"


class InvalidPlan(BillingError):
    default_detail = "El plan no está disponible."
    default_code = "invalid_plan"


class SubscriptionConflict(BillingError):
    default_detail = "La empresa ya tiene una suscripción vigente."
    default_code = "subscription_conflict"


class InvalidSubscriptionState(BillingError):
    default_detail = "La suscripción no admite esta operación."
    default_code = "invalid_subscription_state"


def default_plan():
    return Plan.objects.filter(is_default=True, active=True).first()


def open_subscription(company, *, for_update=False):
    queryset = Subscription.objects.filter(company=company, ended_at__isnull=True)
    if for_update:
        queryset = queryset.select_for_update()
    return (queryset.select_related("plan").prefetch_related("plan__features").first())


def _money(value):
    return Decimal(value).quantize(Decimal("0.01"))


def _audit(action, subscription, actor, metadata=None):
    record_event(
        company=subscription.company, actor=actor, action=action,
        instance=subscription, metadata=metadata or {},
    )


@transaction.atomic
def start_subscription(company, plan, *, trial_days=None, actor=None, now=None):
    now = now or timezone.now()
    company = Company.objects.select_for_update().get(pk=company.pk)
    plan = Plan.objects.select_for_update().get(pk=plan.pk)
    if not plan.active:
        raise InvalidPlan("El plan seleccionado no está activo.")
    if open_subscription(company, for_update=True):
        raise SubscriptionConflict()
    days = plan.trial_days if trial_days is None else trial_days
    if days < 0:
        raise ValidationError({"trial_days": "El periodo de prueba no puede ser negativo."})
    trial = days > 0
    subscription = Subscription.objects.create(
        company=company,
        plan=plan,
        status=Subscription.Status.TRIALING if trial else Subscription.Status.ACTIVE,
        started_at=now,
        trial_ends_at=now + timedelta(days=days) if trial else None,
        current_period_start=None if trial else now,
        current_period_end=None if trial else add_billing_period(now, plan.billing_period),
    )
    if not trial and company.status == Company.Status.TRIAL:
        company.status = Company.Status.ACTIVE
        company.save(update_fields=["status", "updated_at"])
    _audit("subscription.started", subscription, actor, {
        "plan": plan.code, "trial_days": days,
    })
    return subscription


@transaction.atomic
def change_plan(subscription, plan, *, actor=None):
    subscription = (Subscription.objects.select_for_update()
                    .select_related("plan").prefetch_related("plan__features")
                    .get(pk=subscription.pk))
    if subscription.ended_at:
        raise InvalidSubscriptionState("La suscripción ya finalizó.")
    plan = Plan.objects.get(pk=plan.pk)
    if not plan.active:
        raise InvalidPlan("El plan seleccionado no está activo.")
    if subscription.plan_id == plan.pk:
        return subscription
    previous = subscription.plan
    subscription.plan = plan
    subscription.save(update_fields=["plan", "updated_at"])
    subscription.refresh_from_db()
    subscription = (Subscription.objects.select_related("plan")
                    .prefetch_related("plan__features").get(pk=subscription.pk))
    _audit("subscription.plan_changed", subscription, actor, {
        "previous_plan": previous.code, "new_plan": plan.code,
    })
    return subscription


@transaction.atomic
def cancel_subscription(subscription, *, immediate=False, actor=None):
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    if subscription.ended_at:
        return subscription
    now = timezone.now()
    subscription.canceled_at = now
    if immediate:
        subscription.status = Subscription.Status.CANCELED
        subscription.cancel_at_period_end = False
        subscription.ended_at = now
    else:
        subscription.cancel_at_period_end = True
    subscription.save(update_fields=[
        "status", "cancel_at_period_end", "canceled_at", "ended_at", "updated_at",
    ])
    _audit("subscription.canceled", subscription, actor, {"immediate": immediate})
    return subscription


@transaction.atomic
def resume_subscription(subscription, *, actor=None):
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    if subscription.ended_at:
        raise InvalidSubscriptionState("La suscripción ya finalizó.")
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    subscription.save(update_fields=["cancel_at_period_end", "canceled_at", "updated_at"])
    _audit("subscription.resumed", subscription, actor)
    return subscription


@transaction.atomic
def expire_subscription(subscription, *, actor=None):
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    if subscription.ended_at:
        return subscription
    subscription.status = Subscription.Status.EXPIRED
    subscription.ended_at = timezone.now()
    subscription.save(update_fields=["status", "ended_at", "updated_at"])
    _audit("subscription.expired", subscription, actor)
    return subscription


def _next_invoice_sequence(company):
    current = Invoice.objects.filter(company=company).aggregate(value=Max("sequence"))["value"] or 0
    return current + 1


@transaction.atomic
def record_payment(subscription, *, amount, method, reference="", actor=None,
                   paid_at=None, description=""):
    amount = _money(amount)
    if amount <= 0:
        raise ValidationError({"amount": "El pago debe ser mayor que cero."})
    company = Company.objects.select_for_update().get(pk=subscription.company_id)
    subscription = (Subscription.objects.select_for_update()
                    .select_related("plan").prefetch_related("plan__features")
                    .get(pk=subscription.pk))
    if subscription.ended_at:
        raise InvalidSubscriptionState("La suscripción ya finalizó.")
    if reference:
        existing = Payment.objects.filter(
            company=company, reference=reference, status=Payment.Status.COMPLETED,
        ).first()
        if existing:
            return existing

    now = paid_at or timezone.now()
    period_start = now
    if (subscription.status != Subscription.Status.TRIALING
            and subscription.current_period_end
            and subscription.current_period_end > now):
        period_start = subscription.current_period_end
    period_end = add_billing_period(period_start, subscription.plan.billing_period)

    sequence = _next_invoice_sequence(company)
    invoice = Invoice.objects.create(
        company=company,
        subscription=subscription,
        sequence=sequence,
        number=f"FAC-{sequence:06d}",
        description=description or f"Suscripción {subscription.plan.name}",
        subtotal=amount,
        tax=Decimal("0"),
        total=amount,
        currency=subscription.plan.currency,
        status=Invoice.Status.PAID,
        period_start=period_start,
        period_end=period_end,
        paid_at=now,
    )
    payment = Payment.objects.create(
        company=company,
        subscription=subscription,
        amount=amount,
        currency=subscription.plan.currency,
        method=method,
        reference=reference or "",
        paid_at=now,
        period_start=period_start,
        period_end=period_end,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    invoice.payment = payment
    invoice.save(update_fields=["payment"])

    subscription.status = Subscription.Status.ACTIVE
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    subscription.save(update_fields=[
        "status", "current_period_start", "current_period_end",
        "cancel_at_period_end", "canceled_at", "updated_at",
    ])
    if company.status == Company.Status.TRIAL:
        company.status = Company.Status.ACTIVE
        company.save(update_fields=["status", "updated_at"])
    _audit("subscription.payment_recorded", subscription, actor, {
        "amount": str(amount),
        "currency": subscription.plan.currency,
        "method": method,
        "reference": reference,
        "invoice": invoice.number,
    })
    return payment


def saas_summary(now=None):
    now = now or timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    companies = {
        row["status"]: row["count"]
        for row in Company.objects.values("status").annotate(count=Count("id"))
    }
    subscriptions = list(
        Subscription.objects.filter(ended_at__isnull=True).select_related("plan")
    )
    statuses = {choice: 0 for choice in Subscription.Status.values}
    trials_expiring = 0
    mrr_by_currency = {}
    for subscription in subscriptions:
        status = subscription.effective_status(now)
        statuses[status] = statuses.get(status, 0) + 1
        if status == Subscription.Status.ACTIVE:
            monthly = subscription.plan.price
            if subscription.plan.billing_period == Plan.BillingPeriod.YEARLY:
                monthly = monthly / 12
            mrr_by_currency[subscription.plan.currency] = (
                mrr_by_currency.get(subscription.plan.currency, Decimal("0")) + monthly
            )
        if (status == Subscription.Status.TRIALING and subscription.trial_ends_at
                and subscription.trial_ends_at <= now + timedelta(days=7)):
            trials_expiring += 1
    payments = Payment.objects.filter(
        status=Payment.Status.COMPLETED, paid_at__gte=month_start, paid_at__lte=now,
    )
    revenue_by_currency = [
        {"currency": row["currency"], "amount": str(_money(row["total"]))}
        for row in payments.values("currency").annotate(total=Sum("amount"))
    ]
    return {
        "generated_at": now.isoformat(),
        "companies_by_status": companies,
        "total_companies": sum(companies.values()),
        "subscriptions_by_effective_status": statuses,
        "open_subscriptions": len(subscriptions),
        "trials_expiring_in_7_days": trials_expiring,
        "mrr": [
            {"currency": currency, "amount": str(_money(amount))}
            for currency, amount in sorted(mrr_by_currency.items())
        ],
        "payments_this_month": payments.count(),
        "revenue_this_month": revenue_by_currency,
        "plans": Plan.objects.count(),
    }
