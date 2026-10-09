from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from .models import Client


class ClientEndpointsTests(TestCase):
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
        cls.client_of_a = Client.objects.create(
            photographer=cls.photographer_a,
            name="Cliente Ana",
            email="anacliente@test.com",
        )
        cls.client_of_b = Client.objects.create(
            photographer=cls.photographer_b,
            name="Cliente B",
        )

    def setUp(self):
        self.api = APIClient()

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/clients/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_list_is_denied(self):
        self.api.force_authenticate(self.customer)
        response = self.api.get("/api/clients/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_sees_only_own_clients(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get("/api/clients/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Cliente Ana")

    def test_photographer_retrieves_own_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get(f"/api/clients/{self.client_of_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Cliente Ana")

    def test_photographer_cannot_retrieve_others_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.get(f"/api/clients/{self.client_of_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_assigns_authenticated_photographer(self):
        self.api.force_authenticate(self.photographer_a)
        payload = {"name": "Nuevo Cliente", "email": "nuevo@test.com"}
        response = self.api.post("/api/clients/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        client = Client.objects.get(name="Nuevo Cliente")
        self.assertEqual(client.photographer, self.photographer_a)

    def test_create_ignores_photographer_sent_by_client(self):
        self.api.force_authenticate(self.photographer_a)
        payload = {
            "name": "Intento Spoof",
            "photographer": self.photographer_b.pk,
        }
        response = self.api.post("/api/clients/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        client = Client.objects.get(name="Intento Spoof")
        self.assertEqual(client.photographer, self.photographer_a)

    def test_update_own_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.patch(
            f"/api/clients/{self.client_of_a.pk}/",
            {"phone": "+5355555555"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client_of_a.refresh_from_db()
        self.assertEqual(self.client_of_a.phone, "+5355555555")

    def test_cannot_update_others_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.patch(
            f"/api/clients/{self.client_of_b.pk}/",
            {"name": "Hackeado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.client_of_b.refresh_from_db()
        self.assertEqual(self.client_of_b.name, "Cliente B")

    def test_delete_own_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.delete(f"/api/clients/{self.client_of_a.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Client.objects.filter(pk=self.client_of_a.pk).exists())

    def test_cannot_delete_others_client(self):
        self.api.force_authenticate(self.photographer_a)
        response = self.api.delete(f"/api/clients/{self.client_of_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Client.objects.filter(pk=self.client_of_b.pk).exists())

    def test_same_customer_cannot_be_duplicated_for_same_photographer(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Client.objects.create(
                    photographer=self.photographer_a,
                    user=self.customer,
                    name="Primera ficha",
                )
                Client.objects.create(
                    photographer=self.photographer_a,
                    user=self.customer,
                    name="Duplicada",
                )

    def test_same_customer_can_be_client_of_two_photographers(self):
        Client.objects.create(
            photographer=self.photographer_a,
            user=self.customer,
            name="Ficha A",
        )
        Client.objects.create(
            photographer=self.photographer_b,
            user=self.customer,
            name="Ficha B",
        )
        self.assertEqual(
            Client.objects.filter(user=self.customer).count(), 2
        )

    def test_create_ignores_user_sent_by_client(self):
        self.api.force_authenticate(self.photographer_a)
        payload = {"name": "Sin vincular", "user": self.customer.pk}
        response = self.api.post("/api/clients/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        client = Client.objects.get(name="Sin vincular")
        self.assertIsNone(client.user)
