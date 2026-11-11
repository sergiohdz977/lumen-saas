from rest_framework import serializers
from bookings.models import BookingRequest
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
    profile_slug = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "photographer", "photographer_username",
            "customer", "customer_username",
            "booking", "profile_slug",
            "rating", "comment",
            "reply", "replied_at", "created_at",
        ]
        read_only_fields = [
            "id", "customer", "photographer_username",
            "customer_username", "profile_slug",
            "reply", "replied_at", "created_at",
        ]

    def get_profile_slug(self, obj):
        """Public profile where this review lives (for deep links)."""
        profile = getattr(obj.photographer, "profile", None)
        return profile.slug if profile else None

    def validate_photographer(self, value):
        if value.role != value.ROLE_PHOTOGRAPHER:
            raise serializers.ValidationError("You can only review photographers")
        if value == self.context["request"].user:
            raise serializers.ValidationError("You cannot review yourself")
        return value

    def validate(self, attrs):
        booking = attrs.get("booking")
        if booking is None:
            raise serializers.ValidationError(
                "A completed booking is required to leave a review"
            )
        user = self.context["request"].user
        if booking.customer_id != user.id:
            raise serializers.ValidationError(
                "This booking does not belong to you"
            )
        if booking.status != BookingRequest.Status.COMPLETED:
            raise serializers.ValidationError(
                "You can only review completed bookings"
            )
        photographer = attrs.get("photographer")
        if (
            photographer is not None
            and booking.package.profile.user_id != photographer.id
        ):
            raise serializers.ValidationError(
                "The booking does not match that photographer"
            )
        if Review.objects.filter(booking=booking).exists():
            raise serializers.ValidationError(
                "You have already reviewed this session"
            )
        return attrs
