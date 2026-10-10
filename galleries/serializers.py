from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from shoots.models import Shoot
from .models import Gallery, Photo


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
    client_username = serializers.CharField(
        source="shoot.client.user.username", read_only=True
    )

    class Meta:
        model = Gallery
        fields = ["id", "shoot", "shoot_title", "client_username", "created_at"]
        read_only_fields = ["id", "shoot_title", "client_username", "created_at"]

    def validate_shoot(self, value):
        if value.client.photographer != self.context["request"].user:
            raise serializers.ValidationError("Esa sesión no es tuya")
        return value


class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ["id", "gallery", "image", "caption", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_gallery(self, value):
        if value.shoot.client.photographer != self.context["request"].user:
            raise serializers.ValidationError(
                "No puedes añadir fotos a esta galería"
            )
        return value
