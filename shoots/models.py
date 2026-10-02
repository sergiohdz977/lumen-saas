from django.db import models

class Shoot(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        EDITING = "editing", "Editing"
        DELIVERED = "delivered", "Delivered"

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


    def _str_(self):
        return self.title