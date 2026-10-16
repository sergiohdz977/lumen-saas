import logging
import urllib.request
import uuid
from io import BytesIO
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import send_mail
from django.core import signing
from PIL import Image

from .models import Gallery, Photo, SHARE_SALT
from .storage import store_image
from notifications.services import notify

logger = logging.getLogger(__name__)

# (model field, storage folder, max width in px, JPEG quality)
PHOTO_VARIANTS = (
    ("thumbnail", "lumen/thumbnails", 400, 85),
    ("preview", "lumen/previews", 1280, 85),
)


def _open_image(source):
    """Open an image from a local media path or a remote (Cloudinary) URL."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return Image.open(BytesIO(response.read()))
    relative = source.removeprefix(settings.MEDIA_URL)
    return Image.open(Path(settings.MEDIA_ROOT) / relative)


@shared_task
def generate_photo_variants(photo_id):
    """Build the thumbnail and the HD preview, then store their URLs.

    The original file is opened once and resized twice. Runs in the
    background (Celery worker). Never raises: a broken image must not
    break the upload pipeline, so failures are only logged.
    """
    photo = Photo.objects.filter(pk=photo_id).first()
    if photo is None or not photo.image:
        return None
    try:
        with _open_image(photo.image) as original:
            rgb = original.convert("RGB")
            urls = {}
            for field, folder, max_width, quality in PHOTO_VARIANTS:
                image = rgb.copy()
                image.thumbnail((max_width, max_width))
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=quality)
                upload = SimpleUploadedFile(
                    f"{field}-{uuid.uuid4().hex}.jpg",
                    buffer.getvalue(),
                    content_type="image/jpeg",
                )
                urls[field] = store_image(upload, folder=folder)
    except Exception:
        logger.exception(
            "Photo variants generation failed for photo %s", photo_id
        )
        return None

    Photo.objects.filter(pk=photo.pk).update(**urls)
    return urls


@shared_task
def gallery_ready_email(gallery_id):
    """Email the customer when a gallery is created (photos delivered)."""
    gallery = (
        Gallery.objects.select_related("shoot__client", "shoot__client__user")
        .filter(pk=gallery_id)
        .first()
    )
    if gallery is None:
        return None
    client = gallery.shoot.client
    to_email = client.user.email if client.user else client.email
    if to_email:
        token = signing.dumps(str(gallery.pk), salt=SHARE_SALT)
        link = f"{settings.SITE_URL}/api/gallery-view/{token}/"
        send_mail(
            subject="Tus fotos están listas",
            message=(
                f"Hola {client.name},\n\n"
                f'Tus fotos de "{gallery.shoot.title}" ya están disponibles.\n'
                f"Enlace privado (válido 7 días): {link}\n\n"
                "Lumen\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
        )
    if client.user:
        notify(
            client.user,
            "Tus fotos estan listas",
            f'Las fotos de "{gallery.shoot.title}" ya estan disponibles',
        )
    return to_email
