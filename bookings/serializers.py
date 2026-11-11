from django.utils import timezone
from rest_framework import serializers
from payments.models import Payment
from .models import BookingRequest, Message
from .policies import client_refund_cents, policy_summary, refund_fraction


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(
        source="sender.username", read_only=True, allow_null=True
    )
    is_system = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "booking",
            "sender",
            "sender_username",
            "is_system",
            "text",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "booking",
            "sender",
            "sender_username",
            "is_system",
            "created_at",
        ]

    def get_is_system(self, obj):
        return obj.sender_id is None


class BookingRequestSerializer(serializers.ModelSerializer):
    customer_username = serializers.CharField(
        source="customer.username", read_only=True
    )
    package_title = serializers.CharField(
        source="package.title", read_only=True
    )
    profile_slug = serializers.CharField(
        source="package.profile.slug", read_only=True
    )
    profile_studio_name = serializers.CharField(
        source="package.profile.studio_name", read_only=True, allow_blank=True
    )
    cancellation_policy = serializers.CharField(
        source="package.cancellation_policy", read_only=True
    )
    cancellation_policy_summary = serializers.SerializerMethodField()
    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    shoot = serializers.SerializerMethodField()
    days_until_event = serializers.SerializerMethodField()
    refundable = serializers.SerializerMethodField()
    deposit_cents = serializers.SerializerMethodField()
    expected_refund_cents = serializers.SerializerMethodField()

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "customer_username",
            "package",
            "package_title",
            "profile_slug",
            "profile_studio_name",
            "cancellation_policy",
            "cancellation_policy_summary",
            "date",
            "event_location",
            "event_time",
            "event_notes",
            "message",
            "final_price",
            "effective_price",
            "status",
            "policy_accepted",
            "payment_status",
            "deposit_deadline",
            "shoot",
            "days_until_event",
            "refundable",
            "deposit_cents",
            "expected_refund_cents",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "customer_username",
            "package_title",
            "profile_slug",
            "profile_studio_name",
            "cancellation_policy",
            "cancellation_policy_summary",
            "final_price",
            "effective_price",
            "status",
            "payment_status",
            "deposit_deadline",
            "shoot",
            "days_until_event",
            "refundable",
            "deposit_cents",
            "expected_refund_cents",
            "created_at",
        ]

    def get_shoot(self, obj):
        shoot = getattr(obj, "shoot", None)
        return shoot.pk if shoot else None

    def get_days_until_event(self, obj):
        return (obj.date.date() - timezone.now().date()).days

    def get_cancellation_policy_summary(self, obj):
        return policy_summary(obj.package)

    def get_refundable(self, obj):
        """Policy window: would a client cancellation refund anything now?"""
        return refund_fraction(obj) > 0

    def get_deposit_cents(self, obj):
        """Amount already collected as a deposit (None when unpaid)."""
        deposit = (
            obj.payments.filter(
                kind=Payment.Kind.DEPOSIT, status=Payment.Status.PAID
            )
            .order_by("-created_at")
            .first()
        )
        return deposit.amount_cents if deposit else None

    def get_expected_refund_cents(self, obj):
        """Deposit portion a client cancellation would refund right now."""
        deposit = self.get_deposit_cents(obj)
        return client_refund_cents(obj, deposit or 0)

    def validate(self, attrs):
        if self.instance is None and not attrs.get(
            "policy_accepted", False
        ):
            raise serializers.ValidationError(
                {
                    "policy_accepted": (
                        "You must accept the photographer's "
                        "cancellation policy"
                    )
                }
            )
        return attrs

    def validate_package(self, value):
        if not value.profile.is_published:
            raise serializers.ValidationError(
                "This package is not available"
            )
        return value
