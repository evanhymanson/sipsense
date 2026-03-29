"""Push notification subscription management.

GET    /push/status    — subscription status + VAPID public key
POST   /push/subscribe — register a push subscription
DELETE /push/subscribe — unsubscribe current device
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/status", response_model=schemas.PushStatusResponse)
def get_push_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.PushSubscription)
        .filter(
            models.PushSubscription.user_id == current_user.username,
            models.PushSubscription.is_active == True,  # noqa: E712
        )
        .count()
    )
    return schemas.PushStatusResponse(
        subscribed=count > 0,
        subscription_count=count,
        vapid_public_key=os.getenv("VAPID_PUBLIC_KEY", ""),
    )


@router.post("/subscribe", response_model=schemas.PushSubscriptionRead, status_code=201)
def subscribe(
    body: schemas.PushSubscriptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register or re-activate a push subscription."""
    existing = (
        db.query(models.PushSubscription)
        .filter(
            models.PushSubscription.user_id == current_user.username,
            models.PushSubscription.endpoint == body.endpoint,
        )
        .first()
    )
    if existing:
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.is_active = True
        existing.last_used_at = datetime.now(timezone.utc)
        if body.user_agent:
            existing.user_agent = body.user_agent
        db.commit()
        db.refresh(existing)
        return existing

    sub = models.PushSubscription(
        user_id=current_user.username,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        user_agent=body.user_agent,
    )
    db.add(sub)
    try:
        db.commit()
        db.refresh(sub)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subscription already exists")
    return sub


@router.delete("/subscribe", status_code=204)
def unsubscribe(
    body: schemas.PushSubscriptionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deactivate a push subscription (soft-delete)."""
    sub = (
        db.query(models.PushSubscription)
        .filter(
            models.PushSubscription.user_id == current_user.username,
            models.PushSubscription.endpoint == body.endpoint,
        )
        .first()
    )
    if sub:
        sub.is_active = False
        db.commit()
