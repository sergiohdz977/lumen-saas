from django.contrib import admin
from .models import Package, PhotographerProfile, PortfolioPhoto


class PackageInline(admin.TabularInline):
    model = Package
    extra = 1


class PortfolioPhotoInline(admin.TabularInline):
    model = PortfolioPhoto
    extra = 1


@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ("studio_name", "user", "city", "is_published")
    list_filter = ("is_published", "city")
    prepopulated_fields = {"slug": ("studio_name",)}
    search_fields = ("studio_name", "user__username")
    inlines = [PackageInline, PortfolioPhotoInline]
