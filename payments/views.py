import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from bookings.models import BookingRequest
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
        if self.action in ("checkout", "simulate"):
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
            request.user,
            serializer.validated_data["booking"],
            serializer.validated_data["kind"],
        )
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "checkout_url": url,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get", "post"], url_path="simulate")
    def simulate(self, request):
        """Demo payments: GET quotes the amount, POST settles it (no Stripe)."""
        if not settings.STRIPE_DEMO_MODE:
            raise NotFound("Demo payments are disabled")
        booking_id = request.data.get("booking") or request.query_params.get(
            "booking"
        )
        kind = str(
            request.data.get("kind") or request.query_params.get("kind") or ""
        ).strip()
        if kind not in (Payment.Kind.DEPOSIT, Payment.Kind.BALANCE):
            raise ValidationError("kind must be 'deposit' or 'balance'")
        if not booking_id:
            raise ValidationError("booking is required")
        booking = get_object_or_404(BookingRequest, pk=booking_id)
        if request.method == "GET":
            amount_cents = services.simulate_quote(
                request.user, booking, kind
            )
            return Response(
                {
                    "amount_cents": amount_cents,
                    "kind": kind,
                    "booking_status": booking.status,
                }
            )
        payment = services.simulate_payment(request.user, booking, kind)
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "booking_status": payment.booking.status,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="confirm-session")
    def confirm_session(self, request):
        """Settle a checkout from the success page (webhook fallback)."""
        session_id = str(request.data.get("session_id") or "").strip()
        if not session_id:
            raise ValidationError("session_id is required")
        try:
            payment = services.confirm_checkout_session(
                request.user, session_id
            )
        except stripe.InvalidRequestError:
            raise ValidationError("That Stripe session does not exist")
        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "booking_status": payment.booking.status,
            }
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
