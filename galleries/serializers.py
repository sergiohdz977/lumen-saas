from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from payments.services import booking_is_fully_paid
from shoots.models import Shoot
from users.models import User
from .limits import ensure_gallery_quota, ensure_photo_quota
from .models import Favorite, Gallery, Photo
from .storage import store_image
from .tasks import generate_photo_variants, gallery_ready_email


class GallerySerializer(serializers.ModelSerializer):
    shoot = serializers.PrimaryKeyRelatedField(
        queryset=Shoot.objects.all(),
        validators=[
            UniqueValidator(
                queryset=Gallery.objects.all(),
                message="This shoot already has a gallery",
            )
        ],
    )
    shoot_title = serializers.CharField(
        source="shoot.title", read_only=True
    )
    client_username = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()
    booking_status = serializers.SerializerMethodField()
    fully_paid = serializers.SerializerMethodField()

    class Meta:
        model = Gallery
        fields = [
            "id",
            "shoot",
            "shoot_title",
            "client_username",
            "photo_count",
            "booking_status",
            "fully_paid",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "shoot_title",
            "client_username",
            "photo_count",
            "booking_status",
            "fully_paid",
            "created_at",
        ]

    def get_client_username(self, obj):
        user = obj.shoot.client.user
        return user.username if user else None

    def get_photo_count(self, obj):
        if hasattr(obj, "photo_count"):
            return obj.photo_count
        return obj.photos.count()

    def get_booking_status(self, obj):
        booking = getattr(obj.shoot, "booking", None)
        return booking.status if booking else None

    def get_fully_paid(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            if user.role == User.ROLE_PHOTOGRAPHER:
                return True
        booking = getattr(obj.shoot, "booking", None)
        return booking_is_fully_paid(booking)

    def validate_shoot(self, value):
        if value.client.photographer != self.context["request"].user:
            raise serializers.ValidationError("That shoot does not belong to you")
        ensure_gallery_quota(self.context["request"].user)
        return value

    def create(self, validated_data):
        gallery = super().create(validated_data)
        gallery_ready_email.delay(gallery.pk)
        return gallery


class PhotoSerializer(serializers.ModelSerializer):
    image = serializers.FileField(
        error_messages={
            "required": "The image is required",
            "empty": "The file is empty",
        }
    )

    class Meta:
        model = Photo
        fields = [
            "id", "gallery", "image", "thumbnail", "preview",
            "caption", "download_count", "light_download_count", "created_at",
        ]
        read_only_fields = [
            "id", "thumbnail", "preview",
            "download_count", "light_download_count", "created_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["image"] = instance.image
        if not self._viewer_can_download_original(instance):
            data["image"] = instance.preview or instance.thumbnail or ""
        return data

    def _viewer_can_download_original(self, instance):
        """Photographers and paid customers get the original file."""
        request = self.context.get("request")
        if request is None:
            return True
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            if user.role == User.ROLE_PHOTOGRAPHER:
                return True
        shoot = instance.gallery.shoot
        cache = self.context.setdefault("_fully_paid_by_shoot", {})
        if shoot.pk not in cache:
            cache[shoot.pk] = booking_is_fully_paid(
                getattr(shoot, "booking", None)
            )
        return cache[shoot.pk]

    def create(self, validated_data):
        image_file = validated_data.pop("image")
        photo = Photo.objects.create(
            image=store_image(image_file), **validated_data
        )
        generate_photo_variants.delay(photo.pk)
        return photo

    def update(self, instance, validated_data):
        image_file = validated_data.pop("image", None)
        if image_file:
            instance.image = store_image(image_file)
        for field in ("gallery", "caption"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        if image_file:
            generate_photo_variants.delay(instance.pk)
        return instance

    def validate_gallery(self, value):
        if value.shoot.client.photographer != self.context["request"].user:
            raise serializers.ValidationError(
                "You cannot add photos to this gallery"
            )
        return value

    def validate(self, data):
        # Only new photos consume quota; updates never add one.
        if self.instance is None:
            ensure_photo_quota(self.context["request"].user)
        return data


class FavoriteSerializer(serializers.ModelSerializer):
    photo = serializers.PrimaryKeyRelatedField(queryset=Photo.objects.all())
    photo_caption = serializers.CharField(
        source="photo.caption", read_only=True
    )
    photo_thumbnail = serializers.CharField(
        source="photo.thumbnail", read_only=True
    )
    customer_username = serializers.CharField(
        source="user.username", read_only=True
    )

    class Meta:
        model = Favorite
        fields = [
            "id", "photo", "photo_caption", "photo_thumbnail",
            "customer_username", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_photo(self, value):
        request = self.context["request"]
        if value.gallery.shoot.client.user != request.user:
            raise serializers.ValidationError("You cannot favorite that photo")
        if Favorite.objects.filter(photo=value, user=request.user).exists():
            raise serializers.ValidationError(
                "This photo is already in your favorites"
            )
        return value
