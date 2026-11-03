from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "id",
            "user",
            "name",
            "email",
            "phone",
            "is_manual",
            "created_at",
        ]
        read_only_fields = ["id", "user", "is_manual", "created_at"]
