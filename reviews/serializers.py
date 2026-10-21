from rest_framework import serializers
from clients.models import Client
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        error_messages={
            "required": "A rating is required",
            "min_value": "Rating must be at least 1",
            "max_value": "Rating must be at most 5",
        },
    )
    photographer_username = serializers.CharField(
        source="photographer.username", read_only=True
    )
    customer_username = serializers.CharField(
        source="customer.username", read_only=True
    )

    class Meta:
        model = Review
        fields = [
            "id", "photographer", "photographer_username",
            "customer", "customer_username",
            "rating", "comment", "created_at",
        ]
        read_only_fields = [
            "id", "customer", "photographer_username",
            "customer_username", "created_at",
        ]

    def validate_photographer(self, value):
        if value.role != value.ROLE_PHOTOGRAPHER:
            raise serializers.ValidationError("You can only review photographers")
        if value == self.context["request"].user:
            raise serializers.ValidationError("You cannot review yourself")
        if not Client.objects.filter(
            photographer=value, user=self.context["request"].user
        ).exists():
            raise serializers.ValidationError(
                "You can only review photographers you have worked with"
            )
        if Review.objects.filter(
            photographer=value, customer=self.context["request"].user
        ).exclude(pk=self.instance.pk if self.instance else None):
            raise serializers.ValidationError(
                "You have already reviewed this photographer"
            )
        return value
