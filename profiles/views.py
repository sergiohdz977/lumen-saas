from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from users.models import User
from users.permissions import IsPhotographer
from .models import Package, PhotographerProfile, PortfolioPhoto
from .serializers import (
    PackageSerializer,
    PhotographerProfileSerializer,
    PortfolioPhotoSerializer,
)


class PhotographerProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PhotographerProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = PhotographerProfile.objects.filter(is_published=True)


class ProfileOwnedViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAuthenticated(), IsPhotographer()]

    def get_queryset(self):
        qs = self.queryset.select_related("profile")
        if self.action in ("list", "retrieve"):
            qs = qs.filter(profile__is_published=True)
            if self.action == "list":
                profile_slug = self.request.query_params.get("profile")
                if profile_slug:
                    qs = qs.filter(profile__slug=profile_slug)
            return qs
        user = self.request.user
        if user.is_authenticated and user.role == User.ROLE_PHOTOGRAPHER:
            return qs.filter(profile__user=user)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, "profile"):
            raise ValidationError(
                "Crea tu perfil de fotógrafo antes de añadir elementos"
            )
        serializer.save(profile=user.profile)


class PackageViewSet(ProfileOwnedViewSet):
    serializer_class = PackageSerializer
    queryset = Package.objects.all()


class PortfolioPhotoViewSet(ProfileOwnedViewSet):
    serializer_class = PortfolioPhotoSerializer
    queryset = PortfolioPhoto.objects.all()
