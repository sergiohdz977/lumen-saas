from datetime import datetime, timezone as dt_timezone

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from profiles.models import Package, PhotographerProfile
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
