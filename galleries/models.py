from django.db import models


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
    caption = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.caption or f"Foto #{self.pk}"
