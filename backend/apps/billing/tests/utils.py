from decimal import Decimal

from rest_framework.test import APIClient

from apps.billing.models import Plan, PlanFeature
from apps.billing.services import start_subscription
from apps.identity.models import Membership
from apps.tenancy.tests.utils import (
    make_company, make_context, make_membership, make_user, tenant_client,
)

FEATURE_CODES = [
    PlanFeature.Code.BOOKINGS, PlanFeature.Code.CUSTOMERS, PlanFeature.Code.CATALOG,
    PlanFeature.Code.WORKFORCE, PlanFeature.Code.INVENTORY, PlanFeature.Code.SALES,
    PlanFeature.Code.REPORTS, PlanFeature.Code.BRANCHES, PlanFeature.Code.WORKERS,
]


def make_plan(code, *, name=None, price="19990", billing_period="monthly",
              trial_days=14, features=None, is_default=False, active=True):
    plan = Plan.objects.create(
        code=code, name=name or code.title(), price=Decimal(price),
        billing_period=billing_period, trial_days=trial_days,
        is_default=is_default, active=active,
    )
    if features is None:
        features = {feature: (True, None) for feature in FEATURE_CODES}
    for feature_code, config in features.items():
        enabled, limit = config if isinstance(config, tuple) else (config, None)
        PlanFeature.objects.create(
            plan=plan, code=feature_code, enabled=enabled, limit_value=limit,
        )
    return plan


def make_saas_admin(email="saas@example.com"):
    user = make_user(email)
    user.is_saas_admin = True
    user.save(update_fields=["is_saas_admin"])
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class BillingScenarioMixin:
    def build_billing_scenario(self, slug="saas-a", features=None, trial_days=14,
                               plan_price="19990"):
        self.company = make_company(slug, f"Empresa {slug}")
        self.owner = make_user(f"owner-{slug}@example.com")
        self.membership = make_membership(self.owner, self.company, Membership.Role.OWNER)
        self.context = make_context(self.owner, self.company)
        self.client = tenant_client(self.owner, self.context)
        self.plan = make_plan(
            f"plan-{slug}", name="Plan Pro", price=plan_price,
            features=features, trial_days=trial_days,
        )
        self.subscription = start_subscription(
            self.company, self.plan, trial_days=trial_days, actor=self.owner,
        )
        return self.subscription

    def role_client(self, role, email):
        user = make_user(email)
        membership = make_membership(user, self.company, role)
        return tenant_client(user, make_context(user, self.company)), membership, user
