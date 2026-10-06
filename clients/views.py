from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsPhotographer
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, IsPhotographer]

    def get_queryset(self):
        return Client.objects.filter(photographer=self.request.user)

    def perform_create(self, serializer):
        serializer.save(photographer=self.request.user)
