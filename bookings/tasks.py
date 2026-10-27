from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from celery import shared_task
from notifications.services import notify

from .models import BookingRequest


@shared_task
def booking_accepted_email(booking_id):
    """Email the customer when their booking request is accepted."""
    booking = (
        BookingRequest.objects.select_related("customer", "package")
        .filter(pk=booking_id)
        .first()
    )
    if booking is None or not booking.customer.email:
        return None
    send_mail(
        subject="Your booking was accepted",
        message=(
            f"Hello {booking.customer.username},\n\n"
            f'Your shoot "{booking.package.title}" was accepted for '
            f"{booking.date.strftime('%d/%m/%Y %H:%M')}.\n\n"
            "You can check its status in Lumen.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[booking.customer.email],
    )
    return booking.customer.email


@shared_task
def enforce_deposit_deadline(booking_id):
    """Cancel the booking (and drop its shoot) if the deposit never arrived."""
    booking = (
        BookingRequest.objects.select_related(
            "customer", "package__profile__user"
        )
        .filter(pk=booking_id)
        .first()
    )
    if booking is None:
        return None
    if booking.status != BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT:
        # Already confirmed, rejected or cancelled: nothing to do.
        return None
    if (
        booking.deposit_deadline is None
        or timezone.now() < booking.deposit_deadline - timedelta(seconds=60)
    ):
        # The task can fire immediately under CELERY_TASK_ALWAYS_EAGER
        # (tests): the deadline has not passed yet, so keep waiting.
        return None
    from shoots.models import Shoot

    photographer = booking.package.profile.user
    booking.status = BookingRequest.Status.CANCELLED
    booking.save(update_fields=["status"])
    Shoot.objects.filter(
        client__photographer=photographer,
        client__user=booking.customer,
        date=booking.date,
    ).delete()
    notify(
        booking.customer,
        "Booking cancelled",
        (
            f'The deposit for "{booking.package.title}" was not paid in time, '
            "so the booking was cancelled."
        ),
    )
    notify(
        photographer,
        "Booking cancelled",
        (
            f"The deposit from {booking.customer.username} for "
            f'"{booking.package.title}" was not paid within '
            f"{settings.DEPOSIT_DEADLINE_HOURS} hours."
        ),
    )
    return booking.pk
