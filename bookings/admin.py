from django.contrib import admin
from .models import BookingRequest


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("customer", "package", "date", "status", "created_at")
    list_filter = ("status", "date")
    search_fields = ("customer__username", "package__title")
