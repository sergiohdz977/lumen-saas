from django.conf import settings
from django.db import models

SHARE_SALT = "galleries.share"


class Gallery(models.Model):
    shoot = models.OneToOneField(
        "shoots.Shoot",
        on_delete=models.CASCADE,
        related_name="gallery",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Galeria de {self.shoot.title}"

    
class Photo(models.Model):
    gallery = models.ForeignKey(
        Gallery,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.URLField(max_length=500, blank=True)
    thumbnail = models.URLField(max_length=500, blank=True)
    caption = models.CharField(max_length=200, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.caption or f"Foto #{self.pk}"


class Favorite(models.Model):
    photo = models.ForeignKey(
        Photo, on_delete=models.CASCADE, related_name="favorites"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_photos",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["photo", "user"],
                name="unique_favorite_photo_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} favorito foto #{self.photo_id}"
