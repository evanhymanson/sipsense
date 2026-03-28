"""Track user progress on community challenges after each check-in."""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def update_challenge_progress(
    user_id: str, whiskey_id: int, db: Session
) -> list[dict]:
    """After a check-in, update progress on any matching active challenges.

    Returns list of dicts: [{challenge_title, progress, goal, completed}]
    """
    now = datetime.now(timezone.utc)

    # Get all active challenges the user has joined and hasn't completed
    progresses = (
        db.query(models.UserChallengeProgress)
        .join(models.Challenge)
        .filter(
            models.UserChallengeProgress.user_id == user_id,
            models.UserChallengeProgress.completed == False,
            models.Challenge.is_active == True,
            models.Challenge.starts_at <= now,
            models.Challenge.ends_at >= now,
        )
        .all()
    )

    if not progresses:
        return []

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        return []

    updates = []
    for prog in progresses:
        challenge = prog.challenge
        if _whiskey_matches_filter(whiskey, challenge.filters_json):
            prog.progress_count += 1
            if prog.progress_count >= challenge.goal_count:
                prog.completed = True
                prog.completed_at = now
            updates.append({
                "challenge_title": challenge.title,
                "progress": prog.progress_count,
                "goal": challenge.goal_count,
                "completed": prog.completed,
            })

    if updates:
        db.flush()

    return updates


def _whiskey_matches_filter(whiskey: models.Whiskey, filters_json: str | None) -> bool:
    """Check if a whiskey matches the challenge filter criteria."""
    if not filters_json:
        return True  # No filter = any whiskey counts

    try:
        filters = json.loads(filters_json)
    except (json.JSONDecodeError, TypeError):
        return False

    # Category filter
    if "category" in filters:
        if (whiskey.category or "").lower() != filters["category"].lower():
            return False

    # Region contains filter (e.g. "islay" in region)
    if "region_contains" in filters:
        if not whiskey.region or filters["region_contains"].lower() not in whiskey.region.lower():
            return False

    return True
