from django.conf import settings
from django.db import models


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        ACCEPTED = "accepted", "Aceptada"
        REJECTED = "rejected", "Rechazada"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="booking_requests",
    )
    package = models.ForeignKey(
        "profiles.Package",
        on_delete=models.CASCADE,
        related_name="booking_requests",
    )
    date = models.DateTimeField()
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} → {self.package} ({self.status})"
