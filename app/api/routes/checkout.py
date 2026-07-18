import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.checkout import CheckoutSessionResponse
from app.services.stripe_service import (
    create_subscription_checkout_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/checkout",
    tags=["Checkout"],
)


@router.post(
    "/session",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(
    current_user: User = Depends(get_current_user),
) -> CheckoutSessionResponse:
    try:
        session = create_subscription_checkout_session(
            user_id=str(current_user.id),
            email=current_user.email,
        )

    except Exception as exc:
        # Print full traceback into Docker logs
        logger.exception("Stripe Checkout Session creation failed")

        # Return the actual Stripe error while debugging
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    if not session.url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe did not return a checkout URL.",
        )

    return CheckoutSessionResponse(
        checkout_url=session.url,
        session_id=session.id,
    )