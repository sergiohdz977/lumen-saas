from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class PhotographerProfile(models.Model):
    PLAN_FREE = "free"
    PLAN_PRO = "pro"
    PLAN_CHOICES = [
        (PLAN_FREE, "Free"),
        (PLAN_PRO, "Pro"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    studio_name = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(max_length=140, unique=True)
    # Cloudinary (or local media as fallback) URL; empty when not set.
    profile_picture = models.URLField(max_length=500, blank=True)
    bio = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    specialties = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_published = models.BooleanField(default=False)
    # Stripe Connect: where the deposits of this photographer go.
    stripe_account_id = models.CharField(max_length=255, blank=True, default="")
    stripe_onboarded = models.BooleanField(default=False)
    # Stripe subscription: the photographer's own Pro plan.
    plan = models.CharField(
        max_length=10, choices=PLAN_CHOICES, default=PLAN_FREE
    )
    stripe_customer_id = models.CharField(
        max_length=255, blank=True, default=""
    )
    subscription_id = models.CharField(
        max_length=255, blank=True, default=""
    )
    # Public profile extras (About Me).
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    languages = models.CharField(max_length=200, blank=True)
    equipment = models.TextField(blank=True)
    # Banner shown behind the avatar on the public profile.
    cover_image = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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
    class CancellationPolicy(models.TextChoices):
        FLEXIBLE = "flexible", "Flexible"
        MODERATE = "moderate", "Moderate"
        STRICT = "strict", "Strict"
        CUSTOM = "custom", "Custom"

    profile = models.ForeignKey(
        PhotographerProfile,
        on_delete=models.CASCADE,
        related_name="packages",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    # Starting price. ``price_max`` turns the package into a range.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    price_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    cancellation_policy = models.CharField(
        max_length=20,
        choices=CancellationPolicy.choices,
        default=CancellationPolicy.MODERATE,
    )
    # Only used when cancellation_policy is CUSTOM: a client cancelling at
    # least ``cancellation_refund_hours`` before the shoot gets back
    # ``cancellation_refund_percent`` of the deposit.
    cancellation_refund_percent = models.PositiveSmallIntegerField(
        default=100,
        validators=[MaxValueValidator(100)],
    )
    cancellation_refund_hours = models.PositiveIntegerField(default=48)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title


class PortfolioCollection(models.Model):
    profile = models.ForeignKey(
        PhotographerProfile,
        on_delete=models.CASCADE,
        related_name="portfolio_collections",
    )
    title = models.CharField(max_length=100)

    class Meta:
        ordering = ["id"]
        unique_together = [["profile", "title"]]

    def __str__(self):
        return self.title


class PortfolioPhoto(models.Model):
    profile = models.ForeignKey(
        PhotographerProfile,
        on_delete=models.CASCADE,
        related_name="portfolio_photos",
    )
    collection = models.ForeignKey(
        PortfolioCollection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="photos",
    )
    image = models.URLField(max_length=500, blank=True)
    caption = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.caption or f"Foto #{self.pk}"

