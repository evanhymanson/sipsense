"""
Stripe Checkout + webhook handler for premium subscriptions.

Required env vars:
  STRIPE_SECRET_KEY      — sk_test_... or sk_live_...
  STRIPE_WEBHOOK_SECRET  — whsec_...
  STRIPE_PRICE_MONTHLY   — price_... (Stripe Price ID for monthly plan)
  STRIPE_PRICE_YEARLY    — price_... (Stripe Price ID for yearly plan)
  FRONTEND_URL           — https://sipsense.ai (for redirect URLs)
"""
import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

_STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
_PRICE_IDS = {
    "monthly": os.getenv("STRIPE_PRICE_MONTHLY", ""),
    "yearly": os.getenv("STRIPE_PRICE_YEARLY", ""),
}
_FRONTEND_URL = os.getenv("FRONTEND_URL", "https://sipsense.ai")


def _get_stripe():
    """Lazy import stripe so the app starts even without the package installed."""
    try:
        import stripe
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if not _STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = _STRIPE_SECRET_KEY
    return stripe


# ── Checkout Session ─────────────────────────────────────────────────────


@router.post("/create-checkout-session", response_model=schemas.StripeCheckoutResponse)
def create_checkout_session(
    body: schemas.StripeCheckoutCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout session for the user to subscribe."""
    if current_user.is_premium:
        raise HTTPException(status_code=400, detail="Already subscribed")

    stripe = _get_stripe()

    price_id = _PRICE_IDS.get(body.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    # Reuse or create a Stripe Customer for this user
    sub = (
        db.query(models.UserSubscription)
        .filter(models.UserSubscription.user_id == current_user.username)
        .first()
    )
    customer_id = sub.external_id if sub and sub.payment_provider == "stripe" else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            metadata={"sipsense_username": current_user.username},
        )
        customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{_FRONTEND_URL}/premium?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{_FRONTEND_URL}/premium",
        subscription_data={
            "metadata": {"sipsense_username": current_user.username},
            "trial_period_days": 7,
        },
        metadata={"sipsense_username": current_user.username},
    )

    return schemas.StripeCheckoutResponse(checkout_url=session.url)


@router.post("/create-portal-session")
def create_portal_session(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    stripe = _get_stripe()

    sub = (
        db.query(models.UserSubscription)
        .filter(
            models.UserSubscription.user_id == current_user.username,
            models.UserSubscription.payment_provider == "stripe",
        )
        .first()
    )
    if not sub or not sub.external_id:
        raise HTTPException(status_code=400, detail="No Stripe subscription found")

    session = stripe.billing_portal.Session.create(
        customer=sub.external_id,
        return_url=f"{_FRONTEND_URL}/premium",
    )
    return {"url": session.url}


# ── Webhook ──────────────────────────────────────────────────────────────


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events for subscription lifecycle."""
    stripe = _get_stripe()

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, _STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Idempotency: skip already-processed events
    existing = db.query(models.StripeEvent).filter(models.StripeEvent.event_id == event["id"]).first()
    if existing:
        return JSONResponse({"status": "already_processed"})

    db.add(models.StripeEvent(event_id=event["id"], event_type=event["type"]))

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_complete(data, db)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, db)
    else:
        logger.info("Unhandled Stripe event: %s", event_type)

    db.commit()
    return JSONResponse({"status": "ok"})


def _handle_checkout_complete(session: dict, db: Session):
    """Activate premium after successful checkout."""
    username = session.get("metadata", {}).get("sipsense_username")
    if not username:
        logger.warning("Checkout session missing sipsense_username metadata")
        return

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        logger.warning("User %s not found for checkout", username)
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    # Activate premium on user
    user.is_premium = True
    # Expiry will be set by subscription.updated event; set 37 days as safe default (30 + 7 trial)
    from datetime import timedelta
    user.premium_until = datetime.now(timezone.utc) + timedelta(days=37)

    # Create/update subscription record
    sub = db.query(models.UserSubscription).filter(models.UserSubscription.user_id == username).first()
    if sub:
        sub.status = "active"
        sub.payment_provider = "stripe"
        sub.external_id = customer_id
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = user.premium_until
    else:
        sub = models.UserSubscription(
            user_id=username,
            tier="premium",
            status="active",
            payment_provider="stripe",
            external_id=customer_id,
            expires_at=user.premium_until,
        )
        db.add(sub)


def _handle_subscription_updated(subscription: dict, db: Session):
    """Update subscription status and expiry from Stripe."""
    username = subscription.get("metadata", {}).get("sipsense_username")
    if not username:
        return

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return

    status = subscription.get("status")  # active, past_due, canceled, etc.
    current_period_end = subscription.get("current_period_end")

    if status == "active":
        user.is_premium = True
        if current_period_end:
            user.premium_until = datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    elif status in ("past_due", "unpaid"):
        # Keep premium active during grace period
        pass
    elif status in ("canceled", "incomplete_expired"):
        user.is_premium = False
        user.premium_until = None

    sub = db.query(models.UserSubscription).filter(models.UserSubscription.user_id == username).first()
    if sub:
        sub.status = status
        if current_period_end:
            sub.expires_at = datetime.fromtimestamp(current_period_end, tz=timezone.utc)


def _handle_subscription_deleted(subscription: dict, db: Session):
    """Deactivate premium when subscription is fully canceled."""
    username = subscription.get("metadata", {}).get("sipsense_username")
    if not username:
        return

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return

    user.is_premium = False
    user.premium_until = None

    sub = db.query(models.UserSubscription).filter(models.UserSubscription.user_id == username).first()
    if sub:
        sub.status = "canceled"
