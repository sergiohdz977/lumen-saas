from django.db import migrations


def backfill_shoot_booking(apps, schema_editor):
    """Link legacy shoots to their booking (same customer, photographer, date)."""
    Shoot = apps.get_model("shoots", "Shoot")
    BookingRequest = apps.get_model("bookings", "BookingRequest")
    for shoot in Shoot.objects.filter(booking__isnull=True).iterator():
        booking = (
            BookingRequest.objects.filter(
                customer_id=shoot.client.user_id,
                package__profile__user_id=shoot.client.photographer_id,
                date=shoot.date,
                status__in=[
                    "accepted",
                    "accepted_pending_deposit",
                    "confirmed",
                ],
            )
            .order_by("created_at")
            .first()
        )
        if booking is not None:
            shoot.booking = booking
            shoot.save(update_fields=["booking"])


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0003_bookingrequest_deposit_deadline_and_more"),
        ("shoots", "0005_shoot_booking"),
    ]

    operations = [
        migrations.RunPython(
            backfill_shoot_booking, migrations.RunPython.noop
        ),
    ]
