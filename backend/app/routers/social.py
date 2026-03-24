"""Social endpoints: toasts (likes), public user profiles, and follow graph."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc
from typing import Optional

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, get_optional_user
from ..track import track_action
from ..analytics_constants import ACTION_FOLLOW

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
    if not toast:
        raise HTTPException(status_code=404, detail="Toast not found")
    db.delete(toast)
    db.commit()


# ── Follow graph ──────────────────────────────────────────────────────────

@router.post("/users/{username}/follow", status_code=201)
def follow_user(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Can't follow yourself")

    target = db.query(models.User).filter(models.User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(models.Follow)
        .filter(models.Follow.follower_id == current_user.username, models.Follow.following_id == username)
        .first()
    )
    if existing:
        return {"status": "already_following"}

    follow = models.Follow(follower_id=current_user.username, following_id=username)
    db.add(follow)

    # Notify the followed user
    db.add(models.WatchlistAlert(
        username=username,
        alert_type="follow",
        from_username=current_user.username,
        message=f"{current_user.username} started following you",
    ))

    track_action(db, current_user.username, ACTION_FOLLOW,
                 detail={"target": username})
    db.commit()
    return {"status": "following"}


@router.delete("/users/{username}/follow", status_code=204)
def unfollow_user(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follow = (
        db.query(models.Follow)
        .filter(models.Follow.follower_id == current_user.username, models.Follow.following_id == username)
        .first()
    )
    if follow:
        db.delete(follow)
        db.commit()


@router.get("/users/{username}/followers", response_model=list[schemas.UserSearchResult])
def get_followers(
    username: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Users who follow {username}."""
    follows = (
        db.query(models.Follow)
        .filter(models.Follow.following_id == username)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return _build_user_results([f.follower_id for f in follows], current_user, db)


@router.get("/users/{username}/following", response_model=list[schemas.UserSearchResult])
def get_following(
    username: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Users that {username} follows."""
    follows = (
        db.query(models.Follow)
        .filter(models.Follow.follower_id == username)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return _build_user_results([f.following_id for f in follows], current_user, db)


@router.get("/users/search", response_model=list[schemas.UserSearchResult])
def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    skip: int = Query(0, ge=0),
    limit: int = Query(15, ge=1, le=50),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    q_safe = q.replace("%", "\\%").replace("_", "\\_")
    users = (
        db.query(models.User)
        .filter(models.User.username.ilike(f"%{q_safe}%"))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return _build_user_results([u.username for u in users], current_user, db)


def _build_user_results(
    usernames: list[str],
    current_user: Optional[models.User],
    db: Session,
) -> list[schemas.UserSearchResult]:
    if not usernames:
        return []

    # Checkin counts
    checkin_rows = (
        db.query(models.UserRating.user_id, sqlfunc.count(models.UserRating.id))
        .filter(models.UserRating.user_id.in_(usernames))
        .group_by(models.UserRating.user_id)
        .all()
    )
    checkin_counts = {uid: cnt for uid, cnt in checkin_rows}

    # Follower counts
    follower_rows = (
        db.query(models.Follow.following_id, sqlfunc.count(models.Follow.id))
        .filter(models.Follow.following_id.in_(usernames))
        .group_by(models.Follow.following_id)
        .all()
    )
    follower_counts = {uid: cnt for uid, cnt in follower_rows}

    # Which ones the current user already follows
    following_set: set[str] = set()
    if current_user:
        rows = (
            db.query(models.Follow.following_id)
            .filter(models.Follow.follower_id == current_user.username,
                    models.Follow.following_id.in_(usernames))
            .all()
        )
        following_set = {r[0] for r in rows}

    return [
        schemas.UserSearchResult(
            username=u,
            total_checkins=checkin_counts.get(u, 0),
            follower_count=follower_counts.get(u, 0),
            is_following=u in following_set,
        )
        for u in usernames
    ]


# ── Public Profile ────────────────────────────────────────────────────────

@router.get("/users/{username}/profile", response_model=schemas.PublicProfile)
def get_user_profile(
    username: str,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Use SQL aggregates instead of loading all ratings into memory
    stats = (
        db.query(
            sqlfunc.count(models.UserRating.id),
            sqlfunc.count(sqlfunc.distinct(models.UserRating.whiskey_id)),
            sqlfunc.avg(models.UserRating.score),
        )
        .filter(models.UserRating.user_id == username)
        .first()
    )
    total_checkins = stats[0] or 0
    unique_whiskeys = stats[1] or 0
    avg_score = float(stats[2]) if stats[2] is not None else None

    # Top categories via SQL group-by
    cat_rows = (
        db.query(models.Whiskey.category, sqlfunc.count(models.UserRating.id))
        .join(models.UserRating, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(models.UserRating.user_id == username)
        .group_by(models.Whiskey.category)
        .order_by(sqlfunc.count(models.UserRating.id).desc())
        .limit(5)
        .all()
    )
    top_categories = [
        {"category": (cat or "unknown").lower(), "count": cnt}
        for cat, cnt in cat_rows
    ]

    # Only load recent ratings (not all)
    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == username)
        .options(joinedload(models.UserRating.whiskey))
        .order_by(models.UserRating.created_at.desc())
        .limit(10)
        .all()
    )

    # Badges
    user_badges = (
        db.query(models.UserBadge)
        .filter(models.UserBadge.user_id == username)
        .options(joinedload(models.UserBadge.badge))
        .order_by(models.UserBadge.awarded_at.desc())
        .all()
    )

    # Follower / following counts
    follower_count = (
        db.query(sqlfunc.count(models.Follow.id))
        .filter(models.Follow.following_id == username)
        .scalar() or 0
    )
    following_count = (
        db.query(sqlfunc.count(models.Follow.id))
        .filter(models.Follow.follower_id == username)
        .scalar() or 0
    )
    is_following = False
    if current_user and current_user.username != username:
        is_following = (
            db.query(models.Follow)
            .filter(models.Follow.follower_id == current_user.username,
                    models.Follow.following_id == username)
            .first()
        ) is not None

    # Recent check-ins with toast counts
    recent_ids = [r.id for r in ratings]
    toast_counts: dict[int, int] = {}
    user_toasts: set[int] = set()
    if recent_ids:
        counts = (
            db.query(models.Toast.rating_id, sqlfunc.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(recent_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

        if current_user:
            user_toast_rows = (
                db.query(models.Toast.rating_id)
                .filter(
                    models.Toast.rating_id.in_(recent_ids),
                    models.Toast.user_id == current_user.username,
                )
                .all()
            )
            user_toasts = {row[0] for row in user_toast_rows}

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
                image_url=r.image_url,
                created_at=r.created_at,
                toast_count=toast_counts.get(r.id, 0),
            ),
            whiskey=schemas.WhiskeyRead.model_validate(r.whiskey),
            username=r.user_id,
            toast_count=toast_counts.get(r.id, 0),
            user_toasted=r.id in user_toasts,
        )
        for r in ratings if r.whiskey
    ]

    return schemas.PublicProfile(
        username=username,
        member_since=user.created_at,
        total_checkins=total_checkins,
        unique_whiskeys=unique_whiskeys,
        avg_score=round(avg_score, 2) if avg_score is not None else None,
        top_categories=top_categories,
        badges=[
            schemas.UserBadgeRead(
                badge=schemas.BadgeRead.model_validate(ub.badge),
                awarded_at=ub.awarded_at,
            )
            for ub in user_badges
        ],
        recent_checkins=recent_items,
        follower_count=follower_count,
        following_count=following_count,
        is_following=is_following,
    )
