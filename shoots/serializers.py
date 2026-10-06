from rest_framework import serializers
from .models import Shoot


class ShootSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shoot
        fields = ["id", "client", "title", "shoot_type", "date", "status", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_client(self, value):
        request = self.context["request"]
        if value.photographer_id != request.user.id:
            raise serializers.ValidationError(
                "El cliente no pertenece a tu cuenta"
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
                "Transición de estado no válida"
            )
        return value
