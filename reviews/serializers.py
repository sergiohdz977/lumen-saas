from rest_framework import serializers
from clients.models import Client
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        error_messages={
            "required": "La nota es obligatoria",
            "min_value": "La nota mínima es 1",
            "max_value": "La nota máxima es 5",
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
            raise serializers.ValidationError("Solo se pueden valorar fotógrafos")
        if value == self.context["request"].user:
            raise serializers.ValidationError("No puedes valorarte a ti mismo")
        if not Client.objects.filter(
            photographer=value, user=self.context["request"].user
        ).exists():
            raise serializers.ValidationError(
                "Solo puedes valorar fotógrafos con los que has trabajado"
            )
        if Review.objects.filter(
            photographer=value, customer=self.context["request"].user
        ).exclude(pk=self.instance.pk if self.instance else None):
            raise serializers.ValidationError("Ya has valorado a este fotógrafo")
        return value
