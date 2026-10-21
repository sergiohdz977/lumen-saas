from rest_framework import serializers

from bookings.models import BookingRequest

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "booking",
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
