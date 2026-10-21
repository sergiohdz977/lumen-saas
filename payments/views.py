import stripe
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from users.models import User
from users.permissions import IsCustomer, IsPhotographer

from . import providers, services
from .models import Payment
from .serializers import CheckoutSerializer, PaymentSerializer


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == "checkout":
            return [IsAuthenticated(), IsCustomer()]
        if self.action in ("onboard", "upgrade"):
            return [IsAuthenticated(), IsPhotographer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Payment.objects.none()
        qs = Payment.objects.select_related(
            "booking", "customer", "photographer"
        )
        if user.role == User.ROLE_CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(photographer=user)

    @action(detail=False, methods=["post"])
    def onboard(self, request):
        url = services.start_onboarding(
            request.user, request.data.get("country")
        )
        return Response({"onboarding_url": url}, status=201)

    @action(detail=False, methods=["post"])
    def upgrade(self, request):
        url = services.start_upgrade(request.user)
        return Response({"checkout_url": url}, status=201)

    @action(detail=False, methods=["post"])
    def checkout(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment, url = services.start_checkout(
            request.user, serializer.validated_data["booking"]
        )
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "checkout_url": url,
            },
            status=status.HTTP_201_CREATED,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = providers.construct_webhook_event(payload, signature)
    except stripe.SignatureVerificationError:
        return Response(status=status.HTTP_400_BAD_REQUEST)
    services.handle_webhook_event(event)
    return Response({"received": True})
