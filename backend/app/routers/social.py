"""Social endpoints: toasts (likes) and public user profiles."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(tags=["social"])


# ── Toasts ────────────────────────────────────────────────────────────────

@router.post("/ratings/{rating_id}/toast", response_model=schemas.ToastRead, status_code=201)
def add_toast(
    rating_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Check-in not found")

    if rating.user_id == current_user.username:
        raise HTTPException(status_code=400, detail="Can't toast your own check-in")

    existing = (
        db.query(models.Toast)
        .filter(models.Toast.user_id == current_user.username, models.Toast.rating_id == rating_id)
        .first()
    )
    if existing:
        return existing  # idempotent

    toast = models.Toast(user_id=current_user.username, rating_id=rating_id)
    db.add(toast)
    db.commit()
    db.refresh(toast)
    return toast


@router.delete("/ratings/{rating_id}/toast", status_code=204)
def remove_toast(
    rating_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    toast = (
        db.query(models.Toast)
        .filter(models.Toast.user_id == current_user.username, models.Toast.rating_id == rating_id)
        .first()
    )
    if toast:
        db.delete(toast)
        db.commit()


# ── Public Profile ────────────────────────────────────────────────────────

@router.get("/users/{username}/profile", response_model=schemas.PublicProfile)
def get_user_profile(
    username: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == username)
        .options(joinedload(models.UserRating.whiskey))
        .order_by(models.UserRating.created_at.desc())
        .all()
    )

    total_checkins = len(ratings)
    unique_whiskeys = len({r.whiskey_id for r in ratings})
    avg_score = sum(r.score for r in ratings) / total_checkins if total_checkins else None

    # Top categories
    cat_counts: dict[str, int] = {}
    for r in ratings:
        if r.whiskey:
            cat = (r.whiskey.category or "unknown").lower()
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    top_categories = sorted(
        [{"category": cat, "count": cnt} for cat, cnt in cat_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    # Badges
    user_badges = (
        db.query(models.UserBadge)
        .filter(models.UserBadge.user_id == username)
        .options(joinedload(models.UserBadge.badge))
        .order_by(models.UserBadge.awarded_at.desc())
        .all()
    )

    # Recent check-ins (up to 10) with toast counts
    recent = ratings[:10]
    recent_ids = [r.id for r in recent]
    toast_counts: dict[int, int] = {}
    if recent_ids:
        counts = (
            db.query(models.Toast.rating_id, sqlfunc.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(recent_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

    recent_items = [
        schemas.FeedItem(
            rating=schemas.RatingRead(
                id=r.id,
                user_id=r.user_id,
                whiskey_id=r.whiskey_id,
                score=r.score,
                notes=r.notes,
                serving_style=r.serving_style,
                location_note=r.location_note,
                created_at=r.created_at,
                toast_count=toast_counts.get(r.id, 0),
            ),
            whiskey=schemas.WhiskeyRead.model_validate(r.whiskey),
            username=r.user_id,
            toast_count=toast_counts.get(r.id, 0),
            user_toasted=False,
        )
        for r in recent if r.whiskey
    ]

    return schemas.PublicProfile(
        username=username,
        member_since=user.created_at,
        total_checkins=total_checkins,
        unique_whiskeys=unique_whiskeys,
        avg_score=round(avg_score, 2) if avg_score else None,
        top_categories=top_categories,
        badges=[
            schemas.UserBadgeRead(
                badge=schemas.BadgeRead.model_validate(ub.badge),
                awarded_at=ub.awarded_at,
            )
            for ub in user_badges
        ],
        recent_checkins=recent_items,
    )
