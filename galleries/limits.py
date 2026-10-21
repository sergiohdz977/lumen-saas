from django.conf import settings
from rest_framework.exceptions import ValidationError

from .models import Gallery, Photo


def _is_pro(user):
    profile = getattr(user, "profile", None)
    if profile is None:
        return False
    return profile.plan == "pro"


def ensure_gallery_quota(user):
    """Free plan: at most FREE_TIER_GALLERIES galleries."""
    if _is_pro(user):
        return
    used = Gallery.objects.filter(
        shoot__client__photographer=user
    ).count()
    if used >= settings.FREE_TIER_GALLERIES:
        raise ValidationError(
            f"The Free plan allows up to "
            f"{settings.FREE_TIER_GALLERIES} galleries. "
            "Upgrade to Pro for unlimited galleries."
        )


def ensure_photo_quota(user):
    """Free plan: at most FREE_TIER_PHOTOS photos in total."""
    if _is_pro(user):
        return
    used = Photo.objects.filter(
        gallery__shoot__client__photographer=user
    ).count()
    if used >= settings.FREE_TIER_PHOTOS:
        raise ValidationError(
            f"The Free plan allows up to "
            f"{settings.FREE_TIER_PHOTOS} photos. "
            "Upgrade to Pro for unlimited storage."
        )
