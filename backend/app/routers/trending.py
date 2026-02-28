"""
Trending & Popular whiskeys — surface what the community is engaging with.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta, timezone
from typing import Optional

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("/", response_model=list[schemas.WhiskeyRead])
def get_trending(
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    category: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Return whiskeys with the most user activity (ratings + favorites) in the
    given time window.  Falls back to all-time top-rated if there's not enough
    recent activity.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Count recent ratings per whiskey
    rating_counts = (
        db.query(
            models.UserRating.whiskey_id,
            func.count(models.UserRating.id).label("cnt"),
        )
        .filter(models.UserRating.created_at >= cutoff)
        .group_by(models.UserRating.whiskey_id)
        .subquery()
    )

    # Count recent favorites per whiskey
    fav_counts = (
        db.query(
            models.UserFavorite.whiskey_id,
            func.count(models.UserFavorite.id).label("cnt"),
        )
        .filter(models.UserFavorite.created_at >= cutoff)
        .group_by(models.UserFavorite.whiskey_id)
        .subquery()
    )

    # Combine: activity = ratings + 2*favorites (favorites weighted more)
    q = (
        db.query(
            models.Whiskey,
            (func.coalesce(rating_counts.c.cnt, 0) + 2 * func.coalesce(fav_counts.c.cnt, 0)).label("activity"),
        )
        .outerjoin(rating_counts, models.Whiskey.id == rating_counts.c.whiskey_id)
        .outerjoin(fav_counts, models.Whiskey.id == fav_counts.c.whiskey_id)
    )

    if category:
        q = q.filter(models.Whiskey.category.ilike(f"%{category}%"))

    results = q.order_by(desc("activity"), desc(models.Whiskey.rating_avg)).limit(limit).all()

    # If not enough recent activity, fall back to top-rated
    whiskeys = [w for w, _ in results if _ > 0]
    if len(whiskeys) < limit:
        fallback_q = db.query(models.Whiskey)
        if category:
            fallback_q = fallback_q.filter(models.Whiskey.category.ilike(f"%{category}%"))
        existing_ids = {w.id for w in whiskeys}
        fallback = (
            fallback_q
            .filter(models.Whiskey.id.notin_(existing_ids) if existing_ids else True)
            .order_by(desc(models.Whiskey.rating_avg))
            .limit(limit - len(whiskeys))
            .all()
        )
        whiskeys.extend(fallback)

    return whiskeys


@router.get("/new-arrivals", response_model=list[schemas.WhiskeyRead])
def get_new_arrivals(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return recently added whiskeys (by database ID, highest = newest)."""
    return (
        db.query(models.Whiskey)
        .order_by(desc(models.Whiskey.id))
        .limit(limit)
        .all()
    )
