"""Daily engagement streak tracking.

Tracks consecutive days a user is active (check-in, quiz, daily discovery).
Uses ISO date strings to avoid timezone confusion.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from . import models


def record_daily_activity(user_id: str, db: Session) -> dict:
    """Record that a user was active today.  Update streak counters.

    Returns dict with current_streak, longest_streak, is_new_day.
    """
    today_str = date.today().isoformat()

    streak = (
        db.query(models.UserStreak)
        .filter(models.UserStreak.user_id == user_id)
        .first()
    )

    if not streak:
        streak = models.UserStreak(
            user_id=user_id,
            current_streak=1,
            longest_streak=1,
            last_active_date=today_str,
        )
        db.add(streak)
        db.flush()
        return {
            "current_streak": 1,
            "longest_streak": 1,
            "is_new_day": True,
        }

    if streak.last_active_date == today_str:
        # Already counted today
        return {
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "is_new_day": False,
        }

    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    if streak.last_active_date == yesterday_str:
        # Consecutive day
        streak.current_streak += 1
    else:
        # Gap — reset
        streak.current_streak = 1

    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    streak.last_active_date = today_str
    db.flush()

    return {
        "current_streak": streak.current_streak,
        "longest_streak": streak.longest_streak,
        "is_new_day": True,
    }
