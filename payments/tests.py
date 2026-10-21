from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from bookings.models import BookingRequest
from clients.models import Client
from notifications.models import Notification
from profiles.models import Package, PhotographerProfile
from shoots.models import Shoot
from users.models import User

from .models import Payment


def _session_event(payment=None, session_id="cs_test_1", metadata=None):
    if payment is not None:
        metadata = {"payment_id": str(payment.pk), **(metadata or {})}
    return {
        "type": "checkout.session.completed",
        "data": {"object": {"id": session_id, "metadata": metadata or {}}},
    }


class PaymentTestCase(TestCase):
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
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
        )
        cls.profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.package = Package.objects.create(
            profile=cls.profile,
            title="Wedding package",
            price=Decimal("200.00"),
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.shoot = Shoot.objects.create(
            client=cls.client_maria,
            title="Maria wedding",
            shoot_type="wedding",
            date="2026-11-20T10:00:00Z",
        )
        cls.booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date="2026-11-20T10:00:00Z",
            status=BookingRequest.Status.ACCEPTED,
        )
        cls.pending_booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date="2026-12-05T10:00:00Z",
        )

    def setUp(self):
        self.api = APIClient()


class CheckoutTests(PaymentTestCase):
    def _patch_session(self):
        return patch(
            "payments.providers.create_checkout_session",
            return_value=SimpleNamespace(
                id="cs_test_123", url="https://stripe.test/pay/cs_test_123"
            ),
        )

    def test_checkout_creates_pending_payment_with_deposit(self):
        self.api.force_authenticate(self.maria)
        with self._patch_session() as mock_create:
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("checkout_url", response.data)
        payment = Payment.objects.get(booking=self.booking)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount_cents, 4000)
        self.assertEqual(mock_create.call_args.kwargs["amount_cents"], 4000)

    def test_checkout_requires_accepted_booking(self):
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.pending_booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("accepted", str(response.data))

    def test_checkout_of_another_customers_booking_is_denied(self):
        self.api.force_authenticate(self.luis)
        with self._patch_session():
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_cannot_checkout(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/payments/checkout/",
            {"booking": self.booking.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_checkout_is_denied(self):
        response = self.api.post(
            "/api/payments/checkout/",
            {"booking": self.booking.pk},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_paid_deposit_cannot_be_paid_again(self):
        Payment.objects.create(
            booking=self.booking,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_test_paid",
            status=Payment.Status.PAID,
        )
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been paid", str(response.data))


class WebhookTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            booking=self.booking,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_test_123",
        )

    def _post_webhook(self, event):
        with patch(
            "payments.providers.construct_webhook_event",
            return_value=event,
        ):
            return self.api.post(
                "/api/payments/webhook/", {"noop": True}, format="json"
            )

    def test_completed_event_marks_payment_paid_and_notifies(self):
        response = self._post_webhook(_session_event(payment=self.payment))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.assertIsNotNone(self.payment.paid_at)
        titles = set(Notification.objects.values_list("title", flat=True))
        self.assertIn("Deposit received", titles)
        self.assertIn("Payment confirmed", titles)

    def test_same_event_twice_is_processed_once(self):
        event = _session_event(payment=self.payment)
        self._post_webhook(event)
        self._post_webhook(event)
        self.assertEqual(Notification.objects.count(), 2)

    def test_unknown_session_is_ignored(self):
        event = _session_event(session_id="cs_test_ghost")
        response = self._post_webhook(event)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_invalid_signature_is_rejected(self):
        with patch(
            "payments.providers.construct_webhook_event",
            side_effect=stripe.SignatureVerificationError(
                "bad signature", "sig=bad", http_body=""
            ),
        ):
            response = self.api.post(
                "/api/payments/webhook/", {"noop": True}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_event_types_are_ignored(self):
        event = {"type": "invoice.paid", "data": {"object": {"id": "in_1"}}}
        response = self._post_webhook(event)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)


class PaymentVisibilityTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            booking=self.booking,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_test_vis",
        )

    def test_customer_lists_only_own_payments(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.payment.pk])

    def test_photographer_lists_payments_received(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/payments/")
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.payment.pk])

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/payments/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
