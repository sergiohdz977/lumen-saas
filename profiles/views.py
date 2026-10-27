from django.db.models import Q
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
            city = self.request.query_params.get("city", "").strip()
            if city:
                qs = qs.filter(city__icontains=city)
            specialty = self.request.query_params.get("specialty", "").strip()
            if specialty:
                qs = qs.filter(specialties__icontains=specialty)
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
