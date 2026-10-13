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

logger = logging.getLogger(__name__)

THUMBNAIL_MAX_WIDTH = 400


def _open_image(source):
    """Open an image from a local media path or a remote (Cloudinary) URL."""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=30) as response:
            return Image.open(BytesIO(response.read()))
    relative = source.removeprefix(settings.MEDIA_URL)
    return Image.open(Path(settings.MEDIA_ROOT) / relative)


@shared_task
def generate_thumbnail(photo_id):
    """Resize the photo to a small JPEG and store its URL on Photo.thumbnail.

    Runs in the background (Celery worker). Never raises: a broken image
    must not break the upload pipeline, so failures are only logged.
    """
    photo = Photo.objects.filter(pk=photo_id).first()
    if photo is None or not photo.image:
        return None
    try:
        with _open_image(photo.image) as original:
            image = original.convert("RGB")
            image.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_WIDTH))
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
    except Exception:
        logger.exception("Thumbnail generation failed for photo %s", photo_id)
        return None

    upload = SimpleUploadedFile(
        f"thumbnail-{uuid.uuid4().hex}.jpg",
        buffer.getvalue(),
        content_type="image/jpeg",
    )
    photo.thumbnail = store_image(upload, folder="lumen/thumbnails")
    photo.save(update_fields=["thumbnail"])
    return photo.thumbnail


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
    if not to_email:
        return None
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
    return to_email
