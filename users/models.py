from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_PHOTOGRAPHER = "photographer"
    ROLE_CUSTOMER = "customer"
    ROLE_CHOICES = [
        (ROLE_PHOTOGRAPHER, "Fotógrafo"),
        (ROLE_CUSTOMER, "Cliente"),
    ]

    role = models.CharField(
        max_length=12,
        choices=ROLE_CHOICES,
        default=ROLE_CUSTOMER,
        verbose_name="Rol",
    )
    studio_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)

