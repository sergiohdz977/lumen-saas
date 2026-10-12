from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from shoots.models import Shoot
from .models import Gallery, Photo
from .storage import store_image
from .tasks import generate_thumbnail


class GallerySerializer(serializers.ModelSerializer):
    shoot = serializers.PrimaryKeyRelatedField(
        queryset=Shoot.objects.all(),
        validators=[
            UniqueValidator(
                queryset=Gallery.objects.all(),
                message="Esta sesión ya tiene una galería",
            )
        ],
    )
    shoot_title = serializers.CharField(
        source="shoot.title", read_only=True
    )
    client_username = serializers.SerializerMethodField()

    class Meta:
        model = Gallery
        fields = ["id", "shoot", "shoot_title", "client_username", "created_at"]
        read_only_fields = ["id", "shoot_title", "client_username", "created_at"]

    def get_client_username(self, obj):
        user = obj.shoot.client.user
        return user.username if user else None

    def validate_shoot(self, value):
        if value.client.photographer != self.context["request"].user:
            raise serializers.ValidationError("Esa sesión no es tuya")
        return value


class PhotoSerializer(serializers.ModelSerializer):
    image = serializers.FileField()

    class Meta:
        model = Photo
        fields = ["id", "gallery", "image", "thumbnail", "caption", "created_at"]
        read_only_fields = ["id", "thumbnail", "created_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["image"] = instance.image
        return data

    def create(self, validated_data):
        image_file = validated_data.pop("image")
        photo = Photo.objects.create(
            image=store_image(image_file), **validated_data
        )
        generate_thumbnail.delay(photo.pk)
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
            generate_thumbnail.delay(instance.pk)
        return instance

    def validate_gallery(self, value):
        if value.shoot.client.photographer != self.context["request"].user:
            raise serializers.ValidationError(
                "No puedes añadir fotos a esta galería"
            )
        return value
