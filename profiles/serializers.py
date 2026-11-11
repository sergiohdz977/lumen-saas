from rest_framework import serializers
from .models import Package, PhotographerProfile, PortfolioCollection, PortfolioPhoto
from bookings.policies import policy_summary


class PhotographerProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = PhotographerProfile
        fields = [
            "id",
            "user_id",
            "slug",
            "username",
            "studio_name",
            "profile_picture",
            "cover_image",
            "bio",
            "city",
            "specialties",
            "phone",
            "years_experience",
            "languages",
            "equipment",
            "is_published",
            "plan",
            "rating_avg",
            "rating_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "slug",
            "username",
            "plan",
            "rating_avg",
            "rating_count",
            "cover_image",
            "created_at",
        ]

    def get_rating_avg(self, obj):
        value = getattr(obj, "rating_avg", None)
        if value is None:
            return None
        return round(float(value), 1)

    def get_rating_count(self, obj):
        value = getattr(obj, "rating_count", None)
        if value is None:
            return 0
        return int(value)

    def get_profile_picture(self, obj):
        return obj.profile_picture or None

    def get_cover_image(self, obj):
        return obj.cover_image or None


class PackageSerializer(serializers.ModelSerializer):
    profile_slug = serializers.CharField(source="profile.slug", read_only=True)
    studio_name = serializers.CharField(
        source="profile.studio_name", read_only=True
    )
    cancellation_summary = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "id",
            "profile_slug",
            "studio_name",
            "title",
            "description",
            "price",
            "price_max",
            "cancellation_policy",
            "cancellation_refund_percent",
            "cancellation_refund_hours",
            "cancellation_summary",
        ]
        read_only_fields = [
            "id",
            "profile_slug",
            "studio_name",
            "cancellation_summary",
        ]

    def get_cancellation_summary(self, obj):
        return policy_summary(obj)

    def validate(self, attrs):
        price = attrs.get("price", getattr(self.instance, "price", None))
        price_max = attrs.get(
            "price_max", getattr(self.instance, "price_max", None)
        )
        if price_max is not None and price is not None and price_max < price:
            raise serializers.ValidationError(
                {"price_max": "The maximum price cannot be below the minimum"}
            )
        return attrs


class PortfolioPhotoSerializer(serializers.ModelSerializer):
    profile_slug = serializers.CharField(source="profile.slug", read_only=True)
    studio_name = serializers.CharField(
        source="profile.studio_name", read_only=True
    )
    collection_title = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioPhoto
        fields = [
            "id",
            "profile_slug",
            "studio_name",
            "collection",
            "collection_title",
            "image",
            "caption",
        ]
        read_only_fields = ["id", "profile_slug", "studio_name"]

    def get_collection_title(self, obj):
        return obj.collection.title if obj.collection else None

    def validate_collection(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        user = request.user if request else None
        if user is None or value.profile.user_id != user.id:
            raise serializers.ValidationError(
                "That collection belongs to another photographer"
            )
        return value


class PortfolioCollectionSerializer(serializers.ModelSerializer):
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioCollection
        fields = ["id", "title", "photo_count"]

    def get_photo_count(self, obj):
        return obj.photos.count()

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be empty")
        return value
