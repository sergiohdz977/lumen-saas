from datetime import datetime, timezone as dt_timezone

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from clients.models import Client
from profiles.models import Package, PhotographerProfile
from shoots.models import Shoot
from users.models import User
from .models import BookingRequest


class BookingEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.beto = User.objects.create_user(
            username="beto",
            email="beto@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.other_customer = User.objects.create_user(
            username="pedro",
            email="pedro@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.hidden_profile = PhotographerProfile.objects.create(
            user=cls.beto,
            studio_name="Beto Oculto",
            slug="beto-oculto",
            is_published=False,
        )
        cls.package = Package.objects.create(
            profile=cls.ana_profile,
            title="Boda completa",
            price=200,
        )
        cls.hidden_package = Package.objects.create(
            profile=cls.hidden_profile,
            title="Paquete oculto",
            price=10,
        )
        cls.pending_booking = BookingRequest.objects.create(
            customer=cls.customer,
            package=cls.package,
            date=datetime(2026, 11, 20, 10, 0, tzinfo=dt_timezone.utc),
            message="Hola, me interesa",
        )
        cls.other_customer_booking = BookingRequest.objects.create(
            customer=cls.other_customer,
            package=cls.package,
            date=datetime(2026, 12, 1, 10, 0, tzinfo=dt_timezone.utc),
        )

    def setUp(self):
        self.api = APIClient()
        self.valid_payload = {
            "package": self.package.pk,
            "date": "2026-12-15T15:00:00Z",
            "message": "Quiero reservar",
        }

    def test_anonymous_create_is_denied(self):
        response = self.api.post("/api/bookings/", self.valid_payload, format="json")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_photographer_cannot_create_booking(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post("/api/bookings/", self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Solo los clientes", str(response.data))

    def test_customer_creates_pending_booking(self):
        self.api.force_authenticate(self.customer)
        response = self.api.post("/api/bookings/", self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["customer_username"], "maria")
        booking = BookingRequest.objects.get(package=self.package, message="Quiero reservar")
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.status, BookingRequest.Status.PENDING)

    def test_status_cannot_be_forced_on_create(self):
        self.api.force_authenticate(self.customer)
        payload = {**self.valid_payload, "status": "accepted"}
        response = self.api.post("/api/bookings/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

    def test_cannot_book_hidden_profile_package(self):
        self.api.force_authenticate(self.customer)
        payload = {**self.valid_payload, "package": self.hidden_package.pk}
        response = self.api.post("/api/bookings/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no está disponible", str(response.data))

    def test_date_is_required(self):
        self.api.force_authenticate(self.customer)
        payload = {"package": self.package.pk}
        response = self.api.post("/api/bookings/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date", response.data)

    def test_customer_lists_only_own_bookings(self):
        self.api.force_authenticate(self.customer)
        response = self.api.get("/api/bookings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["message"], "Hola, me interesa")

    def test_photographer_lists_incoming_bookings(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/bookings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_photographer_does_not_see_other_photographer_bookings(self):
        package_beto = Package.objects.create(
            profile=self.hidden_profile, title="Otro", price=5
        )
        BookingRequest.objects.create(
            customer=self.customer,
            package=package_beto,
            date=datetime(2027, 1, 1, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/bookings/")
        self.assertEqual(response.data["count"], 2)

    def test_customer_cannot_see_others_booking_detail(self):
        self.api.force_authenticate(self.customer)
        response = self.api.get(f"/api/bookings/{self.other_customer_booking.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/bookings/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_photographer_accepts_pending_booking(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.pending_booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "accepted")
        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, BookingRequest.Status.ACCEPTED)

    def test_photographer_rejects_pending_booking(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.pending_booking.pk}/reject/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "rejected")

    def test_cannot_accept_already_processed_booking(self):
        self.pending_booking.status = BookingRequest.Status.ACCEPTED
        self.pending_booking.save()
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.pending_booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pendientes", str(response.data))

    def test_photographer_cannot_accept_others_booking(self):
        package_beto = Package.objects.create(
            profile=self.hidden_profile, title="Otro", price=5
        )
        beto_booking = BookingRequest.objects.create(
            customer=self.customer,
            package=package_beto,
            date=datetime(2027, 2, 1, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{beto_booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_accept_booking(self):
        self.api.force_authenticate(self.customer)
        response = self.api.post(
            f"/api/bookings/{self.pending_booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Solo los fotógrafos", str(response.data))


class AcceptSideEffectsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.beto = User.objects.create_user(
            username="beto",
            email="beto@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.beto_profile = PhotographerProfile.objects.create(
            user=cls.beto,
            studio_name="Beto Studio",
            slug="beto-studio",
            is_published=True,
        )
        cls.package = Package.objects.create(
            profile=cls.ana_profile, title="Boda completa", price=200
        )
        cls.package_beto = Package.objects.create(
            profile=cls.beto_profile, title="Retratos", price=50
        )

    def setUp(self):
        self.api = APIClient()
        self.booking = BookingRequest.objects.create(
            customer=self.customer,
            package=self.package,
            date=datetime(2026, 11, 20, 10, 0, tzinfo=dt_timezone.utc),
        )

    def test_accept_creates_client_and_booked_shoot(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.ACCEPTED)
        client = Client.objects.get(photographer=self.ana)
        self.assertEqual(client.user, self.customer)
        self.assertEqual(client.email, self.customer.email)
        self.assertEqual(client.name, "maria")
        shoot = Shoot.objects.get()
        self.assertEqual(shoot.client, client)
        self.assertEqual(shoot.status, Shoot.Status.BOOKED)
        self.assertEqual(shoot.date, self.booking.date)
        self.assertEqual(shoot.shoot_type, "Boda completa")

    def test_accept_reuses_client_for_same_customer(self):
        second_package = Package.objects.create(
            profile=self.ana_profile, title="Preboda", price=80
        )
        second_booking = BookingRequest.objects.create(
            customer=self.customer,
            package=second_package,
            date=datetime(2026, 11, 25, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        self.api.post(f"/api/bookings/{self.booking.pk}/accept/", format="json")
        self.api.post(f"/api/bookings/{second_booking.pk}/accept/", format="json")
        self.assertEqual(
            Client.objects.filter(photographer=self.ana).count(), 1
        )
        self.assertEqual(Shoot.objects.count(), 2)

    def test_accept_blocked_when_shoot_exists_same_day(self):
        existing_client = Client.objects.create(
            photographer=self.ana, name="Otro cliente"
        )
        Shoot.objects.create(
            client=existing_client,
            title="Sesion previa",
            shoot_type="retrato",
            date=datetime(2026, 11, 20, 18, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("esa fecha", str(response.data))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.PENDING)
        self.assertEqual(Shoot.objects.count(), 1)
        self.assertEqual(
            Client.objects.filter(photographer=self.ana).count(), 1
        )

    def test_accept_allowed_when_shoot_on_different_day(self):
        existing_client = Client.objects.create(
            photographer=self.ana, name="Otro cliente"
        )
        Shoot.objects.create(
            client=existing_client,
            title="Sesion otra dia",
            shoot_type="retrato",
            date=datetime(2026, 11, 21, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Shoot.objects.count(), 2)

    def test_other_photographer_shoot_does_not_block(self):
        beto_client = Client.objects.create(
            photographer=self.beto, name="Cliente de beto"
        )
        Shoot.objects.create(
            client=beto_client,
            title="Sesion de beto",
            shoot_type="retrato",
            date=datetime(2026, 11, 20, 15, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.booking.pk}/accept/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reject_creates_nothing(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/bookings/{self.booking.pk}/reject/", format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.REJECTED)
        self.assertEqual(Shoot.objects.count(), 0)
        self.assertEqual(Client.objects.count(), 0)

    def test_two_customers_without_email_get_separate_clients(self):
        carla = User.objects.create_user(
            username="carla",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        carla_booking = BookingRequest.objects.create(
            customer=carla,
            package=self.package,
            date=datetime(2026, 11, 26, 10, 0, tzinfo=dt_timezone.utc),
        )
        self.api.force_authenticate(self.ana)
        self.api.post(f"/api/bookings/{self.booking.pk}/accept/", format="json")
        self.api.post(
            f"/api/bookings/{carla_booking.pk}/accept/", format="json"
        )
        self.assertEqual(
            Client.objects.filter(photographer=self.ana).count(), 2
        )
        self.assertCountEqual(
            Client.objects.filter(photographer=self.ana).values_list(
                "user__username", flat=True
            ),
            ["maria", "carla"],
        )


class MarketplaceJourneyTests(TestCase):
    """Full end-to-end journeys across the whole marketplace."""

    def setUp(self):
        self.api = APIClient()

    def test_full_journey_registration_to_booked_shoot(self):
        response = self.api.post(
            "/api/auth/register/",
            {
                "username": "ana",
                "email": "ana@test.com",
                "password": "secret12345",
                "role": "photographer",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ana = User.objects.get(username="ana")

        PhotographerProfile.objects.create(
            user=ana, studio_name="Ana Studio", is_published=True
        )

        self.api.force_authenticate(ana)
        response = self.api.post(
            "/api/packages/",
            {"title": "Sesion de boda", "price": "150.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package_id = response.data["id"]
        self.assertEqual(response.data["profile_slug"], "ana-studio")

        response = self.api.post(
            "/api/auth/register/",
            {
                "username": "maria",
                "email": "maria@test.com",
                "password": "secret12345",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        maria = User.objects.get(username="maria")

        self.api.force_authenticate(user=None)
        response = self.api.get("/api/packages/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Sesion de boda")

        self.api.force_authenticate(maria)
        response = self.api.post(
            "/api/bookings/",
            {
                "package": package_id,
                "date": "2026-11-20T15:00:00Z",
                "message": "Quiero reservar",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        booking_id = response.data["id"]
        self.assertEqual(response.data["status"], "pending")

        self.api.force_authenticate(ana)
        response = self.api.get("/api/bookings/")
        self.assertEqual(response.data["count"], 1)
        response = self.api.post(
            f"/api/bookings/{booking_id}/accept/", format="json"
        )
        self.assertEqual(response.data["status"], "accepted")

        shoot = Shoot.objects.get()
        self.assertEqual(shoot.status, Shoot.Status.BOOKED)
        self.assertEqual(shoot.client.user, maria)
        self.assertEqual(shoot.client.photographer, ana)

        response = self.api.patch(
            f"/api/shoots/{shoot.pk}/", {"status": "editing"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.api.patch(
            f"/api/shoots/{shoot.pk}/", {"status": "delivered"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        shoot.refresh_from_db()
        self.assertEqual(shoot.status, Shoot.Status.DELIVERED)

    def test_rejected_booking_leaves_no_trace_and_customer_can_retry(self):
        ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        profile = PhotographerProfile.objects.create(
            user=ana, studio_name="Ana Studio", is_published=True
        )
        package = Package.objects.create(
            profile=profile, title="Retrato", price=50
        )

        self.api.force_authenticate(maria)
        response = self.api.post(
            "/api/bookings/",
            {
                "package": package.pk,
                "date": "2026-11-20T10:00:00Z",
                "message": "primera",
            },
            format="json",
        )
        rejected_id = response.data["id"]

        self.api.force_authenticate(ana)
        response = self.api.post(
            f"/api/bookings/{rejected_id}/reject/", format="json"
        )
        self.assertEqual(response.data["status"], "rejected")
        self.assertEqual(Shoot.objects.count(), 0)
        self.assertEqual(Client.objects.count(), 0)

        self.api.force_authenticate(maria)
        response = self.api.post(
            "/api/bookings/",
            {
                "package": package.pk,
                "date": "2026-11-25T10:00:00Z",
                "message": "segunda",
            },
            format="json",
        )
        retry_id = response.data["id"]

        self.api.force_authenticate(ana)
        response = self.api.post(
            f"/api/bookings/{retry_id}/accept/", format="json"
        )
        self.assertEqual(response.data["status"], "accepted")
        self.assertEqual(Shoot.objects.count(), 1)
        self.assertEqual(Client.objects.count(), 1)
