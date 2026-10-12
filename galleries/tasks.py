import logging
import urllib.request
import uuid
from io import BytesIO
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from .models import Photo
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
