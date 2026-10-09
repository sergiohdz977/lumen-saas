from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.models import User
from users.permissions import IsCustomer, IsPhotographer
from .models import BookingRequest
from .serializers import BookingRequestSerializer


class BookingRequestViewSet(viewsets.ModelViewSet):
    serializer_class = BookingRequestSerializer
    queryset = BookingRequest.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsCustomer()]
        if self.action in ("accept", "reject"):
            return [IsAuthenticated(), IsPhotographer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related(
            "package__profile", "customer"
        )
        if not user.is_authenticated:
            return qs.none()
        if user.role == User.ROLE_CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(package__profile__user=user)

    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._transition(request, BookingRequest.Status.ACCEPTED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition(request, BookingRequest.Status.REJECTED)

    def _transition(self, request, new_status):
        booking = self.get_object()
        if booking.status != BookingRequest.Status.PENDING:
            raise ValidationError(
                "Solo se pueden gestionar solicitudes pendientes"
            )
        booking.status = new_status
        booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)
