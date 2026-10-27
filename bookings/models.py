from django.conf import settings
from django.db import models
from django.utils import timezone


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        ACCEPTED_PENDING_DEPOSIT = (
            "accepted_pending_deposit",
            "Accepted, awaiting deposit",
        )
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

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
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
    )
    deposit_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} → {self.package} ({self.status})"

    @property
    def deposit_deadline_passed(self):
        return (
            self.deposit_deadline is not None
            and timezone.now() >= self.deposit_deadline
        )
