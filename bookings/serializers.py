from rest_framework import serializers
from .models import BookingRequest


class BookingRequestSerializer(serializers.ModelSerializer):
    customer_username = serializers.CharField(
        source="customer.username", read_only=True
    )
    package_title = serializers.CharField(
        source="package.title", read_only=True
    )
    profile_slug = serializers.CharField(
        source="package.profile.slug", read_only=True
    )
    profile_studio_name = serializers.CharField(
        source="package.profile.studio_name", read_only=True, allow_blank=True
    )

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "customer_username",
            "package",
            "package_title",
            "profile_slug",
            "profile_studio_name",
            "date",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "customer_username",
            "package_title",
            "profile_slug",
            "profile_studio_name",
            "status",
            "created_at",
        ]

    def validate_package(self, value):
        if not value.profile.is_published:
            raise serializers.ValidationError(
                "This package is not available"
            )
        return value
