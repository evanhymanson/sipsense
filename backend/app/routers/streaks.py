"""Streak tracking endpoints.

GET  /streaks/me        — current streak info
POST /streaks/heartbeat — record daily activity
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user
from ..streaks import record_daily_activity

router = APIRouter(prefix="/streaks", tags=["streaks"])


@router.get("/me")
def get_streak(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current streak info."""
    streak = (
        db.query(models.UserStreak)
        .filter(models.UserStreak.user_id == current_user.username)
        .first()
    )
    if not streak:
        return {"current_streak": 0, "longest_streak": 0, "last_active_date": None}
    return {
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "last_active_date": streak.last_active_date,
    }


@router.post("/heartbeat")
def heartbeat(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record daily activity (viewing daily discovery, completing quiz, etc.)."""
    result = record_daily_activity(current_user.username, db)
    db.commit()
    return result
