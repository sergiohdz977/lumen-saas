from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from profiles.models import Package, PhotographerProfile, PortfolioPhoto

User = get_user_model()

DEMO_PASSWORD = "DemoLumen2026"

DEMO_PROFILES = [
    {
        "username": "demofoto",
        "email": "demofoto@example.com",
        "studio_name": "Lumen Demo Studio",
        "city": "La Habana",
        "specialties": "Portraits, Events",
        "bio": (
            "Warm, honest photography for people and celebrations. "
            "Ten years behind the camera, one goal: images that feel "
            "like the moment itself."
        ),
        "phone": "+53 5555 0101",
        "is_published": True,
        "plan": PhotographerProfile.PLAN_FREE,
        "packages": [
            (
                "Portrait Session",
                "60-minute session with 10 professionally edited photos.",
                "89.00",
            ),
            (
                "Event Coverage",
                "Up to 3 hours of coverage and a 60+ photo online gallery.",
                "249.00",
            ),
            (
                "Wedding Essentials",
                "Ceremony and reception coverage with 300 edited photos.",
                "899.00",
            ),
        ],
        "photos": [
            ("img/portfolio-01.jpg", "Golden hour portrait"),
            ("img/portfolio-02.jpg", "Studio setup"),
            ("img/portfolio-03.jpg", "Street story"),
            ("img/portfolio-04.jpg", "Event coverage"),
        ],
    },
    {
        "username": "elena.vargas",
        "email": "elena.vargas@example.com",
        "studio_name": "Elena Vargas Studio",
        "city": "Madrid",
        "specialties": "Weddings, Couples",
        "bio": (
            "Documenting love stories in a natural, unobtrusive style. "
            "Based in Madrid, available across Spain and beyond."
        ),
        "phone": "+34 555 0202",
        "is_published": True,
        "plan": PhotographerProfile.PLAN_FREE,
        "packages": [
            (
                "Couples Session",
                "Golden-hour couples shoot with 15 edited images.",
                "120.00",
            ),
            (
                "Wedding Story",
                "Full-day wedding coverage and a private online gallery.",
                "1450.00",
            ),
        ],
        "photos": [
            ("img/portfolio-05.jpg", "First look"),
            ("img/portfolio-06.jpg", "Ceremony light"),
            ("img/portfolio-07.jpg", "Reception dance"),
        ],
    },
    {
        "username": "marco.ortiz",
        "email": "marco.ortiz@example.com",
        "studio_name": "Marco Ortiz Portraits",
        "city": "Miami",
        "specialties": "Headshots, Branding",
        "bio": (
            "Clean, confident portraits for professionals and personal "
            "brands. Studio or on location in Miami."
        ),
        "phone": "+1 555 0303",
        "is_published": True,
        "plan": PhotographerProfile.PLAN_FREE,
        "packages": [
            (
                "Headshot Mini",
                "20-minute studio headshot with 3 edited retouches.",
                "59.00",
            ),
            (
                "Personal Branding",
                "90-minute session with 20 brand-ready photos.",
                "180.00",
            ),
        ],
        "photos": [
            ("img/portfolio-08.jpg", "Executive headshot"),
            ("img/portfolio-09.jpg", "Natural light portrait"),
            ("img/portfolio-10.jpg", "Brand session"),
        ],
    },
    {
        "username": "aisha.khan",
        "email": "aisha.khan@example.com",
        "studio_name": "Aisha Khan Visuals",
        "city": "London",
        "specialties": "Fashion, Editorial",
        "bio": (
            "Editorial and commercial photography with a sharp, modern "
            "eye. Campaigns, lookbooks and runway coverage."
        ),
        "phone": "+44 555 0404",
        "is_published": True,
        "plan": PhotographerProfile.PLAN_PRO,
        "packages": [
            (
                "Lookbook Session",
                "Half-day fashion shoot with 25 retouched images.",
                "650.00",
            ),
            (
                "Campaign Day",
                "Full-day commercial production support.",
                "1900.00",
            ),
        ],
        "photos": [
            ("img/portfolio-11.jpg", "Editorial look"),
            ("img/portfolio-12.jpg", "Campaign still"),
            ("img/portfolio-13.jpg", "Runway moment"),
        ],
    },
]

DEMO_CUSTOMERS = [
    {
        "username": "sofia.reyes",
        "email": "sofia.reyes@example.com",
    },
]


class Command(BaseCommand):
    help = (
        "Seed demo photographers, packages and portfolio photos. "
        "Idempotent: existing rows are never modified."
    )

    def handle(self, *args, **options):
        new_rows = 0
        for spec in DEMO_PROFILES:
            user, user_created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": User.ROLE_PHOTOGRAPHER,
                },
            )
            if user_created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                new_rows += 1
            self.stdout.write(
                f"user: {spec['username']} ({'created' if user_created else 'exists'})"
            )

            profile, profile_created = PhotographerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "studio_name": spec["studio_name"],
                    "city": spec["city"],
                    "specialties": spec["specialties"],
                    "bio": spec["bio"],
                    "phone": spec["phone"],
                    "is_published": spec["is_published"],
                    "plan": spec["plan"],
                },
            )
            if profile_created:
                new_rows += 1
            else:
                self.stdout.write(f"profile: {profile.slug} (exists)")

            for title, description, price in spec["packages"]:
                _, created = Package.objects.get_or_create(
                    profile=profile,
                    title=title,
                    defaults={"description": description, "price": price},
                )
                if created:
                    new_rows += 1
                    self.stdout.write(f"package: {spec['username']} -> {title}")

            for image, caption in spec["photos"]:
                _, created = PortfolioPhoto.objects.get_or_create(
                    profile=profile,
                    image=image,
                    defaults={"caption": caption},
                )
                if created:
                    new_rows += 1
                    self.stdout.write(f"photo: {spec['username']} -> {caption}")

        for spec in DEMO_CUSTOMERS:
            user, user_created = User.objects.get_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": User.ROLE_CUSTOMER,
                },
            )
            if user_created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                new_rows += 1
            self.stdout.write(
                f"customer: {spec['username']} "
                f"({'created' if user_created else 'exists'})"
            )

        self.stdout.write(
            self.style.SUCCESS(f"seed_demo finished. New rows: {new_rows}")
        )
