"""Gap 14: Subscription box scaffolding — curated whiskey delivery preferences."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/subscription-box", tags=["subscription-box"])

BOX_TIERS = {
    "explorer": {
        "name": "Explorer",
        "bottles": 2,
        "price_range": "$30-60/bottle",
        "description": "Two curated bottles to expand your horizons.",
    },
    "connoisseur": {
        "name": "Connoisseur",
        "bottles": 3,
        "price_range": "$50-100/bottle",
        "description": "Three premium selections matched to your palate.",
    },
    "collector": {
        "name": "Collector",
        "bottles": 3,
        "price_range": "$80-200/bottle",
        "description": "Three exceptional bottles including limited releases.",
    },
}


@router.get("/tiers")
def get_tiers():
    """Return available subscription box tiers."""
    return BOX_TIERS


@router.get("/preferences")
def get_preferences(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's subscription box preferences."""
    box = (
        db.query(models.SubscriptionBox)
        .filter(models.SubscriptionBox.user_id == current_user.username)
        .first()
    )
    if not box:
        return {
            "enrolled": False,
            "tier": None,
            "frequency": None,
            "preferences": {},
            "status": None,
        }

    prefs = {}
    try:
        prefs = json.loads(box.preference_json) if box.preference_json else {}
    except json.JSONDecodeError:
        pass

    return {
        "enrolled": True,
        "tier": box.tier,
        "frequency": box.frequency,
        "preferences": prefs,
        "status": box.status,
        "next_shipment_date": box.next_shipment_date,
    }


@router.put("/preferences")
def update_preferences(
    body: schemas.BoxPreferenceUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update subscription box preferences."""
    box = (
        db.query(models.SubscriptionBox)
        .filter(models.SubscriptionBox.user_id == current_user.username)
        .first()
    )

    prefs = {
        "categories": body.categories,
        "price_min": body.price_min,
        "price_max": body.price_max,
        "avoid_flavors": body.avoid_flavors,
    }

    if not box:
        box = models.SubscriptionBox(
            user_id=current_user.username,
            tier=body.tier or "explorer",
            frequency=body.frequency or "monthly",
            preference_json=json.dumps(prefs),
            status="waitlist",  # Coming soon
        )
        db.add(box)
    else:
        if body.tier:
            box.tier = body.tier
        if body.frequency:
            box.frequency = body.frequency
        box.preference_json = json.dumps(prefs)

    db.commit()
    return {
        "message": "Preferences saved! You're on the waitlist — launching soon.",
        "tier": box.tier,
        "frequency": box.frequency,
        "status": box.status,
    }


@router.get("/preview")
def preview_next_box(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview what your next box might contain based on your preferences."""
    box = (
        db.query(models.SubscriptionBox)
        .filter(models.SubscriptionBox.user_id == current_user.username)
        .first()
    )

    prefs = {}
    if box and box.preference_json:
        try:
            prefs = json.loads(box.preference_json)
        except json.JSONDecodeError:
            pass

    tier_info = BOX_TIERS.get(box.tier if box else "explorer", BOX_TIERS["explorer"])
    bottle_count = tier_info["bottles"]

    # Build a simple query based on preferences
    q = db.query(models.Whiskey).filter(models.Whiskey.rating_avg >= 3.5)

    categories = prefs.get("categories", [])
    if categories:
        from sqlalchemy import or_
        q = q.filter(or_(*(models.Whiskey.category.ilike(f"%{c}%") for c in categories)))

    if prefs.get("price_min"):
        q = q.filter(models.Whiskey.price_usd >= prefs["price_min"])
    if prefs.get("price_max"):
        q = q.filter(models.Whiskey.price_usd <= prefs["price_max"])

    # Exclude already-rated whiskeys
    rated_ids = [
        r[0] for r in
        db.query(models.UserRating.whiskey_id)
        .filter(models.UserRating.user_id == current_user.username)
        .all()
    ]
    if rated_ids:
        q = q.filter(models.Whiskey.id.notin_(rated_ids))

    whiskeys = q.order_by(models.Whiskey.rating_avg.desc()).limit(bottle_count).all()

    return {
        "tier": box.tier if box else "explorer",
        "bottle_count": bottle_count,
        "preview_bottles": [schemas.WhiskeyRead.model_validate(w) for w in whiskeys],
        "message": "This is a preview based on your preferences. Actual selections may vary.",
        "launching_soon": True,
    }
