from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from clients.models import Client
from shoots.models import Shoot
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
        if new_status == BookingRequest.Status.ACCEPTED:
            self._accept(booking)
        else:
            booking.status = new_status
            booking.save(update_fields=["status"])
        return Response(self.get_serializer(booking).data)

    def _accept(self, booking):
        photographer = self.request.user
        with transaction.atomic():
            has_conflict = Shoot.objects.filter(
                client__photographer=photographer,
                date__date=booking.date.date(),
            ).exists()
            if has_conflict:
                raise ValidationError(
                    "Ya tienes una sesión reservada en esa fecha"
                )
            client, _ = Client.objects.get_or_create(
                photographer=photographer,
                user=booking.customer,
                defaults={
                    "name": (
                        booking.customer.get_full_name()
                        or booking.customer.username
                    ),
                    "email": booking.customer.email,
                    "phone": "",
                },
            )
            Shoot.objects.create(
                client=client,
                title=f"{booking.package.title} - {booking.customer.username}",
                shoot_type=booking.package.title,
                date=booking.date,
            )
            booking.status = BookingRequest.Status.ACCEPTED
            booking.save(update_fields=["status"])
