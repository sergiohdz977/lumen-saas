from rest_framework.routers import DefaultRouter
from .views import BookingRequestViewSet

router = DefaultRouter()
router.register("bookings", BookingRequestViewSet, basename="booking")

urlpatterns = router.urls
