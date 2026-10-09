from django.db import models

class Shoot(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Reservada"
        EDITING = "editing", "En edición"
        DELIVERED = "delivered", "Entregada"

    client = models.ForeignKey(
        "clients.Client", on_delete=models.CASCADE, related_name="shoots"
        )
    title = models.CharField(max_length=150)
    shoot_type = models.CharField(max_length=50)
    date = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.BOOKED
        )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
