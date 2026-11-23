import os

from django.core.management.base import BaseCommand

from apps.identity.models import User


class Command(BaseCommand):
    help = (
        "Crea el superadmin de un entorno desplegado usando "
        "AGENDA_SUPERADMIN_EMAIL y AGENDA_SUPERADMIN_PASSWORD. "
        "No modifica usuarios existentes."
    )

    def handle(self, *args, **options):
        email = os.getenv("AGENDA_SUPERADMIN_EMAIL", "").strip()
        password = os.getenv("AGENDA_SUPERADMIN_PASSWORD", "")
        if not email or not password:
            self.stdout.write("bootstrap_superadmin: variables sin configurar, no se hace nada.")
            return
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"bootstrap_superadmin: {email} ya existe, sin cambios.")
            return
        User.objects.create_superuser(
            email=email,
            username=email,
            password=password,
            first_name=os.getenv("AGENDA_SUPERADMIN_FIRST_NAME", "").strip(),
            is_saas_admin=True,
        )
        self.stdout.write(f"bootstrap_superadmin: superadmin {email} creado.")
