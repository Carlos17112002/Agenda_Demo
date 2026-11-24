from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.tests.utils import BookingScenarioMixin
from apps.notifications.models import Notification


@override_settings(PUBLIC_BASE_URL="https://agenda.test")
class BookingReminderTests(BookingScenarioMixin, TestCase):
    def setUp(self):
        self.build_scenario()

    def make_booking(self, hours_ahead=24.5, status=Booking.Status.SCHEDULED, email=None):
        if email is not None:
            self.customer.email = email
            self.customer.save(update_fields=["email"])
        start = timezone.now() + timedelta(hours=hours_ahead)
        return Booking.objects.create(
            company=self.company, branch=self.branch, customer=self.customer,
            service=self.service, worker=self.worker, start_at=start,
            end_at=start + timedelta(minutes=30), block_start=start,
            block_end=start + timedelta(minutes=30), status=status,
            source=Booking.Source.PUBLIC, service_name=self.service.name,
            duration_minutes=30, price=self.service.price,
        )

    def run_command(self):
        with self.captureOnCommitCallbacks(execute=True):
            call_command("send_booking_reminders")

    def reminders(self):
        return Notification.objects.filter(kind=Notification.Kind.BOOKING_REMINDER)

    def test_sends_reminder_with_cancel_and_reschedule_links(self):
        booking = self.make_booking(email="luis@example.com")

        self.run_command()

        reminder = self.reminders().get()
        self.assertEqual(reminder.status, Notification.Status.SENT)
        self.assertEqual(reminder.recipient_email, "luis@example.com")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("Recordatorio", message.subject)
        self.assertIn(booking.public_code, message.body)
        detail_url = f"https://agenda.test/b/{self.company.slug}/reserva/{booking.public_code}/"
        self.assertIn(detail_url, message.body)
        self.assertIn(f"{detail_url}?reagendar=1", message.body)

    def test_is_idempotent_between_runs(self):
        self.make_booking(email="luis@example.com")

        self.run_command()
        self.run_command()

        self.assertEqual(self.reminders().count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_ignores_bookings_outside_the_window(self):
        self.make_booking(hours_ahead=30, email="luis@example.com")
        self.make_booking(hours_ahead=1, email="luis@example.com")

        self.run_command()

        self.assertEqual(self.reminders().count(), 0)

    def test_ignores_canceled_bookings(self):
        self.make_booking(status=Booking.Status.CANCELED, email="luis@example.com")

        self.run_command()

        self.assertEqual(self.reminders().count(), 0)

    def test_ignores_customers_without_email(self):
        self.make_booking(email="")

        self.run_command()

        self.assertEqual(self.reminders().count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_retries_after_a_failed_delivery(self):
        booking = self.make_booking(email="luis@example.com")
        Notification.objects.create(
            company=self.company, booking=booking, kind=Notification.Kind.BOOKING_REMINDER,
            recipient_email="luis@example.com", subject="Recordatorio", body="fallido",
            status=Notification.Status.FAILED,
        )

        self.run_command()

        self.assertEqual(self.reminders().filter(status=Notification.Status.SENT).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
