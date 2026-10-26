from rest_framework import serializers
from .models import Shoot


class ShootSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_email = serializers.EmailField(
        source="client.email", read_only=True, allow_blank=True
    )

    class Meta:
        model = Shoot
        fields = [
            "id",
            "client",
            "client_name",
            "client_email",
            "title",
            "shoot_type",
            "date",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "client_name", "client_email", "created_at"]

    def validate_client(self, value):
        request = self.context["request"]
        if value.photographer_id != request.user.id:
            raise serializers.ValidationError(
                "That client does not belong to your account"
            )
        return value

    def validate_status(self, value):
        if self.instance is None:
            return value
        if value == self.instance.status:
            return value
        allowed_transitions = {
            Shoot.Status.BOOKED: {Shoot.Status.EDITING},
            Shoot.Status.EDITING: {Shoot.Status.DELIVERED},
            Shoot.Status.DELIVERED: set(),
        }
        if value not in allowed_transitions[self.instance.status]:
            raise serializers.ValidationError(
                "Invalid status transition"
            )
        return value
