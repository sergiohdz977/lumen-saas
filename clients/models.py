from django.db import models
from django.conf import settings

class Client(models.Model):
    photographer =  models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clients"
        )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_records",
        help_text="Linked account, if any (set when a booking is accepted)",
        )
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["photographer", "user"],
                name="unique_client_user_per_photographer",
            )
        ]

    def __str__(self):
        return self.name
