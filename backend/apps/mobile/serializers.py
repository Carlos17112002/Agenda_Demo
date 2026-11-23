from rest_framework import serializers

from apps.bookings.serializers import RescheduleSerializer

from .models import DeviceInstallation, PushMessage


class DeviceRegistrationSerializer(serializers.Serializer):
    installation_id = serializers.CharField(max_length=128)
    platform = serializers.ChoiceField(
        choices=DeviceInstallation.Platform.choices,
        default=DeviceInstallation.Platform.OTHER,
    )
    push_token = serializers.CharField(required=False, allow_blank=True, max_length=512)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=32)
    locale = serializers.CharField(required=False, allow_blank=True, max_length=16)


class DeviceInstallationSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = DeviceInstallation
        fields = [
            "id", "installation_id", "platform", "platform_display", "push_token",
            "app_version", "locale", "active", "last_seen_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class PushMessageSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PushMessage
        fields = [
            "id", "kind", "kind_display", "title", "body", "data", "status",
            "status_display", "sent_at", "read_at", "created_at",
        ]
        read_only_fields = fields


class OperationInputSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    type = serializers.CharField(max_length=48)
    payload = serializers.DictField()


class OperationBatchSerializer(serializers.Serializer):
    operations = OperationInputSerializer(many=True, allow_empty=False)


class BookingCancelPayloadSerializer(serializers.Serializer):
    booking = serializers.UUIDField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)


class BookingReschedulePayloadSerializer(RescheduleSerializer):
    booking = serializers.UUIDField()
    expected_start_at = serializers.DateTimeField(required=False)
