import os
import uuid

from django.conf import settings


def store_image(image_file):
    """Send an uploaded image to Cloudinary, or to local media as fallback.

    Returns the URL where the image can be read. Uses Cloudinary only when
    credentials are configured (.env); tests always use local storage.
    """
    if settings.CLOUDINARY_CLOUD_NAME:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            image_file,
            folder="lumen/photos",
            resource_type="image",
        )
        return result["secure_url"]

    extension = os.path.splitext(image_file.name)[1].lower()
    name = f"photos/{uuid.uuid4().hex}{extension}"
    destination = os.path.join(settings.MEDIA_ROOT, name)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "wb") as handle:
        for chunk in image_file.chunks():
            handle.write(chunk)
    return settings.MEDIA_URL + name