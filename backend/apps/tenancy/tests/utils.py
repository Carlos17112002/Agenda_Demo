from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

from apps.identity.models import Membership, User
from apps.tenancy.models import Company, TenantContext


def make_user(email, password="Correct-Horse-Battery-983!"):
    return User.objects.create_user(username=email, email=email, password=password)


def make_membership(user, company, role=Membership.Role.OWNER):
    return Membership.objects.create(user=user, company=company, role=role)


def make_context(user, company):
    return TenantContext.objects.create(user=user, company=company,
                                        expires_at=timezone.now() + timedelta(hours=1))


def tenant_client(user, context):
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_TENANT_CONTEXT=str(context.id))
    return client


def make_company(slug, name=None):
    return Company.objects.create(name=name or slug.title(), slug=slug)
