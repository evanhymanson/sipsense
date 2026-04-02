"""Gap 7: Global reviewer leaderboard — rank users by engagement score."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from .. import models, schemas
from ..database import get_db
from ..auth import get_optional_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


def _period_cutoff(period: str) -> datetime | None:
    """Return the datetime cutoff for the given period, or None for all-time."""
    now = datetime.now(timezone.utc)
    if period == "weekly":
        return now - timedelta(days=7)
    elif period == "monthly":
        return now - timedelta(days=30)
    return None


@router.get("/", response_model=schemas.LeaderboardResponse)
def get_leaderboard(
    period: str = Query("all_time", pattern="^(all_time|monthly|weekly)$"),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Compute engagement leaderboard.
    Score = (checkins * 10) + (helpful_votes_received * 5) + (comments_given * 2)
    """
    cutoff = _period_cutoff(period)

    # Checkin counts per user (bounded to top contributors only)
    _TOP_N = 500  # only aggregate top N users to avoid full table scans
    checkin_q = db.query(
        models.UserRating.user_id,
        sqlfunc.count(models.UserRating.id).label("checkin_count"),
    ).group_by(models.UserRating.user_id)
    if cutoff:
        checkin_q = checkin_q.filter(models.UserRating.created_at >= cutoff)
    checkin_q = checkin_q.order_by(sqlfunc.count(models.UserRating.id).desc()).limit(_TOP_N)
    checkin_map = {row[0]: row[1] for row in checkin_q.all()}

    # Helpful votes received (votes on the user's reviews)
    helpful_q = db.query(
        models.UserRating.user_id,
        sqlfunc.count(models.ReviewHelpful.id).label("helpful_count"),
    ).join(
        models.ReviewHelpful, models.ReviewHelpful.rating_id == models.UserRating.id
    ).group_by(models.UserRating.user_id)
    if cutoff:
        helpful_q = helpful_q.filter(models.ReviewHelpful.created_at >= cutoff)
    helpful_q = helpful_q.order_by(sqlfunc.count(models.ReviewHelpful.id).desc()).limit(_TOP_N)
    helpful_map = {row[0]: row[1] for row in helpful_q.all()}

    # Comments given per user
    comment_q = db.query(
        models.CheckInComment.user_id,
        sqlfunc.count(models.CheckInComment.id).label("comment_count"),
    ).group_by(models.CheckInComment.user_id)
    if cutoff:
        comment_q = comment_q.filter(models.CheckInComment.created_at >= cutoff)
    comment_q = comment_q.order_by(sqlfunc.count(models.CheckInComment.id).desc()).limit(_TOP_N)
    comment_map = {row[0]: row[1] for row in comment_q.all()}

    # Combine all users
    all_users = set(checkin_map) | set(helpful_map) | set(comment_map)

    scored = []
    for username in all_users:
        checkins = checkin_map.get(username, 0)
        helpful = helpful_map.get(username, 0)
        comments = comment_map.get(username, 0)
        score = (checkins * 10) + (helpful * 5) + (comments * 2)
        if score > 0:
            scored.append((username, checkins, helpful, comments, score))

    scored.sort(key=lambda x: x[4], reverse=True)

    entries = []
    user_rank = None
    for i, (username, checkins, helpful, comments, score) in enumerate(scored[:limit], 1):
        entries.append(schemas.LeaderboardEntry(
            rank=i,
            username=username,
            total_checkins=checkins,
            helpful_votes_received=helpful,
            comments_given=comments,
            engagement_score=score,
        ))

    # Find requesting user's rank
    if current_user:
        for i, (username, *_rest) in enumerate(scored, 1):
            if username == current_user.username:
                user_rank = i
                break

    return schemas.LeaderboardResponse(entries=entries, user_rank=user_rank)
