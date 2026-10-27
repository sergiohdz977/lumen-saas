from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone
from bookings.models import BookingRequest
from notifications.models import Notification
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


def booking_paid_kinds(booking):
    """Kinds of payment already settled for this booking."""
    return set(
        Payment.objects.filter(
            booking=booking, status=Payment.Status.PAID
        ).values_list("kind", flat=True)
    )


def booking_is_fully_paid(booking):
    """True once deposit and balance are both settled."""
    if booking is None:
        return True
    return {Payment.Kind.DEPOSIT, Payment.Kind.BALANCE} <= booking_paid_kinds(
        booking
    )


def _warn_stripe_missing(photographer, customer, booking):
    """Tell the photographer why the customer cannot pay (once per read)."""
    if Notification.objects.filter(
        user=photographer, title="Stripe not connected", is_read=False
    ).exists():
        return
    notify(
        photographer,
        "Stripe not connected",
        (
            f'"{customer.username}" tried to pay for '
            f'"{booking.package.title}", but you cannot receive money '
            "until you connect Stripe."
        ),
    )


def start_checkout(user, booking, kind=Payment.Kind.DEPOSIT):
    """Create (or refresh) the pending payment and its Stripe session."""
    if booking.customer_id != user.id:
        raise PermissionDenied("That booking does not belong to you")
    paid_kinds = booking_paid_kinds(booking)
    if kind == Payment.Kind.DEPOSIT:
        if booking.status not in (
            BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT,
            BookingRequest.Status.ACCEPTED,
        ):
            raise ValidationError(
                "You can only pay a deposit for an accepted booking"
            )
        if Payment.Kind.DEPOSIT in paid_kinds:
            raise ValidationError(
                "The deposit for this booking has already been paid"
            )
        percentage = settings.DEPOSIT_PERCENTAGE
    elif kind == Payment.Kind.BALANCE:
        if booking.status != BookingRequest.Status.CONFIRMED:
            raise ValidationError(
                "You can only pay the balance for a confirmed booking"
            )
        if Payment.Kind.DEPOSIT not in paid_kinds:
            raise ValidationError(
                "Pay the deposit before paying the balance"
            )
        if Payment.Kind.BALANCE in paid_kinds:
            raise ValidationError(
                "The balance for this booking has already been paid"
            )
        shoot = getattr(booking, "shoot", None)
        if shoot is None or getattr(shoot, "gallery", None) is None:
            raise ValidationError(
                "The gallery is not ready yet"
            )
        percentage = settings.BALANCE_PERCENTAGE
    else:
        raise ValidationError("Unknown payment kind")
    profile = booking.package.profile
    if not profile.stripe_account_id or not profile.stripe_onboarded:
        _warn_stripe_missing(profile.user, user, booking)
        raise ValidationError(
            "The photographer has not finished setting up payments"
        )
    payment = Payment.objects.filter(booking=booking, kind=kind).first()
    if payment is None:
        amount = booking.package.price * Decimal(percentage) / Decimal(100)
        amount_cents = (amount * 100).quantize(Decimal("1"), ROUND_HALF_UP)
        payment = Payment.objects.create(
            booking=booking,
            kind=kind,
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
        success_url=(
            f"{settings.SITE_URL}/payments/success/"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=f"{settings.SITE_URL}/payments/cancel/",
        destination_account=profile.stripe_account_id,
        platform_fee_cents=platform_fee_cents,
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return payment, session.url


def start_upgrade(user):
    """Start Stripe Checkout for the photographer's Pro subscription."""
    from profiles.models import PhotographerProfile

    if not hasattr(user, "profile"):
        raise ValidationError(
            "Create your photographer profile before upgrading"
        )
    if user.profile.plan == PhotographerProfile.PLAN_PRO:
        raise ValidationError("You are already on the Pro plan")
    if not settings.STRIPE_PRO_PRICE_ID:
        raise ValidationError("Subscriptions are not configured yet")
    profile = user.profile
    if not profile.stripe_customer_id:
        customer = providers.create_customer(user.email)
        profile.stripe_customer_id = customer.id
        profile.save(update_fields=["stripe_customer_id"])
    session = providers.create_subscription_session(
        customer_id=profile.stripe_customer_id,
        price_id=settings.STRIPE_PRO_PRICE_ID,
        success_url=f"{settings.SITE_URL}/payments/success/",
        cancel_url=f"{settings.SITE_URL}/payments/cancel/",
    )
    return session.url


def settle_payment(payment):
    """Mark a payment as paid, confirm its booking and notify both sides."""
    if payment.status == Payment.Status.PAID:
        return payment
    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at"])
    if payment.kind == Payment.Kind.DEPOSIT:
        booking = payment.booking
        confirmed = False
        if booking.status in (
            BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT,
            BookingRequest.Status.ACCEPTED,
        ):
            booking.status = BookingRequest.Status.CONFIRMED
            booking.save(update_fields=["status"])
            confirmed = True
        notify(
            payment.photographer,
            "Deposit received",
            f"{payment.customer.username}'s deposit was paid",
        )
        notify(
            payment.customer,
            "Payment confirmed",
            (
                "Your deposit was received and your booking is confirmed"
                if confirmed
                else "Your deposit was received"
            ),
        )
    else:
        notify(
            payment.photographer,
            "Balance received",
            f"{payment.customer.username}'s final payment was paid",
        )
        notify(
            payment.customer,
            "Payment confirmed",
            "Your remaining balance was received",
        )
    return payment


def confirm_checkout_session(user, session_id):
    """Settle a payment from the success page when no webhook is configured."""
    session = providers.retrieve_checkout_session(session_id)
    metadata = session.get("metadata") or {}
    payment = None
    if metadata.get("payment_id"):
        payment = Payment.objects.filter(pk=metadata["payment_id"]).first()
    if payment is None:
        payment = Payment.objects.filter(
            stripe_session_id=session_id
        ).first()
    if payment is None:
        raise ValidationError(
            "We could not find a payment for that Stripe session"
        )
    if payment.customer_id != user.id:
        raise PermissionDenied("That payment does not belong to you")
    if session.get("payment_status") != "paid":
        # Still processing: the webhook will settle it when it lands.
        return payment
    return settle_payment(payment)


def handle_webhook_event(event):
    """Apply a Stripe event to our payment. Safe to call twice."""
    if event["type"] == "account.updated":
        return _handle_account_updated(event)
    if event["type"] in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        return _handle_subscription(event)
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
    if payment is None:
        # Unknown session: nothing to do, the answer must still be 200.
        return None
    # Safe to call twice: settle_payment ignores already-paid rows, so
    # Stripe retries never double-notify.
    return settle_payment(payment)


def _handle_account_updated(event):
    """Flip the onboarded flag when the photographer finishes Stripe's form."""
    from profiles.models import PhotographerProfile

    account = event["data"]["object"]
    PhotographerProfile.objects.filter(
        stripe_account_id=account["id"]
    ).update(stripe_onboarded=bool(account.get("details_submitted")))
    return account["id"]


def _handle_subscription(event):
    """Keep profile.plan in sync with the Stripe subscription status."""
    from profiles.models import PhotographerProfile

    obj = event["data"]["object"]
    profile = None
    if obj.get("customer"):
        profile = PhotographerProfile.objects.filter(
            stripe_customer_id=obj["customer"]
        ).first()
    if profile is None and obj.get("id"):
        profile = PhotographerProfile.objects.filter(
            subscription_id=obj["id"]
        ).first()
    if profile is None:
        # Event for an account we do not know; still answer 200.
        return None
    if event["type"] == "customer.subscription.deleted":
        profile.plan = PhotographerProfile.PLAN_FREE
        profile.subscription_id = ""
    else:
        active = obj.get("status") in ("active", "trialing")
        profile.plan = (
            PhotographerProfile.PLAN_PRO
            if active
            else PhotographerProfile.PLAN_FREE
        )
        profile.subscription_id = obj.get(
            "id", profile.subscription_id
        )
    profile.save(update_fields=["plan", "subscription_id"])
    return profile.pk
