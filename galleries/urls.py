from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import GalleryViewSet, PhotoViewSet, gallery_view

router = DefaultRouter()
router.register("galleries", GalleryViewSet, basename="gallery")
router.register("photos", PhotoViewSet, basename="photo")

urlpatterns = [
    path("gallery-view/<str:token>/", gallery_view, name="gallery-view"),
] + router.urls
