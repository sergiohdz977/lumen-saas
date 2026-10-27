from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from bookings.models import BookingRequest
from clients.models import Client
from config.asgi import application
from profiles.models import Package, PhotographerProfile
from shoots.models import Shoot
from users.models import User

from .models import Notification
from .services import notify


class NotificationRestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
        )
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
        )
        cls.note_maria = Notification.objects.create(
            user=cls.maria,
            title="Booking accepted",
            message="Your session was accepted",
        )
        Notification.objects.create(
            user=cls.luis, title="De luis", message="otra notificacion"
        )

    def setUp(self):
        self.api = APIClient()

    def test_customer_lists_only_their_notifications(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [item["title"] for item in response.data["results"]]
        self.assertEqual(titles, ["Booking accepted"])

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/notifications/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_mark_one_as_read(self):
        self.api.force_authenticate(self.maria)
        url = f"/api/notifications/{self.note_maria.pk}/read/"
        response = self.api.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.note_maria.refresh_from_db()
        self.assertTrue(self.note_maria.is_read)

    def test_customer_cannot_read_someone_elses_notification(self):
        other = Notification.objects.get(title="De luis")
        self.api.force_authenticate(self.maria)
        url = f"/api/notifications/{other.pk}/read/"
        response = self.api.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_all_as_read(self):
        Notification.objects.create(user=self.maria, title="Segunda")
        self.api.force_authenticate(self.maria)
        response = self.api.post("/api/notifications/read-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated"], 2)
        unread = Notification.objects.filter(
            user=self.maria, is_read=False
        ).exists()
        self.assertFalse(unread)

    def test_unread_filter_returns_only_unread(self):
        Notification.objects.create(user=self.maria, title="Recien llegada")
        Notification.objects.filter(
            user=self.maria, title="Booking accepted"
        ).update(is_read=True)
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/notifications/?unread=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["title"], "Recien llegada"
        )


class NotifyIntegrationTests(TestCase):
    """The three business events that create notifications."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
        )
        cls.profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.package = Package.objects.create(
            profile=cls.profile, title="Boda completa", price=200
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.shoot = Shoot.objects.create(
            client=cls.client_maria,
            title="Boda",
            shoot_type="boda",
            date="2026-11-20T10:00:00Z",
        )
        cls.booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date="2026-12-01T10:00:00Z",
        )

    def setUp(self):
        self.api = APIClient()

    def test_accepting_a_booking_notifies_the_customer(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(f"/api/bookings/{self.booking.pk}/accept/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        note = Notification.objects.get(user=self.maria)
        self.assertEqual(note.title, "Booking accepted")

    def test_new_review_notifies_the_photographer(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/reviews/",
            {
                "photographer": self.ana.pk,
                "rating": 5,
                "comment": "Hermosa",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        note = Notification.objects.get(user=self.ana)
        self.assertEqual(note.title, "New review")

    def test_gallery_creation_notifies_the_customer(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        note = Notification.objects.get(user=self.maria)
        self.assertEqual(note.title, "Your photos are ready")


class NotificationWebSocketTests(TransactionTestCase):
    def test_connected_user_receives_a_live_push(self):
        user = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
        )
        token = str(AccessToken.for_user(user))

        async def scenario():
            path = f"/ws/notifications/?token={token}"
            communicator = WebsocketCommunicator(application, path)
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await sync_to_async(notify)(
                user, "Booking accepted", "All set"
            )
            payload = await communicator.receive_json_from()
            self.assertEqual(payload["title"], "Booking accepted")
            self.assertEqual(payload["message"], "All set")
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_anonymous_connection_is_rejected(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application, "/ws/notifications/"
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_invalid_token_is_rejected(self):
        async def scenario():
            communicator = WebsocketCommunicator(
                application, "/ws/notifications/?token=basura"
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()
