from django.contrib import admin
from .models import PhotographerProfile


@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ("studio_name", "user", "city", "is_published")
    list_filter = ("is_published", "city")
    prepopulated_fields = {"slug": ("studio_name",)}
    search_fields = ("studio_name", "user__username")
