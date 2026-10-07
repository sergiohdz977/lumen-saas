from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import PhotographerProfile
from .serializers import PhotographerProfileSerializer


class PhotographerProfileViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PhotographerProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = PhotographerProfile.objects.filter(is_published=True)
