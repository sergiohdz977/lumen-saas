from rest_framework import serializers
from .models import Package, PhotographerProfile, PortfolioPhoto


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


class PackageSerializer(serializers.ModelSerializer):
    profile_slug = serializers.CharField(source="profile.slug", read_only=True)
    studio_name = serializers.CharField(
        source="profile.studio_name", read_only=True
    )

    class Meta:
        model = Package
        fields = [
            "id",
            "profile_slug",
            "studio_name",
            "title",
            "description",
            "price",
        ]
        read_only_fields = ["id", "profile_slug", "studio_name"]


class PortfolioPhotoSerializer(serializers.ModelSerializer):
    profile_slug = serializers.CharField(source="profile.slug", read_only=True)
    studio_name = serializers.CharField(
        source="profile.studio_name", read_only=True
    )

    class Meta:
        model = PortfolioPhoto
        fields = [
            "id",
            "profile_slug",
            "studio_name",
            "image",
            "caption",
        ]
        read_only_fields = ["id", "profile_slug", "studio_name"]
