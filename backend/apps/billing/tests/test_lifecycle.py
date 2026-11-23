from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.billing.models import Invoice, Payment, Subscription
from apps.billing.services import (
    cancel_subscription, record_payment, resume_subscription, start_subscription,
)
from apps.tenancy.tests.utils import make_company

from .utils import BillingScenarioMixin


class SubscriptionLifecycleTests(BillingScenarioMixin, TestCase):
    def setUp(self):
        self.build_billing_scenario()

    def test_trial_starts_usable_with_remaining_days(self):
        self.assertEqual(self.subscription.status, Subscription.Status.TRIALING)
        self.assertTrue(self.subscription.is_usable())
        self.assertEqual(self.subscription.effective_status(), Subscription.Status.TRIALING)
        self.assertGreater(self.subscription.days_remaining(), 0)

    def test_effective_status_moves_from_grace_to_expired(self):
        now = timezone.now()
        self.subscription.status = Subscription.Status.ACTIVE
        self.subscription.current_period_end = now - timedelta(days=2)
        self.subscription.save()
        self.assertEqual(self.subscription.effective_status(now), Subscription.Status.PAST_DUE)
        self.assertTrue(self.subscription.is_usable(now))

        self.subscription.current_period_end = now - timedelta(days=8)
        self.subscription.save()
        self.assertEqual(self.subscription.effective_status(now), Subscription.Status.EXPIRED)
        self.assertFalse(self.subscription.is_usable(now))

    def test_payment_activates_subscription_and_issues_paid_invoice(self):
        payment = record_payment(
            self.subscription, amount="19990", method="transfer",
            reference="TRX-1", actor=self.owner,
        )
        self.subscription.refresh_from_db()
        self.company.refresh_from_db()

        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(self.subscription.current_period_start, payment.period_start)
        self.assertGreater(self.subscription.current_period_end, timezone.now())
        self.assertTrue(self.subscription.is_usable())
        self.assertEqual(self.company.status, "active")

        invoice = Invoice.objects.get(payment=payment)
        self.assertEqual(invoice.number, "FAC-000001")
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.total, payment.amount)
        self.assertEqual(invoice.company_id, self.company.id)

    def test_payment_reference_is_idempotent(self):
        first = record_payment(
            self.subscription, amount="19990", method="cash", reference="DUP-1",
        )
        second = record_payment(
            self.subscription, amount="19990", method="cash", reference="DUP-1",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Payment.objects.filter(company=self.company).count(), 1)
        self.assertEqual(Invoice.objects.filter(company=self.company).count(), 1)

    def test_invoice_numbers_are_sequential_per_company(self):
        record_payment(self.subscription, amount="19990", method="transfer", reference="A-1")
        other_company = make_company("otra-empresa", "Otra")
        start_subscription(other_company, self.plan, trial_days=0)
        record_payment(
            Subscription.objects.get(company=other_company), amount="19990",
            method="transfer", reference="B-1",
        )
        second = record_payment(
            self.subscription, amount="19990", method="transfer", reference="A-2",
        )

        first_invoice = Invoice.objects.filter(company=self.company).order_by("sequence").first()
        other_invoice = Invoice.objects.get(company=other_company)
        second_invoice = Invoice.objects.get(payment=second)
        self.assertEqual(first_invoice.number, "FAC-000001")
        self.assertEqual(other_invoice.number, "FAC-000001")
        self.assertEqual(second_invoice.number, "FAC-000002")
        self.assertGreater(second.period_start, first_invoice.paid_at)

    def test_cancel_at_period_end_keeps_access_and_resume_clears_it(self):
        cancel_subscription(self.subscription, immediate=False, actor=self.owner)
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertTrue(self.subscription.is_usable())

        resume_subscription(self.subscription, actor=self.owner)
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.cancel_at_period_end)
        self.assertIsNone(self.subscription.canceled_at)

    def test_immediate_cancel_ends_access(self):
        cancel_subscription(self.subscription, immediate=True, actor=self.owner)
        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.ended_at)
        self.assertEqual(self.subscription.effective_status(), Subscription.Status.CANCELED)
        self.assertFalse(self.subscription.is_usable())

    def test_expired_subscription_can_be_renewed_by_payment(self):
        now = timezone.now()
        self.subscription.status = Subscription.Status.ACTIVE
        self.subscription.current_period_start = now - timedelta(days=40)
        self.subscription.current_period_end = now - timedelta(days=8)
        self.subscription.save()
        self.assertFalse(self.subscription.is_usable())

        payment = record_payment(
            self.subscription, amount="19990", method="transfer", reference="RENEW-1",
        )
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.ACTIVE)
        self.assertTrue(self.subscription.is_usable())
        self.assertGreater(self.subscription.current_period_end, now)
        self.assertEqual(payment.invoices.count(), 1)
