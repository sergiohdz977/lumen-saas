from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from bookings.models import BookingRequest
from profiles.models import Package, PhotographerProfile
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
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.beto_profile = PhotographerProfile.objects.create(
            user=cls.beto,
            studio_name="Beto Photo",
            slug="beto-photo",
            is_published=True,
        )
        cls.package = Package.objects.create(
            profile=cls.ana_profile, title="Boda completa", price=200
        )
        cls.package_beto = Package.objects.create(
            profile=cls.beto_profile, title="Retrato", price=100
        )
        cls.booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date=timezone.now() + timedelta(days=30),
            status=BookingRequest.Status.COMPLETED,
        )
        cls.booking_luis = BookingRequest.objects.create(
            customer=cls.luis,
            package=cls.package_beto,
            date=timezone.now() + timedelta(days=30),
            status=BookingRequest.Status.COMPLETED,
        )
        cls.review = Review.objects.create(
            photographer=cls.ana,
            customer=cls.maria,
            booking=cls.booking,
            rating=5,
            comment="Excelente trabajo",
        )

    def setUp(self):
        self.api = APIClient()

    def _completed_booking(self, customer, package):
        return BookingRequest.objects.create(
            customer=customer,
            package=package,
            date=timezone.now() + timedelta(days=45),
            status=BookingRequest.Status.COMPLETED,
        )

    def test_customer_reviews_photographer(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {
                "photographer": self.beto.pk,
                "booking": self.booking_luis.pk,
                "rating": 4,
                "comment": "Muy bien",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["customer_username"], "luis")
        self.assertEqual(response.data["photographer_username"], "beto")
        self.assertEqual(response.data["profile_slug"], "beto-photo")
        self.assertEqual(response.data["booking"], self.booking_luis.pk)
        self.assertEqual(Review.objects.count(), 2)

    def test_rating_below_minimum_is_rejected(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {
                "photographer": self.beto.pk,
                "booking": self.booking_luis.pk,
                "rating": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at least", str(response.data))

    def test_rating_above_maximum_is_rejected(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {
                "photographer": self.beto.pk,
                "booking": self.booking_luis.pk,
                "rating": 6,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at most", str(response.data))

    def test_missing_rating_is_rejected(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.beto.pk, "booking": self.booking_luis.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required", str(response.data))

    def test_review_requires_a_booking(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed booking", str(response.data))

    def test_cannot_review_uncompleted_booking(self):
        self.api.force_authenticate(self.luis)
        pending = BookingRequest.objects.create(
            customer=self.luis,
            package=self.package_beto,
            date=timezone.now() + timedelta(days=10),
        )
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.beto.pk, "booking": pending.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("completed bookings", str(response.data))

    def test_cannot_review_with_another_customers_booking(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.ana.pk, "booking": self.booking.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not belong", str(response.data))

    def test_booking_must_match_the_reviewed_photographer(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.ana.pk, "booking": self.booking_luis.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not match", str(response.data))

    def test_cannot_review_a_customer(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.maria.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only review photographers", str(response.data))

    def test_photographer_cannot_create_review(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/reviews/", {"photographer": self.beto.pk, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_review_same_session_twice(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.ana.pk, "booking": self.booking.pk, "rating": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already reviewed this session", str(response.data))

    def test_can_review_again_after_another_completed_session(self):
        second = self._completed_booking(self.maria, self.package)
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/reviews/",
            {"photographer": self.ana.pk, "booking": second.pk, "rating": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Review.objects.filter(customer=self.maria).count(), 2
        )

    def test_customer_cannot_edit_own_review(self):
        self.api.force_authenticate(self.maria)
        response = self.api.patch(
            f"/api/reviews/{self.review.pk}/",
            {"rating": 4, "comment": "Actualizado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 5)

    def test_customer_cannot_replace_own_review(self):
        self.api.force_authenticate(self.maria)
        response = self.api.put(
            f"/api/reviews/{self.review.pk}/",
            {"photographer": self.ana.pk, "booking": self.booking.pk, "rating": 4},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_customer_deletes_own_review(self):
        self.api.force_authenticate(self.maria)
        response = self.api.delete(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Review.objects.count(), 0)

    def test_customer_cannot_delete_others_review(self):
        self.api.force_authenticate(self.luis)
        response = self.api.delete(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_photographer_cannot_delete_received_review(self):
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/reviews/{self.review.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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


class ReviewReplyTests(TestCase):
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
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.package = Package.objects.create(
            profile=cls.ana_profile, title="Boda completa", price=200
        )
        cls.booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date=timezone.now() + timedelta(days=30),
            status=BookingRequest.Status.COMPLETED,
        )
        cls.review = Review.objects.create(
            photographer=cls.ana,
            customer=cls.maria,
            booking=cls.booking,
            rating=5,
            comment="Excelente trabajo",
        )

    def setUp(self):
        self.api = APIClient()

    def test_photographer_replies_to_a_review(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Thank you, Maria!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.review.refresh_from_db()
        self.assertEqual(self.review.reply, "Thank you, Maria!")
        self.assertIsNotNone(self.review.replied_at)
        self.assertEqual(response.data["reply"], "Thank you, Maria!")

    def test_reply_happens_only_once(self):
        self.api.force_authenticate(self.ana)
        self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "First reply"},
            format="json",
        )
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Second reply"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already replied", str(response.data))
        self.review.refresh_from_db()
        self.assertEqual(self.review.reply, "First reply")

    def test_another_photographer_cannot_reply(self):
        self.api.force_authenticate(self.beto)
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Not mine"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_reply(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Reply to myself"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_empty_reply_is_rejected(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be empty", str(response.data))

    def test_too_long_reply_is_rejected(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "x" * 501},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("500", str(response.data))

    def test_customer_sees_the_reply_on_her_reviews(self):
        self.api.force_authenticate(self.ana)
        self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Thanks!"},
            format="json",
        )
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/reviews/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["reply"], "Thanks!")

    def test_review_reply_notifies_the_customer(self):
        from notifications.models import Notification

        self.api.force_authenticate(self.ana)
        self.api.post(
            f"/api/reviews/{self.review.pk}/reply/",
            {"reply": "Thanks for the kind words!"},
            format="json",
        )
        note = Notification.objects.get(user=self.maria)
        self.assertEqual(note.title, "Reply to your review")
        self.assertEqual(note.link, "dashboard.html?tab=reviews")


class ReviewAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )

    def test_review_with_unknown_photographer_is_rejected(self):
        self.api = APIClient()
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/reviews/", {"photographer": 9999, "rating": 5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)
