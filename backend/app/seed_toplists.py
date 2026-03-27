"""Seed top list definitions at startup."""

import json
import logging
from sqlalchemy.orm import Session
from . import models

logger = logging.getLogger(__name__)

TOP_LIST_DEFINITIONS = [
    {
        "slug": "top-bourbons",
        "title": "Top Bourbons",
        "description": "The highest-rated bourbons on SipSense",
        "list_type": "dynamic",
        "category": "bourbon",
        "filters_json": json.dumps({"sort": "rating"}),
        "image_emoji": "\U0001f947",
        "display_order": 1,
    },
    {
        "slug": "top-scotch",
        "title": "Top Scotch Whisky",
        "description": "Community favorites from Scotland",
        "list_type": "dynamic",
        "category": "scotch",
        "filters_json": json.dumps({"sort": "rating"}),
        "image_emoji": "\U0001f3f4",
        "display_order": 2,
    },
    {
        "slug": "best-under-50",
        "title": "Best Whiskeys Under $50",
        "description": "Top-rated bottles that won't break the bank",
        "list_type": "dynamic",
        "category": None,
        "filters_json": json.dumps({"max_price": 50, "sort": "rating"}),
        "image_emoji": "\U0001f4b0",
        "display_order": 3,
    },
    {
        "slug": "best-value",
        "title": "Best Value Whiskeys",
        "description": "Highest rating-to-price ratio \u2014 the smart picks",
        "list_type": "dynamic",
        "category": None,
        "filters_json": json.dumps({"sort": "value", "max_price": 100}),
        "image_emoji": "\U0001f4c8",
        "display_order": 4,
    },
    {
        "slug": "top-japanese",
        "title": "Top Japanese Whisky",
        "description": "The best of Japanese whisky craftsmanship",
        "list_type": "dynamic",
        "category": "japanese",
        "filters_json": json.dumps({"sort": "rating"}),
        "image_emoji": "\U0001f1ef\U0001f1f5",
        "display_order": 5,
    },
    {
        "slug": "top-rye",
        "title": "Top Rye Whiskeys",
        "description": "Spice-forward ryes the community loves",
        "list_type": "dynamic",
        "category": "rye",
        "filters_json": json.dumps({"sort": "rating"}),
        "image_emoji": "\U0001f33e",
        "display_order": 6,
    },
    {
        "slug": "premium-picks",
        "title": "Premium Picks ($100+)",
        "description": "Top-shelf bottles worth the splurge",
        "list_type": "dynamic",
        "category": None,
        "filters_json": json.dumps({"min_price": 100, "sort": "rating"}),
        "image_emoji": "\U0001f451",
        "display_order": 7,
    },
    {
        "slug": "top-irish",
        "title": "Top Irish Whiskey",
        "description": "Ireland's smoothest and most beloved",
        "list_type": "dynamic",
        "category": "irish",
        "filters_json": json.dumps({"sort": "rating"}),
        "image_emoji": "\u2618\ufe0f",
        "display_order": 8,
    },
]


def seed_toplists(db: Session):
    """Insert or update top list definitions."""
    existing = {tl.slug: tl for tl in db.query(models.TopList).all()}
    created = 0
    for defn in TOP_LIST_DEFINITIONS:
        if defn["slug"] not in existing:
            db.add(models.TopList(**defn))
            created += 1
        else:
            tl = existing[defn["slug"]]
            for key, val in defn.items():
                if key != "slug":
                    setattr(tl, key, val)
    if created:
        db.commit()
        logger.info("Seeded %d new top lists", created)
    else:
        db.commit()
