from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsPhotographer
from .models import Shoot
from .serializers import ShootSerializer


class ShootViewSet(viewsets.ModelViewSet):
    serializer_class = ShootSerializer
    permission_classes = [IsAuthenticated, IsPhotographer]

    def get_queryset(self):
        return Shoot.objects.filter(
            client__photographer=self.request.user
        ).select_related("client")

    def perform_create(self, serializer):
        serializer.save(status=Shoot.Status.BOOKED)
