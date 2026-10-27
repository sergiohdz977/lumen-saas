from rest_framework import serializers

from bookings.models import BookingRequest

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "booking",
            "kind",
            "customer",
            "photographer",
            "amount_cents",
            "currency",
            "status",
            "created_at",
            "paid_at",
        ]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=BookingRequest.objects.all()
    )
    kind = serializers.ChoiceField(
        choices=Payment.Kind.choices,
        default=Payment.Kind.DEPOSIT,
        required=False,
    )
