"""Seed sample critic scores for popular whiskeys."""

import logging
from sqlalchemy.orm import Session
from . import models

logger = logging.getLogger(__name__)

CRITIC_SOURCES = {
    "whisky_advocate": "Whisky Advocate",
    "jim_murray": "Jim Murray's Whisky Bible",
    "wine_enthusiast": "Wine Enthusiast",
}

# (whiskey_name_contains, source, score, max_score, year, review_text)
SAMPLE_SCORES = [
    ("Buffalo Trace", "whisky_advocate", 90, 100, 2024,
     "A versatile bourbon with notes of vanilla, toffee, and subtle oak."),
    ("Buffalo Trace", "jim_murray", 92, 100, 2024,
     "Continuously impressive. Honey and oak in perfect harmony."),
    ("Maker\'s Mark", "whisky_advocate", 88, 100, 2024,
     "Soft, gentle wheat-forward bourbon with baking spice."),
    ("Maker\'s Mark", "wine_enthusiast", 90, 100, 2023,
     "Round and approachable with caramel and vanilla sweetness."),
    ("Ardbeg 10", "whisky_advocate", 95, 100, 2024,
     "Peaty perfection with citrus and espresso."),
    ("Ardbeg 10", "jim_murray", 94.5, 100, 2024,
     "Brilliant stuff. Complexity that unfolds in layers."),
    ("Macallan 12", "whisky_advocate", 91, 100, 2024,
     "Rich sherry cask influence with dried fruit and spice."),
    ("Macallan 12", "jim_murray", 89, 100, 2024,
     "Dependable sherry-bomb. Consistent if not groundbreaking."),
    ("Lagavulin 16", "whisky_advocate", 96, 100, 2024,
     "One of the great single malts. Smoky, maritime, complex."),
    ("Lagavulin 16", "jim_murray", 95, 100, 2024,
     "An Islay benchmark. Magnificent."),
    ("Woodford Reserve", "whisky_advocate", 89, 100, 2024,
     "A well-balanced Kentucky straight bourbon with rich chocolate notes."),
    ("Jameson", "whisky_advocate", 85, 100, 2024,
     "The definitive Irish whiskey. Smooth, approachable, versatile."),
    ("Jameson", "wine_enthusiast", 87, 100, 2023,
     "Smooth and easy with green apple and vanilla."),
    ("Glenfiddich 12", "whisky_advocate", 87, 100, 2024,
     "The quintessential Speyside malt. Fruity and delicate."),
    ("Wild Turkey 101", "whisky_advocate", 91, 100, 2024,
     "Excellent value. Bold and spicy with a long finish."),
    ("Wild Turkey 101", "jim_murray", 93, 100, 2024,
     "One of the great bourbons at any price point."),
]


def seed_critics(db: Session):
    """Seed sample critic scores for popular whiskeys."""
    existing_count = db.query(models.CriticScore).count()
    if existing_count > 0:
        return

    created = 0
    for name_contains, source, score, max_score, year, text in SAMPLE_SCORES:
        whiskey = (
            db.query(models.Whiskey)
            .filter(models.Whiskey.name.ilike(f"%{name_contains}%"))
            .first()
        )
        if not whiskey:
            continue

        db.add(models.CriticScore(
            whiskey_id=whiskey.id,
            source=source,
            source_display=CRITIC_SOURCES.get(source, source),
            score=score,
            max_score=max_score,
            review_year=year,
            review_text=text,
        ))
        created += 1

    if created:
        db.commit()
        logger.info("Seeded %d critic scores", created)
