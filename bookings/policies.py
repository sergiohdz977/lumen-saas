from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from profiles.models import Package


POLICY_NAMES = {
    Package.CancellationPolicy.FLEXIBLE: "Flexible",
    Package.CancellationPolicy.MODERATE: "Moderate",
    Package.CancellationPolicy.STRICT: "Strict",
    Package.CancellationPolicy.CUSTOM: "Custom",
}

POLICY_SUMMARIES = {
    Package.CancellationPolicy.FLEXIBLE: (
        "Full refund if cancelled 48 hours before the shoot."
    ),
    Package.CancellationPolicy.MODERATE: (
        "50% refund if cancelled 7 days before the shoot; the deposit is "
        "retained after that."
    ),
    Package.CancellationPolicy.STRICT: (
        "The deposit is non-refundable upon booking."
    ),
}


def policy_summary(package):
    """Human readable rules for a package, including custom policies."""
    if package.cancellation_policy == Package.CancellationPolicy.CUSTOM:
        percent = package.cancellation_refund_percent
        hours = package.cancellation_refund_hours
        if percent >= 100:
            return (
                "Full refund if cancelled at least "
                f"{hours} hours before the shoot."
            )
        if percent <= 0:
            return "The deposit is non-refundable upon booking."
        return (
            f"{percent}% refund if cancelled at least {hours} hours before "
            "the shoot; the deposit is retained after that."
        )
    return POLICY_SUMMARIES.get(package.cancellation_policy, "")


def refund_fraction(booking):
    """Share of the paid deposit refunded if the client cancels right now."""
    package = booking.package
    policy = package.cancellation_policy
    remaining = booking.date - timezone.now()
    if policy == Package.CancellationPolicy.FLEXIBLE:
        return (
            Decimal("1") if remaining >= timedelta(hours=48) else Decimal("0")
        )
    if policy == Package.CancellationPolicy.MODERATE:
        return (
            Decimal("0.5") if remaining >= timedelta(days=7) else Decimal("0")
        )
    if policy == Package.CancellationPolicy.CUSTOM:
        if remaining >= timedelta(hours=package.cancellation_refund_hours):
            return Decimal(package.cancellation_refund_percent) / Decimal(100)
        return Decimal("0")
    return Decimal("0")


def client_refund_cents(booking, deposit_cents):
    """What a client cancellation would refund from the paid deposit."""
    if not deposit_cents:
        return 0
    fraction = refund_fraction(booking)
    if fraction <= 0:
        return 0
    return int(
        (Decimal(deposit_cents) * fraction).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def policy_name(booking):
    return POLICY_NAMES.get(
        booking.package.cancellation_policy,
        booking.package.cancellation_policy.title(),
    )
