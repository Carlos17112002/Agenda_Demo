from django.db.models import Q
from rest_framework.permissions import BasePermission

ROLE_DEFAULTS = {
    "owner": {"*"},
    "admin": {"*"},
    "manager": {
        "bookings.read", "bookings.write", "customers.read", "customers.write",
        "catalog.read", "catalog.write", "workforce.read", "workforce.write",
        "inventory.read", "purchases.read", "sales.read", "sales.write",
        "payments.read", "cash.read", "cash.manage", "expenses.read", "expenses.write",
        "reports.read", "subscription.read", "branches.read",
    },
    "reception": {
        "bookings.read", "bookings.write", "customers.read", "customers.write",
        "catalog.read", "workforce.read", "sales.read", "sales.write",
        "payments.read", "cash.read", "cash.manage", "branches.read",
    },
    "worker": {
        "bookings.own.read", "bookings.own.write", "customers.assigned.read",
        "catalog.read", "branches.read",
    },
    "inventory": {
        "inventory.read", "inventory.write", "purchases.read", "purchases.write",
        "catalog.read", "branches.read",
    },
    "accounting": {
        "sales.read", "reports.read", "payments.read", "catalog.read", "inventory.read",
        "cash.read", "expenses.read", "expenses.write", "subscription.read", "branches.read",
    },
}

PERMISSION_CATALOG = sorted({
    "bookings.read", "bookings.write", "bookings.own.read", "bookings.own.write",
    "customers.read", "customers.write", "customers.assigned.read",
    "catalog.read", "catalog.write", "workforce.read", "workforce.write",
    "inventory.read", "inventory.write", "purchases.read", "purchases.write",
    "sales.read", "sales.write", "cash.read", "cash.manage", "payments.read",
    "expenses.read", "expenses.write", "reports.read",
    "subscription.read", "subscription.manage", "branches.read", "branches.manage",
    "company.manage",
})


def role_defaults_payload():
    catalog = set(PERMISSION_CATALOG)
    return {
        role: sorted(catalog if "*" in permissions else permissions)
        for role, permissions in ROLE_DEFAULTS.items()
    }


def has_tenant_permission(membership, required, branch_id=None):
    """Role baseline plus explicit grants for one permission; deny always wins."""
    grants = membership.permission_grants.filter(permission=required)
    if branch_id:
        grants = grants.filter(Q(branch__isnull=True) | Q(branch_id=branch_id))
    elif grants.filter(branch__isnull=False).exists():
        grants = grants.filter(branch__isnull=True)
    if grants.filter(effect="deny").exists():
        return False
    if grants.filter(effect="allow").exists():
        return True
    defaults = ROLE_DEFAULTS.get(membership.role, set())
    return "*" in defaults or required in defaults


def effective_permissions(membership):
    """Global permissions for navigation; branch-scoped grants are still enforced per request."""
    defaults = ROLE_DEFAULTS.get(membership.role, set())
    permissions = set(PERMISSION_CATALOG) if "*" in defaults else set(defaults)
    grants = membership.permission_grants.filter(branch__isnull=True)
    denied = set(grants.filter(effect="deny").values_list("permission", flat=True))
    allowed = set(grants.filter(effect="allow").values_list("permission", flat=True))
    return sorted((permissions - denied) | allowed)


def _resolve_tenant(request):
    from .authentication import resolve_tenant
    tenant = getattr(request, "tenant", None)
    if tenant is None and request.user and request.user.is_authenticated:
        tenant = resolve_tenant(request, request.user)
    return tenant


def _required_permission(view):
    if hasattr(view, "get_required_tenant_permission"):
        return view.get_required_tenant_permission()
    return getattr(view, "required_tenant_permission", None)


class HasTenantContext(BasePermission):
    message = "Selecciona una empresa a la que tengas acceso."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and _resolve_tenant(request))


class HasTenantPermission(BasePermission):
    """Check role baseline plus explicit grants; a deny grant always wins."""

    def has_permission(self, request, view):
        tenant = _resolve_tenant(request)
        if not tenant or not request.user.is_authenticated:
            return False
        membership = request.user.memberships.filter(company=tenant, active=True).first()
        if not membership:
            return False
        required = _required_permission(view)
        if not required:
            return False
        branch_id = view.kwargs.get("branch_pk") or getattr(request, "data", {}).get("branch")
        if branch_id:
            from .models import Branch
            if not Branch.objects.filter(pk=branch_id, company=tenant).exists():
                return False
        if not has_tenant_permission(membership, required, branch_id):
            return False
        from apps.billing.gating import enforce_tenant_billing
        enforce_tenant_billing(tenant, required)
        return True
