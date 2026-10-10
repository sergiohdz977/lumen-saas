from rest_framework.routers import DefaultRouter
from .views import GalleryViewSet, PhotoViewSet

router = DefaultRouter()
router.register("galleries", GalleryViewSet, basename="gallery")
router.register("photos", PhotoViewSet, basename="photo")

urlpatterns = router.urls
