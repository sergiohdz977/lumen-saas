import os
from pathlib import Path

from django.conf import settings
from django.db.models import Avg, OuterRef, Q, Subquery
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from galleries.storage import store_image
from reviews.models import Review
from users.models import User
from users.permissions import IsPhotographer
from .models import (
    Package,
    PhotographerProfile,
    PortfolioCollection,
    PortfolioPhoto,
)
from .serializers import (
    PackageSerializer,
    PhotographerProfileSerializer,
    PortfolioCollectionSerializer,
    PortfolioPhotoSerializer,
)

MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_COVER_BYTES = 4 * 1024 * 1024
MAX_PORTFOLIO_BYTES = 8 * 1024 * 1024


class PhotographerProfileViewSet(viewsets.ModelViewSet):
    """Public read + owner-only ``PATCH /api/profiles/{slug}/``.

    The router binds POST/PUT/DELETE to handlers, but ``http_method_names``
    blocks them (405) before any handler runs, so create/delete stay
    unavailable: a profile is created with the user and can only be edited
    by its own photographer. Anonymous POST/PUT/DELETE are answered before
    permission checks, which keeps the read-only 405 contract for them.
    """

    serializer_class = PhotographerProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = PhotographerProfile.objects.all()
    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "metadata"):
            return [AllowAny()]
        if self.action == "partial_update":
            return [IsAuthenticated(), IsPhotographer()]
        # create / update / destroy: unreachable, answered with 405.
        return [AllowAny()]

    def get_queryset(self):
        if self.action in ("list", "retrieve"):
            qs = PhotographerProfile.objects.filter(is_published=True)
            qs = qs.annotate(
                rating_avg=Subquery(
                    Review.objects.filter(photographer_id=OuterRef("user_id"))
                    .values("photographer_id")
                    .annotate(avg=Avg("rating"))
                    .values("avg")[:1]
                )
            )
            city = self.request.query_params.get("city", "").strip()
            if city:
                qs = qs.filter(city__icontains=city)
            specialty = self.request.query_params.get("specialty", "").strip()
            if specialty:
                qs = qs.filter(specialties__icontains=specialty)
            min_rating = self.request.query_params.get(
                "min_rating", ""
            ).strip()
            if min_rating:
                try:
                    threshold = float(min_rating)
                except ValueError:
                    raise ValidationError(
                        {"min_rating": "Must be a number"}
                    )
                rated = (
                    Review.objects.values("photographer_id")
                    .annotate(avg=Avg("rating"))
                    .filter(avg__gte=threshold)
                    .values_list("photographer_id", flat=True)
                )
                qs = qs.filter(user_id__in=rated)
            max_price = self.request.query_params.get("max_price", "").strip()
            if max_price:
                try:
                    ceiling = float(max_price)
                except ValueError:
                    raise ValidationError({"max_price": "Must be a number"})
                affordable = Package.objects.filter(
                    price__lte=ceiling
                ).values_list("profile_id", flat=True)
                qs = qs.filter(pk__in=affordable)
            return qs
        # Writes only reach the caller's own profile (published or not).
        user = self.request.user
        if user.is_authenticated and user.role == User.ROLE_PHOTOGRAPHER:
            return PhotographerProfile.objects.filter(user=user)
        return PhotographerProfile.objects.none()


class ProfileOwnedViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated(), IsPhotographer()]

    def get_queryset(self):
        qs = self.queryset.select_related("profile")
        user = self.request.user
        if self.action == "retrieve":
            return qs.filter(profile__is_published=True)
        if self.action == "list":
            # Public list: published catalogs. Photographers also see their
            # own items so an unpublished studio can still manage them.
            if user.is_authenticated and user.role == User.ROLE_PHOTOGRAPHER:
                qs = qs.filter(
                    Q(profile__is_published=True) | Q(profile__user=user)
                )
            else:
                qs = qs.filter(profile__is_published=True)
            profile_slug = self.request.query_params.get("profile")
            if profile_slug:
                qs = qs.filter(profile__slug=profile_slug)
            return qs
        if user.is_authenticated and user.role == User.ROLE_PHOTOGRAPHER:
            return qs.filter(profile__user=user)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, "profile"):
            raise ValidationError(
                "Create your photographer profile before adding items"
            )
        serializer.save(profile=user.profile)


class PackageViewSet(ProfileOwnedViewSet):
    serializer_class = PackageSerializer
    queryset = Package.objects.all()


class PortfolioPhotoViewSet(ProfileOwnedViewSet):
    serializer_class = PortfolioPhotoSerializer
    queryset = PortfolioPhoto.objects.all()


class PortfolioCollectionViewSet(ProfileOwnedViewSet):
    serializer_class = PortfolioCollectionSerializer
    queryset = PortfolioCollection.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        title = serializer.validated_data["title"]
        if PortfolioCollection.objects.filter(
            profile__user=user, title=title
        ).exists():
            raise ValidationError(
                {"title": "You already have a collection with this name"}
            )
        super().perform_create(serializer)


class ProfilePictureView(APIView):
    """``POST /api/profiles/picture/`` - JWT upload of the own avatar.

    The image goes through ``store_image`` (Cloudinary when credentials
    are set, local media otherwise) and the resulting URL is saved on the
    caller's profile. Returns ``{"profile_picture": <url>}``.

    ``DELETE /api/profiles/picture/`` clears the avatar and discards the
    stored file (best effort). Returns ``{"profile_picture": null}``.
    """

    permission_classes = [IsAuthenticated, IsPhotographer]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise ValidationError(
                {"profile_picture": "Photographer profile not found"}
            )
        image = request.FILES.get("profile_picture")
        if image is None:
            raise ValidationError(
                {"profile_picture": "No image received"}
            )
        if not (image.content_type or "").startswith("image/"):
            raise ValidationError(
                {"profile_picture": "Only images are allowed"}
            )
        if image.size > MAX_AVATAR_BYTES:
            raise ValidationError(
                {"profile_picture": "Image must be 2 MB or smaller"}
            )
        url = store_image(image, folder="lumen/avatars")
        profile.profile_picture = url
        profile.save(update_fields=["profile_picture"])
        return Response({"profile_picture": url})

    def delete(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise ValidationError(
                {"profile_picture": "Photographer profile not found"}
            )
        if profile.profile_picture:
            self._discard_file(profile.profile_picture)
            profile.profile_picture = ""
            profile.save(update_fields=["profile_picture"])
        return Response({"profile_picture": None})

    @staticmethod
    def _discard_file(url):
        """Best-effort removal of the stored avatar file."""
        try:
            if url.startswith(settings.MEDIA_URL):
                relative = url.removeprefix(settings.MEDIA_URL)
                if not relative.startswith("lumen/avatars/"):
                    return
                path = Path(settings.MEDIA_ROOT) / relative
                if path.is_file():
                    path.unlink()
            elif settings.CLOUDINARY_CLOUD_NAME and "/lumen/avatars/" in url:
                import cloudinary.uploader

                public_id = url.split("/upload/", 1)[-1]
                public_id = public_id.split("/", 1)[-1]
                public_id = os.path.splitext(public_id)[0]
                cloudinary.uploader.destroy(public_id)
        except Exception:
            pass


class PortfolioPhotoUploadView(APIView):
    """``POST /api/portfolio-photos/upload/`` - JWT upload of a local file.

    Stores the image via ``store_image`` into ``lumen/portfolio`` and
    creates the ``PortfolioPhoto`` for the caller's profile. Accepts
    optional ``caption`` and ``collection`` fields. Returns the created
    photo (201).
    """

    permission_classes = [IsAuthenticated, IsPhotographer]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise ValidationError(
                {"image": "Create your photographer profile first"}
            )
        image = request.FILES.get("image")
        if image is None:
            raise ValidationError({"image": "No image received"})
        if not (image.content_type or "").startswith("image/"):
            raise ValidationError({"image": "Only images are allowed"})
        if image.size > MAX_PORTFOLIO_BYTES:
            raise ValidationError(
                {"image": "Image must be 8 MB or smaller"}
            )
        caption = (request.data.get("caption") or "").strip()[:200]
        collection = None
        collection_raw = request.data.get("collection") or None
        if collection_raw:
            collection = PortfolioCollection.objects.filter(
                pk=collection_raw, profile=profile
            ).first()
            if collection is None:
                raise ValidationError(
                    {"collection": "Collection not found"}
                )
        url = store_image(image, folder="lumen/portfolio")
        photo = PortfolioPhoto.objects.create(
            profile=profile,
            collection=collection,
            image=url,
            caption=caption,
        )
        serializer = PortfolioPhotoSerializer(
            photo, context={"request": request}
        )
        return Response(serializer.data, status=201)


class ProfileCoverView(APIView):
    """``POST /api/profiles/cover/`` - JWT upload of the own cover banner.

    Same contract as ``ProfilePictureView`` but stores the profile cover:
    the image goes through ``store_image`` into ``lumen/covers`` and the
    resulting URL is saved as ``cover_image``. Returns
    ``{"cover_image": <url>}``. ``DELETE`` clears the banner.
    """

    permission_classes = [IsAuthenticated, IsPhotographer]

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise ValidationError({"cover_image": "Photographer profile not found"})
        image = request.FILES.get("cover_image")
        if image is None:
            raise ValidationError({"cover_image": "No image received"})
        if not (image.content_type or "").startswith("image/"):
            raise ValidationError({"cover_image": "Only images are allowed"})
        if image.size > MAX_COVER_BYTES:
            raise ValidationError({"cover_image": "Image must be 4 MB or smaller"})
        url = store_image(image, folder="lumen/covers")
        profile.cover_image = url
        profile.save(update_fields=["cover_image"])
        return Response({"cover_image": url})

    def delete(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            raise ValidationError({"cover_image": "Photographer profile not found"})
        if profile.cover_image:
            self._discard_file(profile.cover_image)
            profile.cover_image = ""
            profile.save(update_fields=["cover_image"])
        return Response({"cover_image": None})

    @staticmethod
    def _discard_file(url):
        """Best-effort removal of the stored cover file."""
        try:
            if url.startswith(settings.MEDIA_URL):
                relative = url.removeprefix(settings.MEDIA_URL)
                if not relative.startswith("lumen/covers/"):
                    return
                path = Path(settings.MEDIA_ROOT) / relative
                if path.is_file():
                    path.unlink()
            elif settings.CLOUDINARY_CLOUD_NAME and "/lumen/covers/" in url:
                import cloudinary.uploader

                public_id = url.split("/upload/", 1)[-1]
                public_id = public_id.split("/", 1)[-1]
                public_id = os.path.splitext(public_id)[0]
                cloudinary.uploader.destroy(public_id)
        except Exception:
            pass
