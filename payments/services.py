from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone
from bookings.models import BookingRequest
from notifications.services import notify
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import providers
from .models import Payment


def start_onboarding(user, country):
    """Create the photographer's Stripe Express account and its link."""
    if not hasattr(user, "profile"):
        raise ValidationError(
            "Create your photographer profile before setting up payments"
        )
    country = str(country or "").strip().upper()
    if len(country) != 2 or not country.isalpha():
        raise ValidationError(
            "Country must be a 2-letter code, for example US or ES"
        )
    if not user.profile.stripe_account_id:
        account = providers.create_connected_account(country)
        user.profile.stripe_account_id = account.id
        user.profile.save(update_fields=["stripe_account_id"])
    link = providers.create_account_link(user.profile.stripe_account_id)
    return link.url


def start_checkout(user, booking):
    """Create (or refresh) the pending payment and its Stripe session."""
    if booking.customer_id != user.id:
        raise PermissionDenied("That booking does not belong to you")
    if booking.status != BookingRequest.Status.ACCEPTED:
        raise ValidationError(
            "You can only pay a deposit for an accepted booking"
        )
    profile = booking.package.profile
    if not profile.stripe_account_id or not profile.stripe_onboarded:
        raise ValidationError(
            "The photographer has not finished setting up payments"
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
    platform_fee_cents = None
    if settings.STRIPE_PLATFORM_FEE_PERCENTAGE > 0:
        platform_fee_cents = int(
            (
                Decimal(payment.amount_cents)
                * Decimal(settings.STRIPE_PLATFORM_FEE_PERCENTAGE)
                / Decimal(100)
            ).quantize(Decimal("1"), ROUND_HALF_UP)
        )
    session = providers.create_checkout_session(
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        payment=payment,
        success_url=f"{settings.SITE_URL}/payments/success/",
        cancel_url=f"{settings.SITE_URL}/payments/cancel/",
        destination_account=profile.stripe_account_id,
        platform_fee_cents=platform_fee_cents,
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return payment, session.url


def handle_webhook_event(event):
    """Apply a Stripe event to our payment. Safe to call twice."""
    if event["type"] == "account.updated":
        return _handle_account_updated(event)
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


def _handle_account_updated(event):
    """Flip the onboarded flag when the photographer finishes Stripe's form."""
    from profiles.models import PhotographerProfile

    account = event["data"]["object"]
    PhotographerProfile.objects.filter(
        stripe_account_id=account["id"]
    ).update(stripe_onboarded=bool(account.get("details_submitted")))
    return account["id"]
