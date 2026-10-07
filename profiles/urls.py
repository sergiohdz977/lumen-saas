from rest_framework.routers import DefaultRouter
from .views import PhotographerProfileViewSet, PackageViewSet, PortfolioPhotoViewSet

router = DefaultRouter()
router.register("profiles", PhotographerProfileViewSet, basename="profile")
router.register("packages", PackageViewSet, basename="package")
router.register("portfolio-photos", PortfolioPhotoViewSet, basename="portfolio-photo")

urlpatterns = router.urls
