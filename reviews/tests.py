from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from clients.models import Client
from users.models import User
from .models import Review


class ReviewTests(TestCase):
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
        cls.maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.review = Review.objects.create(
            photographer=cls.ana,
            customer=cls.maria,
            rating=5,
            comment="Excelente trabajo",
        )

    def setUp(self):
        self.api = APIClient()

    def test_customer_reviews_photographer(self):
        self.api.force_authenticate(self.luis)
        Client.objects.create(
            photographer=self.beto, user=self.luis, name="Luis F"
        )
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.beto.pk, "rating": 4, "comment": "Muy bien"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["customer_username"], "luis")
        self.assertEqual(response.data["photographer_username"], "beto")
        self.assertEqual(Review.objects.count(), 2)

    def test_rating_below_minimum_is_rejected(self):
        self.api.force_authenticate(self.luis)
        Client.objects.create(photographer=self.beto, user=self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("mínima", str(response.data))

    def test_rating_above_maximum_is_rejected(self):
        self.api.force_authenticate(self.luis)
        Client.objects.create(photographer=self.beto, user=self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 6},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("máxima", str(response.data))

    def test_missing_rating_is_rejected(self):
        self.api.force_authenticate(self.luis)
        Client.objects.create(photographer=self.beto, user=self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("obligatoria", str(response.data))

    def test_cannot_review_photographer_without_working_together(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("has trabajado", str(response.data))

    def test_cannot_review_a_customer(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.maria.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valorar fotógrafos", str(response.data))

    def test_photographer_cannot_create_review(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_review_same_photographer_twice(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.ana.pk, "rating": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Ya has valorado", str(response.data))

    def test_customer_edits_own_review(self):
        self.api.force_authenticate(self.maria)
        response = self.api.patch(
            f"/api/reviews/{self.review.pk}/",
            {"rating": 4, "comment": "Actualizado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 4)
        self.assertEqual(self.review.comment, "Actualizado")

    def test_customer_deletes_own_review(self):
        self.api.force_authenticate(self.maria)
        response = self.api.delete(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Review.objects.count(), 0)

    def test_customer_cannot_delete_others_review(self):
        self.api.force_authenticate(self.luis)
        response = self.api.delete(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_photographer_sees_received_reviews(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/reviews/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["customer_username"], "maria"
        )

    def test_customer_sees_written_reviews(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/reviews/")
        self.assertEqual(response.data["count"], 1)
        self.api.force_authenticate(self.luis)
        response = self.api.get("/api/reviews/")
        self.assertEqual(response.data["count"], 0)

    def test_any_authenticated_user_can_list_by_photographer(self):
        self.api.force_authenticate(self.luis)
        response = self.api.get(f"/api/reviews/?photographer={self.ana.pk}")
        self.assertEqual(response.data["count"], 1)
        response = self.api.get(f"/api/reviews/?photographer={self.beto.pk}")
        self.assertEqual(response.data["count"], 0)

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/reviews/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
