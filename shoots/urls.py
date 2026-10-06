from rest_framework.routers import DefaultRouter
from .views import ShootViewSet

router = DefaultRouter()
router.register("", ShootViewSet, basename="shoot")

urlpatterns = router.urls
