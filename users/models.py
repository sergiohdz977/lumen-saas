from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    studio_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)

