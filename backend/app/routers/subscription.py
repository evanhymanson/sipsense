"""
Premium subscription management.
Phase 2 MVP: manual activation. Stripe integration planned for Phase 3.
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

_ADMIN_USERS = {u.strip() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()}

router = APIRouter(prefix="/subscription", tags=["subscription"])

FEATURES = [
    schemas.FeatureComparison(feature="AI Chat & Tasting Notes", free_tier="5 per day", premium_tier="Unlimited"),
    schemas.FeatureComparison(feature="Video Feed", free_tier="With ads", premium_tier="Ad-free"),
    schemas.FeatureComparison(feature="Activity Feed", free_tier="With ads", premium_tier="Ad-free"),
    schemas.FeatureComparison(feature="Deal Alerts", free_tier="Standard", premium_tier="Priority + Exclusive"),
    schemas.FeatureComparison(feature="Palate Analytics", free_tier="Basic", premium_tier="Advanced"),
    schemas.FeatureComparison(feature="Support", free_tier="Community", premium_tier="Priority"),
]


@router.get("/status", response_model=schemas.SubscriptionStatus)
def get_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check current user's subscription status."""
    # Check if premium has expired
    if current_user.is_premium and current_user.premium_until:
        expiry = current_user.premium_until
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            current_user.is_premium = False
            db.commit()

    sub = (
        db.query(models.UserSubscription)
        .filter(models.UserSubscription.user_id == current_user.username)
        .first()
    )

    return schemas.SubscriptionStatus(
        is_premium=current_user.is_premium,
        tier=sub.tier if sub else None,
        expires_at=current_user.premium_until,
        has_stripe=bool(sub and sub.payment_provider == "stripe"),
    )


@router.post("/activate")
def activate_premium(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activate premium subscription (admin only for Phase 2).
    In Phase 3 this will be triggered by Stripe webhook."""
    if current_user.username not in _ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    if current_user.is_premium:
        raise HTTPException(status_code=400, detail="Already premium")

    from datetime import timedelta
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    current_user.is_premium = True
    current_user.premium_until = expires

    # Create or update subscription record
    sub = (
        db.query(models.UserSubscription)
        .filter(models.UserSubscription.user_id == current_user.username)
        .first()
    )
    if sub:
        sub.status = "active"
        sub.started_at = datetime.now(timezone.utc)
        sub.expires_at = expires
    else:
        sub = models.UserSubscription(
            user_id=current_user.username,
            tier="premium",
            status="active",
            expires_at=expires,
        )
        db.add(sub)

    db.commit()
    return {"status": "activated", "expires_at": expires.isoformat()}


@router.post("/cancel")
def cancel_subscription(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel premium subscription."""
    if not current_user.is_premium:
        raise HTTPException(status_code=400, detail="No active subscription")

    current_user.is_premium = False
    current_user.premium_until = None

    sub = (
        db.query(models.UserSubscription)
        .filter(models.UserSubscription.user_id == current_user.username)
        .first()
    )
    if sub:
        sub.status = "canceled"

    db.commit()
    return {"status": "canceled"}


@router.get("/features", response_model=list[schemas.FeatureComparison])
def get_features():
    """Return feature comparison between free and premium tiers."""
    return FEATURES
