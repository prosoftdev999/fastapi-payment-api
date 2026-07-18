import stripe

from app.core.config import settings


stripe.api_key = settings.stripe_secret_key


def create_subscription_checkout_session(
    *,
    user_id: str,
    email: str,
) -> stripe.checkout.Session:
    return stripe.checkout.Session.create(
        mode="subscription",
        customer_email=email,
        client_reference_id=user_id,
        line_items=[
            {
                "price": settings.stripe_price_id,
                "quantity": 1,
            }
        ],
        success_url=(
            f"{settings.frontend_success_url}"
            "?session_id={CHECKOUT_SESSION_ID}"
        ),
        cancel_url=settings.frontend_cancel_url,
        metadata={
            "user_id": user_id,
        },
        subscription_data={
            "metadata": {
                "user_id": user_id,
            }
        },
    )