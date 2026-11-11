from django.conf import settings
from django.db import models


class Review(models.Model):
    photographer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    booking = models.ForeignKey(
        "bookings.BookingRequest",
        on_delete=models.CASCADE,
        related_name="reviews",
        null=True,
        blank=True,
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    reply = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One review per completed session. Legacy rows have no
            # booking, so they sit outside the constraint.
            models.UniqueConstraint(
                fields=["booking"],
                name="unique_review_per_booking",
                condition=models.Q(booking__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.customer} → {self.photographer}: {self.rating}/5"
