from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone
from bookings.models import BookingRequest
from notifications.services import notify
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import providers
from .models import Payment


def start_checkout(user, booking):
    """Create (or refresh) the pending payment and its Stripe session."""
    if booking.customer_id != user.id:
        raise PermissionDenied("That booking does not belong to you")
    if booking.status != BookingRequest.Status.ACCEPTED:
        raise ValidationError(
            "You can only pay a deposit for an accepted booking"
        )
    payment = Payment.objects.filter(booking=booking).first()
    if payment and payment.status == Payment.Status.PAID:
        raise ValidationError(
            "The deposit for this booking has already been paid"
        )
    if payment is None:
        amount = booking.package.price * Decimal(
            settings.DEPOSIT_PERCENTAGE
        ) / Decimal(100)
        amount_cents = (amount * 100).quantize(Decimal("1"), ROUND_HALF_UP)
        payment = Payment.objects.create(
            booking=booking,
            customer=user,
            photographer=booking.package.profile.user,
            amount_cents=int(amount_cents),
        )
    session = providers.create_checkout_session(
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        payment=payment,
        success_url=f"{settings.SITE_URL}/payments/success/",
        cancel_url=f"{settings.SITE_URL}/payments/cancel/",
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return payment, session.url


def handle_webhook_event(event):
    """Apply a Stripe event to our payment. Safe to call twice."""
    if event["type"] != "checkout.session.completed":
        return None
    session = event["data"]["object"]
    metadata = session.get("metadata") or {}
    payment = None
    if metadata.get("payment_id"):
        payment = Payment.objects.filter(pk=metadata["payment_id"]).first()
    if payment is None:
        payment = Payment.objects.filter(
            stripe_session_id=session["id"]
        ).first()
    if payment is None or payment.status == Payment.Status.PAID:
        # Unknown session, or the event arrived twice (Stripe retries):
        # nothing to do, the answer must still be 200.
        return payment
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at"])
    notify(
        payment.photographer,
        "Deposit received",
        f"{payment.customer.username}'s deposit was paid",
    )
    notify(
        payment.customer,
        "Payment confirmed",
        "Your deposit was received",
    )
    return payment
