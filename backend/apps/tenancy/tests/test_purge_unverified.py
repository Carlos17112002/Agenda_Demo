from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, User
from apps.tenancy.models import Company, TenantContext


def unverified_company(name, slug, email, *, days_old=10, active=False):
    company = Company.objects.create(name=name, slug=slug)
    user = User.objects.create_user(username=email, email=email, is_active=active)
    Membership.objects.create(user=user, company=company, role=Membership.Role.OWNER)
    AuditEvent.objects.create(company=company, actor=user, action="company.registered",
                              entity_type="Company", entity_id=str(company.id))
    Company.objects.filter(pk=company.pk).update(
        created_at=timezone.now() - timedelta(days=days_old)
    )
    return company, user


class PurgeUnverifiedCommandTests(TestCase):
    def test_deletes_only_old_unverified_companies(self):
        old_company, old_user = unverified_company("Vieja", "vieja", "vieja@example.com")
        TenantContext.objects.create(
            user=old_user, company=old_company,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        recent_company, _ = unverified_company(
            "Nueva", "nueva", "nueva@example.com", days_old=1,
        )
        verified_company, _ = unverified_company(
            "Activa", "activa", "activa@example.com", days_old=30, active=True,
        )

        call_command("purge_unverified_companies", "--days", "7")

        self.assertFalse(Company.objects.filter(pk=old_company.pk).exists())
        self.assertFalse(User.objects.filter(pk=old_user.pk).exists())
        self.assertFalse(TenantContext.objects.filter(company_id=old_company.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(company_id=old_company.pk).exists())
        self.assertTrue(Company.objects.filter(pk=recent_company.pk).exists())
        self.assertTrue(Company.objects.filter(pk=verified_company.pk).exists())

    def test_dry_run_deletes_nothing(self):
        company, _ = unverified_company("Vieja", "vieja", "vieja@example.com")
        call_command("purge_unverified_companies", "--days", "7", "--dry-run")
        self.assertTrue(Company.objects.filter(pk=company.pk).exists())
