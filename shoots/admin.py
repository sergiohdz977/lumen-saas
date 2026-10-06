from django.contrib import admin
from .models import Shoot


@admin.register(Shoot)
class ShootAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "shoot_type", "date", "status")
    list_filter = ("status", "shoot_type")
    search_fields = ("title", "client__name")
