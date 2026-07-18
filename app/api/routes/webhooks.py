from datetime import UTC, datetime
from uuid import UUID
import json
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.invoice import Invoice
from app.models.subscription import Subscription
from app.models.user import User
from app.models.webhook_event import WebhookEvent


router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)


def timestamp_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None

    return datetime.fromtimestamp(value, tz=UTC)


async def find_user_by_customer_id(
    db: AsyncSession,
    customer_id: str | None,
) -> User | None:
    if not customer_id:
        return None

    result = await db.execute(
        select(User).where(
            User.stripe_customer_id == customer_id
        )
    )
    return result.scalar_one_or_none()


async def find_user_from_metadata(
    db: AsyncSession,
    metadata: dict | None,
) -> User | None:
    if not metadata:
        return None

    raw_user_id = metadata.get("user_id")

    if not raw_user_id:
        return None

    try:
        user_id = UUID(str(raw_user_id))
    except (TypeError, ValueError):
        return None

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def handle_checkout_completed(
    db: AsyncSession,
    checkout_session: dict,
) -> None:
    user = await find_user_from_metadata(
        db,
        checkout_session.get("metadata"),
    )

    if user is None:
        client_reference_id = checkout_session.get(
            "client_reference_id"
        )

        if client_reference_id:
            try:
                user_id = UUID(str(client_reference_id))
            except (TypeError, ValueError):
                user_id = None

            if user_id is not None:
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

    if user is None:
        return

    customer_id = checkout_session.get("customer")

    if isinstance(customer_id, str):
        user.stripe_customer_id = customer_id


async def handle_subscription_event(
    db: AsyncSession,
    stripe_subscription: dict,
) -> None:
    customer_id = stripe_subscription.get("customer")

    user = await find_user_by_customer_id(
        db,
        customer_id if isinstance(customer_id, str) else None,
    )

    if user is None:
        user = await find_user_from_metadata(
            db,
            stripe_subscription.get("metadata"),
        )

    if user is None:
        return

    if isinstance(customer_id, str):
        user.stripe_customer_id = customer_id

    subscription_id = stripe_subscription["id"]

    result = await db.execute(
        select(Subscription).where(
            Subscription.stripe_subscription_id
            == subscription_id
        )
    )
    subscription = result.scalar_one_or_none()

    item_data = (
        stripe_subscription.get("items", {}).get("data", [])
    )

    price_id = ""

    if item_data:
        price_id = (
            item_data[0].get("price", {}).get("id", "")
        )

    values = {
        "user_id": user.id,
        "stripe_price_id": price_id,
        "status": stripe_subscription.get(
            "status",
            "unknown",
        ),
        "current_period_end": timestamp_to_datetime(
            stripe_subscription.get("current_period_end")
        ),
        "cancel_at_period_end": bool(
            stripe_subscription.get(
                "cancel_at_period_end",
                False,
            )
        ),
    }

    if subscription is None:
        subscription = Subscription(
            stripe_subscription_id=subscription_id,
            **values,
        )
        db.add(subscription)
        return

    for field_name, field_value in values.items():
        setattr(subscription, field_name, field_value)


async def handle_invoice_event(
    db: AsyncSession,
    stripe_invoice: dict,
) -> None:
    customer_id = stripe_invoice.get("customer")

    user = await find_user_by_customer_id(
        db,
        customer_id if isinstance(customer_id, str) else None,
    )

    if user is None:
        return

    invoice_id = stripe_invoice["id"]

    result = await db.execute(
        select(Invoice).where(
            Invoice.stripe_invoice_id == invoice_id
        )
    )
    invoice = result.scalar_one_or_none()

    subscription_id = stripe_invoice.get("subscription")

    if not isinstance(subscription_id, str):
        subscription_id = None

    values = {
        "user_id": user.id,
        "stripe_subscription_id": subscription_id,
        "status": stripe_invoice.get("status") or "unknown",
        "amount_due": int(
            stripe_invoice.get("amount_due") or 0
        ),
        "amount_paid": int(
            stripe_invoice.get("amount_paid") or 0
        ),
        "currency": stripe_invoice.get("currency") or "usd",
        "hosted_invoice_url": stripe_invoice.get(
            "hosted_invoice_url"
        ),
        "invoice_pdf": stripe_invoice.get("invoice_pdf"),
    }

    if invoice is None:
        invoice = Invoice(
            stripe_invoice_id=invoice_id,
            **values,
        )
        db.add(invoice)
        return

    for field_name, field_value in values.items():
        setattr(invoice, field_name, field_value)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    try:
        stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.stripe_webhook_secret,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload.",
        ) from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        ) from exc

    event_data = json.loads(payload.decode("utf-8"))

    event_id = event_data["id"]
    event_type = event_data["type"]
    stripe_object = event_data["data"]["object"]

    result = await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.stripe_event_id == event_id
        )
    )

    if result.scalar_one_or_none() is not None:
        return {"received": True}

    if event_type == "checkout.session.completed":
        await handle_checkout_completed(
            db,
            stripe_object,
        )

    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await handle_subscription_event(
            db,
            stripe_object,
        )

    elif event_type in {
        "invoice.created",
        "invoice.finalized",
        "invoice.paid",
        "invoice.payment_succeeded",
        "invoice.payment_failed",
    }:
        await handle_invoice_event(
            db,
            stripe_object,
        )

    db.add(
        WebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
        )
    )

    await db.commit()

    return {"received": True}
