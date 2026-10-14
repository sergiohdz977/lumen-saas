from rest_framework import serializers
from .models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(
        choices=User.ROLE_CHOICES,
        default=User.ROLE_CUSTOMER,
        error_messages={
            "invalid_choice": "El rol debe ser 'photographer' o 'customer'",
        },
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "role"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este correo ya existe")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)