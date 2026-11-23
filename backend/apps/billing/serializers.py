from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.tenancy.models import Company

from .models import Invoice, Payment, Plan, PlanFeature, Subscription


class PlanFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanFeature
        fields = ["code", "enabled", "limit_value"]


class PublicPlanSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "description", "price", "currency",
                  "billing_period", "trial_days", "is_default", "features"]
        read_only_fields = fields


class PlanSerializer(PublicPlanSerializer):
    class Meta(PublicPlanSerializer.Meta):
        fields = PublicPlanSerializer.Meta.fields + [
            "active", "is_default", "sort_order", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PlanFeatureInputSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=PlanFeature.Code.choices)
    enabled = serializers.BooleanField(default=True)
    limit_value = serializers.IntegerField(min_value=0, allow_null=True, required=False)


class PlanWriteSerializer(serializers.ModelSerializer):
    # DRF derives a UniqueValidator from the partial unique constraint; exclusivity
    # is enforced in create/update instead, so the field is declared explicitly.
    is_default = serializers.BooleanField(required=False)
    features = PlanFeatureInputSerializer(many=True, required=False)

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "description", "price", "currency",
                  "billing_period", "trial_days", "active", "is_default", "sort_order",
                  "features"]
        read_only_fields = ["id"]
        validators = []

    def validate_code(self, code):
        queryset = Plan.objects.filter(code=code)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ya existe un plan con este código.")
        return code

    def validate_currency(self, currency):
        return currency.upper()

    def validate_features(self, features):
        codes = [item["code"] for item in features]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("No se puede repetir un código de funcionalidad.")
        return features

    def _replace_features(self, plan, features):
        plan.features.all().delete()
        PlanFeature.objects.bulk_create([
            PlanFeature(plan=plan, **item) for item in features
        ])

    def create(self, validated_data):
        features = validated_data.pop("features", [])
        with transaction.atomic():
            if validated_data.get("is_default"):
                Plan.objects.filter(is_default=True).update(is_default=False)
            plan = Plan.objects.create(**validated_data)
            self._replace_features(plan, features)
        return plan

    def update(self, instance, validated_data):
        features = validated_data.pop("features", None)
        with transaction.atomic():
            if validated_data.get("is_default"):
                Plan.objects.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)
            instance = super().update(instance, validated_data)
            if features is not None:
                self._replace_features(instance, features)
        return instance


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    features = PlanFeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price", "currency", "billing_period",
                  "trial_days", "features"]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    effective_status = serializers.SerializerMethodField()
    usable = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "company", "company_name", "plan", "status", "effective_status",
                  "usable", "days_remaining", "started_at", "trial_ends_at",
                  "current_period_start", "current_period_end", "cancel_at_period_end",
                  "canceled_at", "ended_at", "created_at", "updated_at"]
        read_only_fields = fields

    def get_effective_status(self, subscription):
        return subscription.effective_status()

    def get_usable(self, subscription):
        return subscription.is_usable()

    def get_days_remaining(self, subscription):
        return subscription.days_remaining()


class SubscriptionCreateSerializer(serializers.Serializer):
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())
    trial_days = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class ChangePlanSerializer(serializers.Serializer):
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.all())


class CancelSubscriptionSerializer(serializers.Serializer):
    immediate = serializers.BooleanField(default=False)


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    description = serializers.CharField(max_length=240, required=False, allow_blank=True)
    paid_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate_amount(self, amount):
        if amount <= 0:
            raise serializers.ValidationError("El pago debe ser mayor que cero.")
        return amount

    def validate_paid_at(self, value):
        return value or timezone.now()


class PaymentSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    subscription = serializers.UUIDField(source="subscription_id", read_only=True)
    invoice_numbers = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "company", "subscription", "amount", "currency", "method",
                  "status", "reference", "paid_at", "period_start", "period_end",
                  "created_by", "created_at", "invoice_numbers"]
        read_only_fields = fields

    def get_invoice_numbers(self, payment):
        return [invoice.number for invoice in payment.invoices.all()]


class InvoiceSerializer(serializers.ModelSerializer):
    company = serializers.UUIDField(source="company_id", read_only=True)
    subscription = serializers.UUIDField(source="subscription_id", read_only=True)
    payment = serializers.UUIDField(source="payment_id", read_only=True, allow_null=True)

    class Meta:
        model = Invoice
        fields = ["id", "company", "subscription", "payment", "number", "description",
                  "subtotal", "tax", "total", "currency", "status", "period_start",
                  "period_end", "issued_at", "due_at", "paid_at", "created_at"]
        read_only_fields = fields


class SaasCompanySerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "slug", "legal_name", "tax_identifier", "status",
                  "created_at", "updated_at", "subscription"]
        read_only_fields = fields

    def get_subscription(self, company):
        subscriptions = getattr(company, "open_subscriptions", None) or []
        subscription = subscriptions[0] if subscriptions else None
        if subscription is None:
            return None
        return {
            "id": str(subscription.id),
            "plan": subscription.plan.code,
            "status": subscription.status,
            "effective_status": subscription.effective_status(),
            "usable": subscription.is_usable(),
            "current_period_end": subscription.current_period_end,
            "trial_ends_at": subscription.trial_ends_at,
        }


class CompanyStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["active", "suspended", "closed"])
