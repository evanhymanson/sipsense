"""Seed initial community challenges.

Challenges rotate monthly — dates are computed relative to the current month.
Called at startup alongside seed_badges().
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)

CHALLENGE_DEFINITIONS = [
    {
        "slug": "bourbon-trail",
        "title": "Bourbon Trail",
        "description": "Rate 4 different bourbons this month",
        "challenge_type": "rate_category",
        "goal_count": 4,
        "filters_json": '{"category": "bourbon"}',
        "image_emoji": "\U0001f3c7",  # horse racing
    },
    {
        "slug": "global-explorer",
        "title": "Global Explorer",
        "description": "Rate whiskeys from 3 different countries",
        "challenge_type": "explore_region",
        "goal_count": 3,
        "filters_json": '{"type": "any"}',  # any whiskey counts
        "image_emoji": "\U0001f30d",  # globe
    },
    {
        "slug": "peat-week",
        "title": "Peat Week",
        "description": "Rate 3 peated scotches from Islay",
        "challenge_type": "rate_category",
        "goal_count": 3,
        "filters_json": '{"category": "scotch", "region_contains": "islay"}',
        "image_emoji": "\U0001f525",  # fire
    },
]


def seed_challenges(db: Session) -> None:
    """Insert challenge definitions if they don't already exist.

    Sets start/end dates for the current month.
    """
    existing = {c.slug for c in db.query(models.Challenge).all()}

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # End of month: go to next month day 1, then subtract 1 second
    if now.month == 12:
        month_end = month_start.replace(year=now.year + 1, month=1)
    else:
        month_end = month_start.replace(month=now.month + 1)

    added = 0
    for defn in CHALLENGE_DEFINITIONS:
        if defn["slug"] not in existing:
            db.add(models.Challenge(
                slug=defn["slug"],
                title=defn["title"],
                description=defn["description"],
                challenge_type=defn["challenge_type"],
                goal_count=defn["goal_count"],
                filters_json=defn["filters_json"],
                image_emoji=defn["image_emoji"],
                starts_at=month_start,
                ends_at=month_end,
                is_active=True,
            ))
            added += 1

    if added:
        db.commit()
        logger.info("Seeded %d challenge(s)", added)
