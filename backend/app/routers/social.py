"""Social endpoints: toasts (likes), public user profiles, and follow graph."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc
from typing import Optional

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, get_optional_user
from ..track import track_action
from ..analytics_constants import ACTION_FOLLOW, ACTION_COMMENT
from ..levels import compute_user_level

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


# ── Review Helpfulness ────────────────────────────────────────────────────

@router.post("/ratings/{rating_id}/helpful", status_code=201)
def mark_helpful(
    rating_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a review as helpful."""
    rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Check-in not found")
    if rating.user_id == current_user.username:
        raise HTTPException(status_code=400, detail="Can't mark your own review as helpful")

    existing = (
        db.query(models.ReviewHelpful)
        .filter(models.ReviewHelpful.user_id == current_user.username,
                models.ReviewHelpful.rating_id == rating_id)
        .first()
    )
    if existing:
        return {"status": "already_marked"}

    helpful = models.ReviewHelpful(user_id=current_user.username, rating_id=rating_id)
    db.add(helpful)
    db.commit()
    return {"status": "marked_helpful"}


@router.delete("/ratings/{rating_id}/helpful", status_code=204)
def unmark_helpful(
    rating_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove helpfulness vote."""
    helpful = (
        db.query(models.ReviewHelpful)
        .filter(models.ReviewHelpful.user_id == current_user.username,
                models.ReviewHelpful.rating_id == rating_id)
        .first()
    )
    if helpful:
        db.delete(helpful)
        db.commit()


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


# ── Check-in Comments ────────────────────────────────────────────────────

@router.post("/ratings/{rating_id}/comment", response_model=schemas.CheckInCommentRead, status_code=201)
def add_checkin_comment(
    rating_id: int,
    body: schemas.CheckInCommentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Check-in not found")

    comment = models.CheckInComment(
        user_id=current_user.username,
        rating_id=rating_id,
        text=body.text,
    )
    db.add(comment)

    # Notify the check-in owner (unless commenting on own)
    if rating.user_id != current_user.username:
        db.add(models.WatchlistAlert(
            username=rating.user_id,
            alert_type="comment",
            from_username=current_user.username,
            message=f"{current_user.username} commented on your check-in",
        ))

    track_action(db, current_user.username, ACTION_COMMENT,
                 detail={"rating_id": rating_id})
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/ratings/{rating_id}/comments", response_model=list[schemas.CheckInCommentRead])
def get_checkin_comments(
    rating_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.CheckInComment)
        .filter(models.CheckInComment.rating_id == rating_id)
        .order_by(models.CheckInComment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.delete("/ratings/comments/{comment_id}", status_code=204)
def delete_checkin_comment(
    comment_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(models.CheckInComment).filter(models.CheckInComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Can only delete your own comments")
    db.delete(comment)
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


@router.get("/users/suggested", response_model=list[schemas.SuggestedUserResult])
def get_suggested_users(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find users with similar taste profiles who you don't follow yet."""
    from ..ml.taste_similarity import find_similar_users

    # Get users the current user already follows
    following_ids = {
        row[0] for row in
        db.query(models.Follow.following_id)
        .filter(models.Follow.follower_id == current_user.username)
        .all()
    }

    similar = find_similar_users(current_user.username, db, following_ids, limit=limit)

    # Enrich with follower counts
    usernames = [s["username"] for s in similar]
    if not usernames:
        return []

    follower_rows = (
        db.query(models.Follow.following_id, sqlfunc.count(models.Follow.id))
        .filter(models.Follow.following_id.in_(usernames))
        .group_by(models.Follow.following_id)
        .all()
    )
    follower_counts = {uid: cnt for uid, cnt in follower_rows}

    return [
        schemas.SuggestedUserResult(
            username=s["username"],
            total_checkins=s["checkin_count"],
            follower_count=follower_counts.get(s["username"], 0),
            is_following=False,
            match_score=s["match_score"],
            reason=s["reason"],
        )
        for s in similar
    ]


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

    # Recent check-ins with toast + helpful + comment counts
    recent_ids = [r.id for r in ratings]
    toast_counts: dict[int, int] = {}
    helpful_counts: dict[int, int] = {}
    comment_counts: dict[int, int] = {}
    user_toasts: set[int] = set()
    user_helpfuls: set[int] = set()
    if recent_ids:
        counts = (
            db.query(models.Toast.rating_id, sqlfunc.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(recent_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

        h_counts = (
            db.query(models.ReviewHelpful.rating_id, sqlfunc.count(models.ReviewHelpful.id))
            .filter(models.ReviewHelpful.rating_id.in_(recent_ids))
            .group_by(models.ReviewHelpful.rating_id)
            .all()
        )
        helpful_counts = {rid: cnt for rid, cnt in h_counts}

        c_rows = (
            db.query(models.CheckInComment.rating_id, sqlfunc.count(models.CheckInComment.id))
            .filter(models.CheckInComment.rating_id.in_(recent_ids))
            .group_by(models.CheckInComment.rating_id)
            .all()
        )
        comment_counts = {rid: cnt for rid, cnt in c_rows}

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
            user_helpful_rows = (
                db.query(models.ReviewHelpful.rating_id)
                .filter(
                    models.ReviewHelpful.rating_id.in_(recent_ids),
                    models.ReviewHelpful.user_id == current_user.username,
                )
                .all()
            )
            user_helpfuls = {row[0] for row in user_helpful_rows}

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
                helpful_count=helpful_counts.get(r.id, 0),
                user_marked_helpful=r.id in user_helpfuls,
            ),
            whiskey=schemas.WhiskeyRead.model_validate(r.whiskey),
            username=r.user_id,
            toast_count=toast_counts.get(r.id, 0),
            user_toasted=r.id in user_toasts,
            helpful_count=helpful_counts.get(r.id, 0),
            user_marked_helpful=r.id in user_helpfuls,
            comment_count=comment_counts.get(r.id, 0),
        )
        for r in ratings if r.whiskey
    ]

    # User level
    user_level = compute_user_level(username, db)

    # User's public lists (up to 5 for preview)
    user_lists_raw = (
        db.query(models.UserList)
        .filter(models.UserList.user_id == username, models.UserList.is_public == True)
        .order_by(models.UserList.updated_at.desc())
        .limit(5)
        .all()
    )
    user_lists = [
        {"id": ul.id, "slug": ul.slug, "title": ul.title, "item_count": len(ul.items)}
        for ul in user_lists_raw
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
        level=user_level,
        user_lists=user_lists,
    )


# ── User Level ─────────────────────────────────────────────────────────

@router.get("/users/{username}/level")
def get_user_level(
    username: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return compute_user_level(username, db)


# ── User Ratings (paginated) ────────────────────────────────────────────

@router.get("/users/{username}/ratings", response_model=schemas.UserRatingsResponse)
def get_user_ratings(
    username: str,
    sort_by: schemas.ReviewSortOption = Query(
        schemas.ReviewSortOption.recent, description="Sort order"
    ),
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Paginated, sortable list of a user's check-ins with whiskey info."""
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    base_q = db.query(models.UserRating).filter(models.UserRating.user_id == username)
    total = base_q.count()

    # Apply sort order
    if sort_by == schemas.ReviewSortOption.highest:
        base_q = base_q.order_by(models.UserRating.score.desc(), models.UserRating.created_at.desc())
    elif sort_by == schemas.ReviewSortOption.lowest:
        base_q = base_q.order_by(models.UserRating.score.asc(), models.UserRating.created_at.desc())
    elif sort_by == schemas.ReviewSortOption.helpful:
        toast_sub = (
            db.query(
                models.Toast.rating_id,
                sqlfunc.count(models.Toast.id).label("tc"),
            )
            .group_by(models.Toast.rating_id)
            .subquery()
        )
        base_q = (
            base_q.outerjoin(toast_sub, models.UserRating.id == toast_sub.c.rating_id)
            .order_by(toast_sub.c.tc.desc().nullslast(), models.UserRating.created_at.desc())
        )
    else:  # recent
        base_q = base_q.order_by(models.UserRating.created_at.desc())

    ratings = (
        base_q
        .options(joinedload(models.UserRating.whiskey))
        .offset(skip)
        .limit(limit + 1)
        .all()
    )
    has_more = len(ratings) > limit
    ratings = ratings[:limit]

    # Batch-load toast counts, comment counts, user toast status
    rating_ids = [r.id for r in ratings]
    toast_counts: dict[int, int] = {}
    comment_counts: dict[int, int] = {}
    user_toasts: set[int] = set()

    if rating_ids:
        counts = (
            db.query(models.Toast.rating_id, sqlfunc.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(rating_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

        c_rows = (
            db.query(models.CheckInComment.rating_id, sqlfunc.count(models.CheckInComment.id))
            .filter(models.CheckInComment.rating_id.in_(rating_ids))
            .group_by(models.CheckInComment.rating_id)
            .all()
        )
        comment_counts = {rid: cnt for rid, cnt in c_rows}

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
            comment_count=comment_counts.get(r.id, 0),
        ))

    return schemas.UserRatingsResponse(items=items, total=total, has_more=has_more)
