from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "photographer", "created_at")
    list_filter = ("photographer",)
    search_fields = ("name", "email")
