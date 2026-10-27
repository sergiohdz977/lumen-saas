from django.conf import settings
from django.core import signing
from django.db.models import Count, F
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from notifications.services import notify
from payments.services import booking_is_fully_paid
from users.models import User
from users.permissions import IsCustomer, IsPhotographer
from .models import Favorite, Gallery, Photo, SHARE_SALT
from .serializers import FavoriteSerializer, GallerySerializer, PhotoSerializer


class GalleryViewSet(viewsets.ModelViewSet):
    serializer_class = GallerySerializer
    permission_classes = [IsAuthenticated]
    queryset = Gallery.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsPhotographer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Gallery.objects.none()
        qs = Gallery.objects.select_related(
            "shoot__client", "shoot__client__user", "shoot__booking"
        ).annotate(photo_count=Count("photos"))
        if user.role == User.ROLE_PHOTOGRAPHER:
            qs = qs.filter(shoot__client__photographer=user)
        else:
            qs = qs.filter(shoot__client__user=user)
        if self.action == "list":
            shoot_id = self.request.query_params.get("shoot")
            if shoot_id:
                qs = qs.filter(shoot_id=shoot_id)
        return qs

    @action(detail=True, methods=["post"], url_path="share-link")
    def share_link(self, request, pk=None):
        gallery = self.get_object()
        token = signing.dumps(str(gallery.pk), salt=SHARE_SALT)
        url = request.build_absolute_uri(f"/api/gallery-view/{token}/")
        return Response(
            {
                "url": url,
                "expires_in_days": settings.GALLERY_SHARE_MAX_AGE // 86400,
            }
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def gallery_view(request, token):
    try:
        gallery_id = signing.loads(
            token,
            salt=SHARE_SALT,
            max_age=settings.GALLERY_SHARE_MAX_AGE,
        )
    except signing.SignatureExpired:
        raise NotFound("The link has expired")
    except signing.BadSignature:
        raise NotFound("The link is not valid")

    gallery = get_object_or_404(
        Gallery.objects.select_related(
            "shoot__client", "shoot__client__user", "shoot__booking"
        ),
        pk=gallery_id,
    )
    context = {"request": request}
    return Response(
        {
            "gallery": GallerySerializer(gallery, context=context).data,
            "photos": PhotoSerializer(
                gallery.photos.all(), many=True, context=context
            ).data,
        }
    )


class PhotoViewSet(viewsets.ModelViewSet):
    serializer_class = PhotoSerializer
    permission_classes = [IsAuthenticated]
    queryset = Photo.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve", "download"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsPhotographer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Photo.objects.none()
        qs = Photo.objects.select_related(
            "gallery__shoot__client", "gallery__shoot__booking"
        )
        if user.role == User.ROLE_PHOTOGRAPHER:
            qs = qs.filter(gallery__shoot__client__photographer=user)
        else:
            qs = qs.filter(gallery__shoot__client__user=user)
        if self.action == "list":
            gallery_id = self.request.query_params.get("gallery")
            if gallery_id:
                qs = qs.filter(gallery_id=gallery_id)
        return qs

    @action(detail=True, methods=["post"])
    def download(self, request, pk=None):
        photo = self.get_object()
        version = request.data.get("version", "original")
        if version == "light":
            counter = "light_download_count"
        elif version == "original":
            if request.user.role != User.ROLE_PHOTOGRAPHER:
                booking = getattr(photo.gallery.shoot, "booking", None)
                if not booking_is_fully_paid(booking):
                    raise PermissionDenied(
                        "Complete the payment to download photos "
                        "in high quality."
                    )
            counter = "download_count"
        else:
            raise ValidationError("Invalid version: use 'light' or 'original'")
        Photo.objects.filter(pk=photo.pk).update(**{counter: F(counter) + 1})
        photo.refresh_from_db(
            fields=["download_count", "light_download_count"]
        )
        return Response(
            {
                "download_count": photo.download_count,
                "light_download_count": photo.light_download_count,
            }
        )


class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    queryset = Favorite.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCustomer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Favorite.objects.none()
        qs = Favorite.objects.select_related(
            "photo", "user", "photo__gallery__shoot__client"
        )
        if user.role == User.ROLE_PHOTOGRAPHER:
            qs = qs.filter(photo__gallery__shoot__client__photographer=user)
        else:
            qs = qs.filter(user=user)
        photo_id = self.request.query_params.get("photo")
        if photo_id:
            qs = qs.filter(photo_id=photo_id)
        return qs

    def perform_create(self, serializer):
        favorite = serializer.save(user=self.request.user)
        owner = favorite.photo.gallery.shoot.client.photographer
        if owner and owner.pk != self.request.user.pk:
            notify(
                owner,
                "New favorite",
                (
                    f"{self.request.user.username} favorited a photo from "
                    f"'{favorite.photo.gallery.shoot.title}'."
                ),
            )
