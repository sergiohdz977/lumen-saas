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
            return qs.filter(shoot__client__photographer=user)
        return qs.filter(shoot__client__user=user)


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
            return qs.filter(gallery__shoot__client__photographer=user)
        return qs.filter(gallery__shoot__client__user=user)
