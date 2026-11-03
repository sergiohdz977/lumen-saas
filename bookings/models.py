from django.conf import settings
from django.db import models
from django.utils import timezone


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        ACCEPTED = "accepted", "Accepted"
        COMPLETED = "completed", "Completed"
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
    event_location = models.CharField(max_length=255, blank=True)
    event_time = models.TimeField(null=True, blank=True)
    event_notes = models.TextField(blank=True)
    message = models.TextField(blank=True)
    final_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    deposit_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer} → {self.package} ({self.status})"

    @property
    def effective_price(self):
        """Price the customer pays: the photographer's offer if there is one."""
        if self.final_price is not None:
            return self.final_price
        return self.package.price

    @property
    def deposit_deadline_passed(self):
        return (
            self.deposit_deadline is not None
            and timezone.now() >= self.deposit_deadline
        )


class Message(models.Model):
    """Chat thread attached to a booking. sender=None marks system messages."""

    booking = models.ForeignKey(
        BookingRequest,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="messages_sent",
        null=True,
        blank=True,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        who = self.sender.username if self.sender_id else "system"
        return f"{who} @ {self.booking_id}: {self.text[:40]}"
