"""User level/status system — computed on-the-fly from activity."""

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from . import models

LEVELS = [
    {"rank": 1, "name": "Novice",       "emoji": "\U0001f331", "min_points": 0},
    {"rank": 2, "name": "Enthusiast",    "emoji": "\U0001f943", "min_points": 50},
    {"rank": 3, "name": "Connoisseur",   "emoji": "\U0001f3c5", "min_points": 200},
    {"rank": 4, "name": "Expert",        "emoji": "\u2B50",     "min_points": 500},
    {"rank": 5, "name": "Master",        "emoji": "\U0001f451", "min_points": 1000},
]

PTS_CHECKIN = 5
PTS_UNIQUE = 3
PTS_BADGE = 15
PTS_HELPFUL = 2


def compute_user_level(username: str, db: Session) -> dict:
    """Compute a user's level from their activity."""
    total_checkins = (
        db.query(sqlfunc.count(models.UserRating.id))
        .filter(models.UserRating.user_id == username)
        .scalar() or 0
    )
    unique_whiskeys = (
        db.query(sqlfunc.count(sqlfunc.distinct(models.UserRating.whiskey_id)))
        .filter(models.UserRating.user_id == username)
        .scalar() or 0
    )
    badge_count = (
        db.query(sqlfunc.count(models.UserBadge.id))
        .filter(models.UserBadge.user_id == username)
        .scalar() or 0
    )
    helpful_received = (
        db.query(sqlfunc.count(models.ReviewHelpful.id))
        .join(models.UserRating, models.ReviewHelpful.rating_id == models.UserRating.id)
        .filter(models.UserRating.user_id == username)
        .scalar() or 0
    )

    points = (
        total_checkins * PTS_CHECKIN
        + unique_whiskeys * PTS_UNIQUE
        + badge_count * PTS_BADGE
        + helpful_received * PTS_HELPFUL
    )

    current = LEVELS[0]
    for lvl in LEVELS:
        if points >= lvl["min_points"]:
            current = lvl

    idx = LEVELS.index(current)
    next_lvl = LEVELS[idx + 1] if idx + 1 < len(LEVELS) else None

    progress = 0.0
    if next_lvl:
        span = next_lvl["min_points"] - current["min_points"]
        progress = min(100.0, ((points - current["min_points"]) / span) * 100) if span > 0 else 100.0

    return {
        "rank": current["rank"],
        "name": current["name"],
        "emoji": current["emoji"],
        "points": points,
        "next_level_name": next_lvl["name"] if next_lvl else None,
        "next_level_points": next_lvl["min_points"] if next_lvl else None,
        "progress_pct": round(progress, 1),
    }
