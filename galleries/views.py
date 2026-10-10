from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from users.models import User
from users.permissions import IsPhotographer
from .models import Gallery, Photo
from .serializers import GallerySerializer, PhotoSerializer


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
            "shoot__client", "shoot__client__user"
        )
        if user.role == User.ROLE_PHOTOGRAPHER:
            qs = qs.filter(shoot__client__photographer=user)
        else:
            qs = qs.filter(shoot__client__user=user)
        if self.action == "list":
            shoot_id = self.request.query_params.get("shoot")
            if shoot_id:
                qs = qs.filter(shoot_id=shoot_id)
        return qs


class PhotoViewSet(viewsets.ModelViewSet):
    serializer_class = PhotoSerializer
    permission_classes = [IsAuthenticated]
    queryset = Photo.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsPhotographer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Photo.objects.none()
        qs = Photo.objects.select_related("gallery__shoot__client")
        if user.role == User.ROLE_PHOTOGRAPHER:
            qs = qs.filter(gallery__shoot__client__photographer=user)
        else:
            qs = qs.filter(gallery__shoot__client__user=user)
        if self.action == "list":
            gallery_id = self.request.query_params.get("gallery")
            if gallery_id:
                qs = qs.filter(gallery_id=gallery_id)
        return qs
