from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from bookings.models import BookingRequest, Message
from clients.models import Client
from galleries.models import Favorite, Gallery, Photo
from notifications.models import Notification
from payments.models import Payment
from profiles.management.commands.seed_demo import DEMO_PROFILES
from reviews.models import Review
from shoots.models import Shoot

User = get_user_model()

DEMO_USERNAMES = [spec["username"] for spec in DEMO_PROFILES]


class Command(BaseCommand):
    help = (
        "Wipe every customer, booking, review, client, shoot, gallery and "
        "payment, then leave only the seeded demo photographers (profiles, "
        "packages and portfolio are kept)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip the interactive confirmation (for scripted runs).",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            answer = input(
                "This deletes all customers, bookings, reviews and chat, "
                "keeping only the demo photographers. Continue? [y/N] "
            )
            if answer.strip().lower() not in {"y", "yes"}:
                self.stdout.write("Cancelled. Nothing was deleted.")
                return

        counts = {}
        for label, model in (
            ("favorites", Favorite),
            ("gallery photos", Photo),
            ("galleries", Gallery),
            ("shoots", Shoot),
            ("messages", Message),
            ("payments", Payment),
            ("reviews", Review),
            ("bookings", BookingRequest),
            ("clients", Client),
            ("notifications", Notification),
        ):
            counts[label] = model.objects.all().delete()[0]

        removed_users = User.objects.exclude(
            username__in=DEMO_USERNAMES
        ).delete()[0]
        counts["users"] = removed_users

        # Make sure the four demo photographers exist (idempotent).
        call_command("seed_demo")
        # seed_demo also creates a demo customer; the goal is photographers
        # only, so drop every remaining customer account.
        User.objects.filter(role=User.ROLE_CUSTOMER).delete()

        for label, total in counts.items():
            self.stdout.write(f"deleted {label}: {total}")
        self.stdout.write(
            self.style.SUCCESS(
                "reset_demo finished. Only demo photographers remain."
            )
        )
