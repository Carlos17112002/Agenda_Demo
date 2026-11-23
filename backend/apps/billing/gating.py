from rest_framework.exceptions import APIException

from .models import PlanFeature, Subscription


class SubscriptionInactive(APIException):
    status_code = 402
    default_detail = "La suscripción de la empresa no está vigente."
    default_code = "subscription_inactive"


class PlanFeatureUnavailable(APIException):
    status_code = 403
    default_detail = "El plan actual no incluye este módulo."
    default_code = "plan_feature_unavailable"


class PlanLimitReached(APIException):
    status_code = 402
    default_detail = "Se alcanzó el límite del plan actual."
    default_code = "plan_limit_reached"


MODULE_FEATURES = {
    "bookings": PlanFeature.Code.BOOKINGS,
    "customers": PlanFeature.Code.CUSTOMERS,
    "catalog": PlanFeature.Code.CATALOG,
    "workforce": PlanFeature.Code.WORKFORCE,
    "inventory": PlanFeature.Code.INVENTORY,
    "purchases": PlanFeature.Code.INVENTORY,
    "sales": PlanFeature.Code.SALES,
    "cash": PlanFeature.Code.SALES,
    "expenses": PlanFeature.Code.SALES,
    "payments": PlanFeature.Code.SALES,
    "reports": PlanFeature.Code.REPORTS,
}

LIMIT_LABELS = {
    PlanFeature.Code.BRANCHES: "sucursales activas",
    PlanFeature.Code.WORKERS: "trabajadores activos",
}


def current_subscription(company):
    return (Subscription.objects.filter(company=company, ended_at__isnull=True)
            .select_related("plan").prefetch_related("plan__features").first())


def enforce_tenant_billing(company, permission):
    """Subscription and plan-module gate; billing endpoints stay reachable when expired."""
    subscription = current_subscription(company)
    if permission.startswith("subscription."):
        return subscription
    if subscription is None:
        if Subscription.objects.filter(company=company).exists():
            raise SubscriptionInactive("La suscripción de la empresa finalizó.")
        return None
    if not subscription.is_usable():
        raise SubscriptionInactive()
    module = permission.split(".", 1)[0]
    feature = MODULE_FEATURES.get(module)
    if feature and not subscription.has_feature(feature):
        raise PlanFeatureUnavailable(
            f"El plan {subscription.plan.name} no incluye este módulo."
        )
    return subscription


def enforce_plan_limit(company, code, current_count):
    subscription = current_subscription(company)
    if subscription is None or not subscription.is_usable():
        return
    limit = subscription.feature_limit(code)
    if limit is not None and current_count >= limit:
        label = LIMIT_LABELS.get(code, "registros")
        raise PlanLimitReached(
            f"El plan {subscription.plan.name} permite hasta {limit} {label}."
        )
