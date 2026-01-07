import stripe
from .settings import settings

stripe.api_key = settings.stripe_secret_key

def create_checkout_session(customer_email: str, success_url: str, cancel_url: str) -> str:
    """
    Creates a subscription checkout session using STRIPE_PRICE_ID.
    Returns session URL to redirect the user.
    """
    if not settings.stripe_price_id:
        raise ValueError("STRIPE_PRICE_ID not set")

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        customer_email=customer_email,
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url

