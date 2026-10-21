import stripe
from django.conf import settings

# Thin wrapper around Stripe. Everything Stripe-specific lives here so
# the provider can be swapped later without touching models or views.


def create_checkout_session(
    amount_cents, currency, payment, success_url, cancel_url
):
    stripe.api_key = settings.STRIPE_SECRET_KEY
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
    )


def construct_webhook_event(payload, signature):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Webhook.construct_event(
        payload, signature, settings.STRIPE_WEBHOOK_SECRET
    )
