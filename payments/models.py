from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    class Kind(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        BALANCE = "balance", "Balance"

    booking = models.ForeignKey(
        "bookings.BookingRequest",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.DEPOSIT
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_made",
    )
    photographer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments_received",
    )
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="usd")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    stripe_session_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.customer} -> {self.photographer}: "
            f"{self.amount_cents} {self.currency} ({self.status})"
        )
