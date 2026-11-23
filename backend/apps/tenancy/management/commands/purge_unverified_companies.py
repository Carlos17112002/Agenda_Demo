from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.identity.models import Membership, User
from apps.tenancy.models import Company, TenantContext


class Command(BaseCommand):
    help = (
        "Elimina empresas del alta autoservicio que nunca verificaron su correo. "
        "Por defecto borra registros de más de 7 días."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        company_ids = list(
            Company.objects.filter(
                created_at__lt=cutoff,
                memberships__active=True,
                memberships__user__is_active=False,
            ).values_list("id", flat=True).distinct()
        )
        purged = 0
        for company in Company.objects.filter(id__in=company_ids):
            owner_ids = list(
                Membership.objects.filter(company=company).values_list("user_id", flat=True)
            )
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] {company.slug}")
                purged += 1
                continue
            with transaction.atomic():
                AuditEvent.objects.filter(company=company).delete()
                Membership.objects.filter(company=company).delete()
                TenantContext.objects.filter(company=company).delete()
                company.delete()
                for user in User.objects.filter(id__in=owner_ids, is_active=False):
                    if not user.memberships.exists():
                        user.delete()
            purged += 1
        self.stdout.write(f"purge_unverified_companies: {purged} empresa(s) procesada(s).")
