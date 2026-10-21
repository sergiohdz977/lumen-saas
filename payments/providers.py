import stripe
from django.conf import settings

# Thin wrapper around Stripe. Everything Stripe-specific lives here so
# the provider can be swapped later without touching models or views.


def create_checkout_session(
    amount_cents,
    currency,
    payment,
    success_url,
    cancel_url,
    destination_account=None,
    platform_fee_cents=None,
):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    kwargs = {}
    if destination_account:
        # Destination charge: Stripe moves the money to the
        # photographer right after the customer pays.
        kwargs["payment_intent_data"] = {
            "transfer_data": {"destination": destination_account},
        }
        if platform_fee_cents:
            kwargs["payment_intent_data"]["application_fee_amount"] = (
                platform_fee_cents
            )
    return stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount_cents,
                    "product_data": {"name": "Booking deposit"},
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "payment_id": str(payment.pk),
            "booking_id": str(payment.booking_id),
        },
        **kwargs,
    )


def create_connected_account(country):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Account.create(
        type="express",
        country=country,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
    )


def create_account_link(account_id):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{settings.SITE_URL}/payments/onboard/refresh/",
        return_url=f"{settings.SITE_URL}/payments/onboard/done/",
        type="account_onboarding",
    )


def create_customer(email):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Customer.create(email=email)


def create_subscription_session(
    customer_id, price_id, success_url, cancel_url
):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )


def construct_webhook_event(payload, signature):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )
