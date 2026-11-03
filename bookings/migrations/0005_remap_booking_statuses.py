from django.db import migrations

# Old status values -> the definitive flow states.
OLD_TO_NEW = {
    "pending": "requested",
    "accepted_pending_deposit": "awaiting_payment",
    "accepted": "awaiting_payment",
    "confirmed": "accepted",
}

NEW_TO_OLD = {
    "requested": "pending",
    "awaiting_payment": "accepted_pending_deposit",
    "accepted": "confirmed",
    "completed": "confirmed",
}


def forwards(apps, schema_editor):
    BookingRequest = apps.get_model("bookings", "BookingRequest")
    for old, new in OLD_TO_NEW.items():
        BookingRequest.objects.filter(status=old).update(status=new)


def backwards(apps, schema_editor):
    BookingRequest = apps.get_model("bookings", "BookingRequest")
    for new, old in NEW_TO_OLD.items():
        BookingRequest.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0004_bookingrequest_event_location_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
