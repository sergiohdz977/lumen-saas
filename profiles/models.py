from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class PhotographerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    studio_name = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(max_length=140, unique=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    specialties = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.studio_name or self.user.username)
            slug = base
            number = 2
            while PhotographerProfile.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{number}"
                number += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.studio_name or self.user.username


class Package(models.Model):
    profile = models.ForeignKey(
        PhotographerProfile,
        on_delete=models.CASCADE,
        related_name="packages",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    def __str__(self):
        return self.title


class PortfolioPhoto(models.Model):
    profile = models.ForeignKey(
        PhotographerProfile,
        on_delete=models.CASCADE,
        related_name="portfolio_photos",
    )
    image = models.URLField(max_length=500, blank=True)
    caption = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.caption or f"Foto #{self.pk}"
