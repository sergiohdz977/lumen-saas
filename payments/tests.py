from datetime import timedelta
from decimal import Decimal
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from bookings.models import BookingRequest
from clients.models import Client
from galleries.models import Gallery
from notifications.models import Notification
from profiles.models import Package, PhotographerProfile
from shoots.models import Shoot
from users.models import User

from .models import Payment
from .services import booking_is_fully_paid


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
            stripe_account_id="acct_test_1",
            stripe_onboarded=True,
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
        self.assertEqual(payment.kind, Payment.Kind.DEPOSIT)
        self.assertEqual(payment.amount_cents, 4000)
        self.assertEqual(mock_create.call_args.kwargs["amount_cents"], 4000)
        self.assertEqual(
            mock_create.call_args.kwargs["destination_account"], "acct_test_1"
        )

    def test_checkout_blocked_when_photographer_not_onboarded(self):
        self.profile.stripe_onboarded = False
        self.profile.save(update_fields=["stripe_onboarded"])
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("setting up payments", str(response.data))

    def test_blocked_checkout_alerts_the_photographer(self):
        self.profile.stripe_onboarded = False
        self.profile.save(update_fields=["stripe_onboarded"])
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        alert = Notification.objects.get(
            user=self.ana, title="Stripe not connected"
        )
        self.assertFalse(alert.is_read)
        self.assertIn("maria", alert.message)
        self.assertIn("connect Stripe", alert.message)

    def test_stripe_alert_is_not_duplicated_while_unread(self):
        self.profile.stripe_onboarded = False
        self.profile.save(update_fields=["stripe_onboarded"])
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
            self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        alerts = Notification.objects.filter(
            user=self.ana, title="Stripe not connected"
        )
        self.assertEqual(alerts.count(), 1)

    def test_connected_photographer_gets_no_stripe_alert(self):
        self.api.force_authenticate(self.maria)
        with self._patch_session():
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(
            Notification.objects.filter(
                user=self.ana, title="Stripe not connected"
            ).exists()
        )

    def test_platform_fee_is_computed_when_configured(self):
        self.api.force_authenticate(self.maria)
        with self._patch_session() as mock_create:
            with override_settings(STRIPE_PLATFORM_FEE_PERCENTAGE=10):
                self.api.post(
                    "/api/payments/checkout/",
                    {"booking": self.booking.pk},
                    format="json",
                )
        self.assertEqual(
            mock_create.call_args.kwargs["platform_fee_cents"], 400
        )

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

    def test_account_updated_marks_profile_onboarded(self):
        self.profile.stripe_onboarded = False
        self.profile.save(update_fields=["stripe_onboarded"])
        event = {
            "type": "account.updated",
            "data": {
                "object": {
                    "id": "acct_test_1",
                    "details_submitted": True,
                }
            },
        }
        with patch(
            "payments.providers.construct_webhook_event",
            return_value=event,
        ):
            response = self.api.post(
                "/api/payments/webhook/", {"noop": True}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.stripe_onboarded)

    def test_account_updated_for_unknown_account_is_ignored(self):
        event = {
            "type": "account.updated",
            "data": {
                "object": {"id": "acct_ghost", "details_submitted": True}
            },
        }
        with patch(
            "payments.providers.construct_webhook_event",
            return_value=event,
        ):
            response = self.api.post(
                "/api/payments/webhook/", {"noop": True}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

    def _subscription_event(
        self,
        type_="customer.subscription.updated",
        sub_id="sub_1",
        customer="cus_test_1",
        status="active",
    ):
        return {
            "type": type_,
            "data": {
                "object": {
                    "id": sub_id,
                    "customer": customer,
                    "status": status,
                }
            },
        }

    def test_subscription_active_marks_profile_pro(self):
        self.profile.stripe_customer_id = "cus_test_1"
        self.profile.save(update_fields=["stripe_customer_id"])
        response = self._post_webhook(self._subscription_event())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "pro")
        self.assertEqual(self.profile.subscription_id, "sub_1")

    def test_subscription_canceled_downgrades_to_free(self):
        self.profile.stripe_customer_id = "cus_test_1"
        self.profile.plan = "pro"
        self.profile.subscription_id = "sub_1"
        self.profile.save(
            update_fields=[
                "stripe_customer_id",
                "plan",
                "subscription_id",
            ]
        )
        response = self._post_webhook(
            self._subscription_event(status="canceled")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "free")

    def test_subscription_deleted_clears_plan(self):
        self.profile.stripe_customer_id = "cus_test_1"
        self.profile.plan = "pro"
        self.profile.subscription_id = "sub_1"
        self.profile.save(
            update_fields=[
                "stripe_customer_id",
                "plan",
                "subscription_id",
            ]
        )
        response = self._post_webhook(
            self._subscription_event(
                type_="customer.subscription.deleted"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "free")
        self.assertEqual(self.profile.subscription_id, "")

    def test_unknown_subscription_is_ignored(self):
        response = self._post_webhook(
            self._subscription_event(
                sub_id="sub_ghost", customer="cus_ghost"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "free")
        self.assertEqual(self.profile.subscription_id, "")


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


class OnboardTests(PaymentTestCase):
    def _patch_provider(self, account_id="acct_new"):
        stack = ExitStack()
        stack.enter_context(
            patch(
                "payments.providers.create_connected_account",
                return_value=SimpleNamespace(id=account_id),
            )
        )
        stack.enter_context(
            patch(
                "payments.providers.create_account_link",
                return_value=SimpleNamespace(
                    url=f"https://connect.stripe.test/{account_id}"
                ),
            )
        )
        return stack

    def test_photographer_gets_onboarding_url(self):
        self.profile.stripe_account_id = ""
        self.profile.save(update_fields=["stripe_account_id"])
        self.api.force_authenticate(self.ana)
        with self._patch_provider():
            response = self.api.post(
                "/api/payments/onboard/", {"country": "es"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("onboarding_url", response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_account_id, "acct_new")

    def test_second_onboarding_reuses_existing_account(self):
        self.api.force_authenticate(self.ana)
        with self._patch_provider():
            response = self.api.post(
                "/api/payments/onboard/", {"country": "ES"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_account_id, "acct_test_1")

    def test_customer_cannot_onboard(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/payments/onboard/", {"country": "US"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_without_profile_is_rejected(self):
        carlos = User.objects.create_user(
            username="carlos",
            email="carlos@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        self.api.force_authenticate(carlos)
        response = self.api.post(
            "/api/payments/onboard/", {"country": "US"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photographer profile", str(response.data))

    def test_invalid_country_is_rejected(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/payments/onboard/", {"country": "Spain"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("2-letter", str(response.data))


class UpgradeTests(PaymentTestCase):
    def _patch_upgrade(self, price_id="price_pro_1"):
        stack = ExitStack()
        stack.enter_context(override_settings(STRIPE_PRO_PRICE_ID=price_id))
        stack.enter_context(
            patch(
                "payments.providers.create_customer",
                return_value=SimpleNamespace(id="cus_test_1"),
            )
        )
        stack.enter_context(
            patch(
                "payments.providers.create_subscription_session",
                return_value=SimpleNamespace(
                    url="https://checkout.stripe.test/sub_1"
                ),
            )
        )
        return stack

    def test_photographer_gets_subscription_checkout_url(self):
        self.api.force_authenticate(self.ana)
        with self._patch_upgrade():
            response = self.api.post(
                "/api/payments/upgrade/", {}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("checkout_url", response.data)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_customer_id, "cus_test_1")

    def test_stripe_customer_is_created_only_once(self):
        self.api.force_authenticate(self.ana)
        with override_settings(STRIPE_PRO_PRICE_ID="price_pro_1"), patch(
            "payments.providers.create_customer",
            return_value=SimpleNamespace(id="cus_test_1"),
        ) as mock_customer, patch(
            "payments.providers.create_subscription_session",
            return_value=SimpleNamespace(
                url="https://checkout.stripe.test/sub_1"
            ),
        ):
            self.api.post("/api/payments/upgrade/", {}, format="json")
            self.api.post("/api/payments/upgrade/", {}, format="json")
        self.assertEqual(mock_customer.call_count, 1)

    def test_already_on_pro_is_rejected(self):
        self.profile.plan = "pro"
        self.profile.save(update_fields=["plan"])
        self.api.force_authenticate(self.ana)
        with self._patch_upgrade():
            response = self.api.post(
                "/api/payments/upgrade/", {}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already", str(response.data))

    def test_upgrade_without_price_id_is_rejected(self):
        self.api.force_authenticate(self.ana)
        with override_settings(STRIPE_PRO_PRICE_ID=""):
            response = self.api.post(
                "/api/payments/upgrade/", {}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not configured", str(response.data))

    def test_customer_cannot_upgrade(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/payments/upgrade/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_without_profile_is_rejected(self):
        carlos = User.objects.create_user(
            username="carlos",
            email="carlos@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        self.api.force_authenticate(carlos)
        with self._patch_upgrade():
            response = self.api.post(
                "/api/payments/upgrade/", {}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photographer profile", str(response.data))

    def test_profile_shows_plan(self):
        response = self.api.get(f"/api/profiles/{self.profile.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["plan"], "free")


class BalanceCheckoutTests(PaymentTestCase):
    def _prepare(self, confirmed=True, deposit_paid=True, gallery=True):
        self.shoot.booking = self.booking
        self.shoot.save(update_fields=["booking"])
        if confirmed:
            self.booking.status = BookingRequest.Status.CONFIRMED
            self.booking.save(update_fields=["status"])
        if deposit_paid:
            Payment.objects.create(
                booking=self.booking,
                kind=Payment.Kind.DEPOSIT,
                customer=self.maria,
                photographer=self.ana,
                amount_cents=4000,
                stripe_session_id="cs_dep_paid",
                status=Payment.Status.PAID,
            )
        if gallery:
            Gallery.objects.create(shoot=self.shoot)

    def _checkout(self, kind="balance"):
        self.api.force_authenticate(self.maria)
        with patch(
            "payments.providers.create_checkout_session",
            return_value=SimpleNamespace(
                id="cs_test_bal", url="https://stripe.test/pay/cs_test_bal"
            ),
        ) as mock_create:
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk, "kind": kind},
                format="json",
            )
        return response, mock_create

    def test_balance_checkout_charges_remaining_80_percent(self):
        self._prepare()
        response, mock_create = self._checkout()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(
            booking=self.booking, kind=Payment.Kind.BALANCE
        )
        self.assertEqual(payment.amount_cents, 16000)
        self.assertEqual(
            mock_create.call_args.kwargs["amount_cents"], 16000
        )

    def test_balance_requires_confirmed_booking(self):
        self._prepare(confirmed=False)
        response, _ = self._checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirmed", str(response.data))

    def test_balance_requires_paid_deposit(self):
        self._prepare(deposit_paid=False)
        response, _ = self._checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("deposit", str(response.data))

    def test_balance_requires_gallery(self):
        self._prepare(gallery=False)
        response, _ = self._checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gallery is not ready", str(response.data))

    def test_balance_cannot_be_paid_twice(self):
        self._prepare()
        Payment.objects.create(
            booking=self.booking,
            kind=Payment.Kind.BALANCE,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=16000,
            stripe_session_id="cs_bal_paid",
            status=Payment.Status.PAID,
        )
        response, _ = self._checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been paid", str(response.data))

    def test_invalid_kind_is_rejected(self):
        self._prepare()
        response, _ = self._checkout(kind="full")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_deposit_checkout_still_works_for_legacy_accepted(self):
        self.api.force_authenticate(self.maria)
        with patch(
            "payments.providers.create_checkout_session",
            return_value=SimpleNamespace(
                id="cs_test_dep", url="https://stripe.test/pay/cs_test_dep"
            ),
        ):
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(
            booking=self.booking, kind=Payment.Kind.DEPOSIT
        )
        self.assertEqual(payment.amount_cents, 4000)


class WebhookConfirmationTests(PaymentTestCase):
    def setUp(self):
        super().setUp()
        self.booking.status = (
            BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT
        )
        self.booking.deposit_deadline = timezone.now() + timedelta(hours=48)
        self.booking.save(update_fields=["status", "deposit_deadline"])
        self.payment = Payment.objects.create(
            booking=self.booking,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_test_conf",
        )

    def _post_webhook(self, event):
        with patch(
            "payments.providers.construct_webhook_event",
            return_value=event,
        ):
            return self.api.post(
                "/api/payments/webhook/", {"noop": True}, format="json"
            )

    def test_deposit_payment_confirms_the_booking(self):
        response = self._post_webhook(_session_event(payment=self.payment))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.CONFIRMED)
        message = Notification.objects.get(
            user=self.maria, title="Payment confirmed"
        ).message
        self.assertIn("confirmed", message)

    def test_balance_payment_keeps_the_booking_confirmed(self):
        self.booking.status = BookingRequest.Status.CONFIRMED
        self.booking.save(update_fields=["status"])
        Payment.objects.create(
            booking=self.booking,
            kind=Payment.Kind.DEPOSIT,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_test_conf_dep",
            status=Payment.Status.PAID,
        )
        balance = Payment.objects.create(
            booking=self.booking,
            kind=Payment.Kind.BALANCE,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=16000,
            stripe_session_id="cs_test_conf_bal",
        )
        response = self._post_webhook(
            _session_event(payment=balance, session_id="cs_test_conf_bal")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        balance.refresh_from_db()
        self.assertEqual(balance.status, Payment.Status.PAID)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.CONFIRMED)
        titles = set(Notification.objects.values_list("title", flat=True))
        self.assertIn("Balance received", titles)
        self.assertIn("Payment confirmed", titles)


class FullyPaidHelperTests(PaymentTestCase):
    def _paid(self, kind, stripe_id):
        Payment.objects.create(
            booking=self.booking,
            kind=kind,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id=stripe_id,
            status=Payment.Status.PAID,
        )

    def test_no_payments_means_not_fully_paid(self):
        self.assertFalse(booking_is_fully_paid(self.booking))

    def test_deposit_only_is_not_fully_paid(self):
        self._paid(Payment.Kind.DEPOSIT, "cs_f1")
        self.assertFalse(booking_is_fully_paid(self.booking))

    def test_deposit_and_balance_are_fully_paid(self):
        self._paid(Payment.Kind.DEPOSIT, "cs_f1")
        self._paid(Payment.Kind.BALANCE, "cs_f2")
        self.assertTrue(booking_is_fully_paid(self.booking))

    def test_pending_payments_do_not_count(self):
        Payment.objects.create(
            booking=self.booking,
            kind=Payment.Kind.DEPOSIT,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_p1",
        )
        Payment.objects.create(
            booking=self.booking,
            kind=Payment.Kind.BALANCE,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=16000,
            stripe_session_id="cs_p2",
        )
        self.assertFalse(booking_is_fully_paid(self.booking))

    def test_missing_booking_counts_as_paid(self):
        self.assertTrue(booking_is_fully_paid(None))


class ConfirmSessionTests(PaymentTestCase):
    def _prepare(self, payment_status="paid"):
        self.booking.status = (
            BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT
        )
        self.booking.save(update_fields=["status"])
        self.payment = Payment.objects.create(
            booking=self.booking,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000,
            stripe_session_id="cs_confirm_1",
        )
        return {
            "id": "cs_confirm_1",
            "payment_status": payment_status,
            "metadata": {"payment_id": str(self.payment.pk)},
        }

    def _confirm(self, session, user=None):
        self.api.force_authenticate(user or self.maria)
        with patch(
            "payments.providers.retrieve_checkout_session",
            return_value=session,
        ):
            return self.api.post(
                "/api/payments/confirm-session/",
                {"session_id": session["id"]},
                format="json",
            )

    def test_success_page_confirms_payment_and_booking(self):
        session = self._prepare()
        response = self._confirm(session)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PAID)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingRequest.Status.CONFIRMED)
        self.assertEqual(response.data["booking_status"], "confirmed")

    def test_processing_session_stays_pending(self):
        session = self._prepare(payment_status="unpaid")
        response = self._confirm(session)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.booking.refresh_from_db()
        self.assertEqual(
            self.booking.status,
            BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT,
        )

    def test_confirming_someone_elses_session_is_denied(self):
        session = self._prepare()
        response = self._confirm(session, user=self.luis)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_session_is_rejected(self):
        self._prepare()
        session = {
            "id": "cs_ghost",
            "payment_status": "paid",
            "metadata": {},
        }
        response = self._confirm(session)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("could not find", str(response.data))

    def test_invalid_stripe_session_is_rejected(self):
        self.api.force_authenticate(self.maria)
        with patch(
            "payments.providers.retrieve_checkout_session",
            side_effect=stripe.InvalidRequestError(
                "No such checkout session", "session_id"
            ),
        ):
            response = self.api.post(
                "/api/payments/confirm-session/",
                {"session_id": "cs_bad"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not exist", str(response.data))

    def test_missing_session_id_is_rejected(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/payments/confirm-session/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_double_confirmation_notifies_once(self):
        session = self._prepare()
        self._confirm(session)
        self._confirm(session)
        self.assertEqual(Notification.objects.count(), 2)

    def test_checkout_success_url_carries_session_id(self):
        self.api.force_authenticate(self.maria)
        with patch(
            "payments.providers.create_checkout_session",
            return_value=SimpleNamespace(
                id="cs_test_url", url="https://stripe.test/pay/cs_test_url"
            ),
        ) as mock_create:
            response = self.api.post(
                "/api/payments/checkout/",
                {"booking": self.booking.pk},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn(
            "{CHECKOUT_SESSION_ID}",
            mock_create.call_args.kwargs["success_url"],
        )
