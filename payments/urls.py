from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PaymentConfigView, PaymentViewSet, stripe_webhook

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = [
    path("payments/config/", PaymentConfigView.as_view()),
    path("payments/webhook/", stripe_webhook),
] + router.urls
