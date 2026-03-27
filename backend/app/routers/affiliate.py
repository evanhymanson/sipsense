"""
Affiliate click tracking — logs buy-link clicks for commission reporting.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, get_optional_user

router = APIRouter(prefix="/affiliate", tags=["affiliate"])


@router.post("/click")
def record_click(
    body: schemas.AffiliateClickCreate,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Record a click on a buy link before redirecting to the retailer."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == body.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    click = models.AffiliateClick(
        user_id=current_user.username if current_user else None,
        whiskey_id=body.whiskey_id,
        retailer=body.retailer,
        source=body.source,
    )
    db.add(click)
    db.commit()
    return {"status": "recorded"}


@router.get("/stats")
def get_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Affiliate click stats scoped to the current user's own clicks."""
    base = db.query(models.AffiliateClick).filter(
        models.AffiliateClick.user_id == current_user.username
    )

    total = base.count()

    by_retailer_rows = (
        base.with_entities(models.AffiliateClick.retailer, sqlfunc.count(models.AffiliateClick.id))
        .group_by(models.AffiliateClick.retailer)
        .all()
    )
    clicks_by_retailer = {r: c for r, c in by_retailer_rows}

    by_source_rows = (
        base.with_entities(models.AffiliateClick.source, sqlfunc.count(models.AffiliateClick.id))
        .group_by(models.AffiliateClick.source)
        .all()
    )
    clicks_by_source = {s: c for s, c in by_source_rows}

    conversion_count = (
        base.filter(models.AffiliateClick.converted == True).count()
    )
    total_commission = (
        base.with_entities(sqlfunc.sum(models.AffiliateClick.commission_amount))
        .filter(models.AffiliateClick.converted == True)
        .scalar() or 0.0
    )

    return schemas.AffiliateStats(
        total_clicks=total,
        clicks_by_retailer=clicks_by_retailer,
        clicks_by_source=clicks_by_source,
        conversion_count=conversion_count,
        total_commission=total_commission,
    )


@router.get("/pending-followups")
def get_pending_followups(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return whiskeys the user clicked buy links for but hasn't rated yet.
    Used for 'Did you buy it? Rate it!' prompts."""
    from datetime import datetime, timezone, timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    clicks = (
        db.query(models.AffiliateClick.whiskey_id)
        .filter(
            models.AffiliateClick.user_id == current_user.username,
            models.AffiliateClick.clicked_at >= cutoff,
        )
        .distinct()
        .all()
    )
    clicked_ids = [c[0] for c in clicks]
    if not clicked_ids:
        return {"followups": []}

    rated_ids = {
        r[0] for r in
        db.query(models.UserRating.whiskey_id)
        .filter(
            models.UserRating.user_id == current_user.username,
            models.UserRating.whiskey_id.in_(clicked_ids),
        )
        .all()
    }

    unrated_ids = [wid for wid in clicked_ids if wid not in rated_ids]
    if not unrated_ids:
        return {"followups": []}

    whiskeys = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.id.in_(unrated_ids))
        .limit(5)
        .all()
    )
    return {
        "followups": [
            {
                "id": w.id,
                "name": w.name,
                "distillery": w.distillery,
                "image_url": w.image_url,
                "category": w.category,
            }
            for w in whiskeys
        ]
    }
