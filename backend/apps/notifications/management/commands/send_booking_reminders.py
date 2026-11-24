from django.core.management.base import BaseCommand

from apps.notifications.services import send_due_reminders


class Command(BaseCommand):
    help = "Envía recordatorios de reservas que comienzan entre 24 y 25 horas más adelante."

    def handle(self, *args, **options):
        result = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios: {result['queued']} enviados, {result['skipped']} omitidos."
        ))
