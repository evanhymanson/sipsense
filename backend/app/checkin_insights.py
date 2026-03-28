"""Post-check-in contextual insights engine.

After a user rates a whiskey, generates 1-3 short insight strings like:
- "This is your 4th peated scotch"
- "You rate Japanese whisky 0.8 stars above your average"
- "First Canadian whisky — welcome to a new world!"
"""

import logging

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def generate_checkin_insights(
    user_id: str, whiskey_id: int, score: float, db: Session
) -> list[str]:
    """Return 1-3 contextual insight strings after a check-in."""
    insights: list[str] = []

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        return insights

    category = (whiskey.category or "").strip()
    if not category:
        return insights

    # Count how many unique whiskeys the user has rated in this category
    category_count = (
        db.query(sqlfunc.count(sqlfunc.distinct(models.UserRating.whiskey_id)))
        .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(
            models.UserRating.user_id == user_id,
            sqlfunc.lower(models.Whiskey.category) == category.lower(),
        )
        .scalar() or 0
    )

    # First in category
    if category_count == 1:
        insights.append(f"First {category} — welcome to a new world!")
    elif category_count > 1:
        ordinal = _ordinal(category_count)
        insights.append(f"This is your {ordinal} {category}")

    # Compare score vs user's average for this category
    category_avg = (
        db.query(sqlfunc.avg(models.UserRating.score))
        .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(
            models.UserRating.user_id == user_id,
            sqlfunc.lower(models.Whiskey.category) == category.lower(),
        )
        .scalar()
    )
    if category_avg is not None and category_count > 2:
        diff = round(score - float(category_avg), 1)
        if abs(diff) >= 0.5:
            direction = "above" if diff > 0 else "below"
            insights.append(
                f"You rate {category} {abs(diff):.1f} stars {direction} your average"
            )

    # Check if this is the user's highest-rated in this category
    if category_count > 1:
        max_in_category = (
            db.query(sqlfunc.max(models.UserRating.score))
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(
                models.UserRating.user_id == user_id,
                sqlfunc.lower(models.Whiskey.category) == category.lower(),
            )
            .scalar()
        )
        if max_in_category is not None and score >= float(max_in_category):
            insights.append(f"New personal favorite {category}!")

    return insights[:3]


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string: 1->1st, 2->2nd, etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
