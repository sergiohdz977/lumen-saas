from rest_framework.routers import DefaultRouter
from .views import PhotographerProfileViewSet

router = DefaultRouter()
router.register("profiles", PhotographerProfileViewSet, basename="profile")

urlpatterns = router.urls
