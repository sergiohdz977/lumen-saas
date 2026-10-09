from datetime import datetime, timezone as dt_timezone

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from clients.models import Client
from .models import Shoot


class ShootEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.photographer_a = User.objects.create_user(
            username="fotografa",
            email="fotografa@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.photographer_b = User.objects.create_user(
            username="fotografo_b",
            email="b@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="cliente",
            email="cliente@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.client_a = Client.objects.create(
            photographer=cls.photographer_a,
            name="Cliente Ana",
        )
        cls.client_b = Client.objects.create(
            photographer=cls.photographer_b,
            name="Cliente B",
        )
        cls.shoot_a = Shoot.objects.create(
            client=cls.client_a,
            title="Boda Maria",
            shoot_type="wedding",
            date=datetime(2026, 11, 20, 10, 0, tzinfo=dt_timezone.utc),
        )
        cls.shoot_b = Shoot.objects.create(
            client=cls.client_b,
            title="Sesion de otro",
            shoot_type="portrait",
            date=datetime(2026, 11, 21, 10, 0, tzinfo=dt_timezone.utc),
        )
        cls.valid_payload = {
            "client": cls.client_a.pk,
            "title": "Bautizo",
            "shoot_type": "baptism",
            "date": "2026-12-01T15:00:00Z",
        }

    def setUp(self):
        self.api = APIClient()

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/shoots/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_list_is_denied(self):
        self.api.force_authenticate(self.customer)
        response = self.api.get("/api/shoots/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_sees_only_own_shoots(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get("/api/shoots/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Boda Maria")

    def test_photographer_retrieves_own_shoot(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get(f"/api/shoots/{self.shoot_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Boda Maria")

    def test_photographer_cannot_retrieve_others_shoot(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get(f"/api/shoots/{self.shoot_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_forces_status_booked(self):
        self.api.force_authenticate(self.photographer_a)
        payload = {**self.valid_payload, "status": "delivered"}
        response = self.api.post("/api/shoots/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        shoot = Shoot.objects.get(title="Bautizo")
        self.assertEqual(shoot.status, Shoot.Status.BOOKED)
        self.assertEqual(shoot.client.photographer, self.photographer_a)

    def test_create_with_others_client_is_rejected(self):
        self.api.force_authenticate(self.photographer_a)
        payload = {**self.valid_payload, "client": self.client_b.pk}
        response = self.api.post("/api/shoots/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_transition_booked_to_editing(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.patch(
            f"/api/shoots/{self.shoot_a.pk}/",
            {"status": "editing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.shoot_a.refresh_from_db()
        self.assertEqual(self.shoot_a.status, Shoot.Status.EDITING)

    def test_status_transition_editing_to_delivered(self):
        self.api.force_authenticate(self.photographer_a)
        self.shoot_a.status = Shoot.Status.EDITING
        self.shoot_a.save()
        response = self.api.patch(
            f"/api/shoots/{self.shoot_a.pk}/",
            {"status": "delivered"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.shoot_a.refresh_from_db()
        self.assertEqual(self.shoot_a.status, Shoot.Status.DELIVERED)

    def test_status_cannot_go_backwards(self):
        self.api.force_authenticate(self.photographer_a)
        self.shoot_a.status = Shoot.Status.DELIVERED
        self.shoot_a.save()
        response = self.api.patch(
            f"/api/shoots/{self.shoot_a.pk}/",
            {"status": "editing"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.shoot_a.refresh_from_db()
        self.assertEqual(self.shoot_a.status, Shoot.Status.DELIVERED)

    def test_update_own_shoot_title(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.patch(
            f"/api/shoots/{self.shoot_a.pk}/",
            {"title": "Titulo nuevo"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.shoot_a.refresh_from_db()
        self.assertEqual(self.shoot_a.title, "Titulo nuevo")

    def test_cannot_update_others_shoot(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.patch(
            f"/api/shoots/{self.shoot_b.pk}/",
            {"title": "Hackeado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.shoot_b.refresh_from_db()
        self.assertEqual(self.shoot_b.title, "Sesion de otro")

    def test_delete_own_shoot(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.delete(f"/api/shoots/{self.shoot_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Shoot.objects.filter(pk=self.shoot_a.pk).exists())

    def test_cannot_delete_others_shoot(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.delete(f"/api/shoots/{self.shoot_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Shoot.objects.filter(pk=self.shoot_b.pk).exists())
