from rest_framework import serializers
from .models import PhotographerProfile


class PhotographerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PhotographerProfile
        fields = [
            "id",
            "slug",
            "username",
            "studio_name",
            "bio",
            "city",
            "specialties",
            "phone",
            "created_at",
        ]
        read_only_fields = fields
