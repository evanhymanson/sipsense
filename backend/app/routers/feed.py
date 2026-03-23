"""Activity feed: paginated global timeline of check-ins."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from .. import models, schemas
from ..database import get_db
from ..auth import get_optional_user

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/", response_model=schemas.FeedResponse)
def get_feed(
    category: Optional[str] = Query(None, description="Filter by whiskey category"),
    following_only: bool = Query(False, description="Only show check-ins from followed users"),
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.UserRating)
        .options(joinedload(models.UserRating.whiskey))
        .order_by(models.UserRating.created_at.desc())
    )

    if following_only and current_user:
        from sqlalchemy import select
        following_ids = select(models.Follow.following_id).where(
            models.Follow.follower_id == current_user.username
        )
        query = query.filter(models.UserRating.user_id.in_(following_ids))

    if category:
        cat_safe = category.replace("%", "\\%").replace("_", "\\_")
        query = query.join(models.Whiskey).filter(
            models.Whiskey.category.ilike(f"%{cat_safe}%")
        )

    ratings = query.offset(skip).limit(limit + 1).all()
    has_more = len(ratings) > limit
    ratings = ratings[:limit]

    # Batch-load toast counts
    rating_ids = [r.id for r in ratings]
    toast_counts: dict[int, int] = {}
    user_toasts: set[int] = set()

    if rating_ids:
        from sqlalchemy import func as sqlfunc
        counts = (
            db.query(models.Toast.rating_id, sqlfunc.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(rating_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

        if current_user:
            user_toast_rows = (
                db.query(models.Toast.rating_id)
                .filter(
                    models.Toast.rating_id.in_(rating_ids),
                    models.Toast.user_id == current_user.username,
                )
                .all()
            )
            user_toasts = {row[0] for row in user_toast_rows}

    items = []
    for r in ratings:
        if r.whiskey is None:
            continue
        items.append(schemas.FeedItem(
            rating=schemas.RatingRead(
                id=r.id,
                user_id=r.user_id,
                whiskey_id=r.whiskey_id,
                score=r.score,
                notes=r.notes,
                serving_style=r.serving_style,
                location_note=r.location_note,
                image_url=r.image_url,
                created_at=r.created_at,
                toast_count=toast_counts.get(r.id, 0),
            ),
            whiskey=schemas.WhiskeyRead.model_validate(r.whiskey),
            username=r.user_id,
            toast_count=toast_counts.get(r.id, 0),
            user_toasted=r.id in user_toasts,
        ))

    return schemas.FeedResponse(items=items, has_more=has_more)
