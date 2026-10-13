from django.conf import settings
from django.core.mail import send_mail

from celery import shared_task

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
        subject="Tu reserva fue aceptada",
        message=(
            f"Hola {booking.customer.username},\n\n"
            f'Tu sesión "{booking.package.title}" fue aceptada para el '
            f"{booking.date.strftime('%d/%m/%Y %H:%M')}.\n\n"
            "Puedes ver el estado desde Lumen.\n"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[booking.customer.email],
    )
    return booking.customer.email
