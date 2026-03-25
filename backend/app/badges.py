"""
Badge definitions and evaluation engine.

After each check-in, call evaluate_badges(user_id, db) to award any
newly-earned badges.  Returns a list of Badge objects that were just awarded.
"""

import logging
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, distinct
from . import models

logger = logging.getLogger(__name__)

BADGE_DEFINITIONS = [
    # ── Milestone badges ──────────────────────────────────────────────────
    {
        "slug": "first_sip",
        "name": "First Sip",
        "description": "Rate your first whiskey",
        "emoji": "🥃",
        "category": "milestone",
    },
    {
        "slug": "the_regular",
        "name": "The Regular",
        "description": "25 check-ins and counting",
        "emoji": "🔁",
        "category": "milestone",
    },
    {
        "slug": "connoisseur",
        "name": "Connoisseur",
        "description": "50 check-ins — you know your whiskey",
        "emoji": "🎩",
        "category": "milestone",
    },
    # ── Style badges ──────────────────────────────────────────────────────
    {
        "slug": "bourbon_trail",
        "name": "Bourbon Trail",
        "description": "Rate 5 different bourbons",
        "emoji": "🏇",
        "category": "style",
    },
    {
        "slug": "peat_freak",
        "name": "Peat Freak",
        "description": "Rate 5 Islay scotches",
        "emoji": "🔥",
        "category": "style",
    },
    {
        "slug": "master_blender",
        "name": "Master Blender",
        "description": "Try all 8 whiskey categories",
        "emoji": "🧪",
        "category": "style",
    },
    {
        "slug": "world_traveler",
        "name": "World Traveler",
        "description": "Rate whiskeys from 4+ countries",
        "emoji": "🌍",
        "category": "style",
    },
    # ── Taste badges ──────────────────────────────────────────────────────
    {
        "slug": "high_roller",
        "name": "High Roller",
        "description": "Check in a bottle worth $200+",
        "emoji": "💎",
        "category": "taste",
    },
    {
        "slug": "cask_strength",
        "name": "Cask Strength",
        "description": "Rate a whiskey at 55% ABV or higher",
        "emoji": "💪",
        "category": "taste",
    },
    {
        "slug": "top_shelf",
        "name": "Top Shelf",
        "description": "Give a perfect 5-star rating",
        "emoji": "⭐",
        "category": "taste",
    },
]

# Map region → country for world_traveler badge
_REGION_COUNTRY = {
    "kentucky": "USA", "tennessee": "USA", "usa": "USA", "america": "USA",
    "indiana": "USA", "texas": "USA", "new york": "USA", "oregon": "USA",
    "colorado": "USA", "virginia": "USA", "california": "USA",
    "speyside": "Scotland", "highland": "Scotland", "highlands": "Scotland",
    "islay": "Scotland", "lowland": "Scotland", "lowlands": "Scotland",
    "campbeltown": "Scotland", "scotland": "Scotland", "islands": "Scotland",
    "ireland": "Ireland", "cork": "Ireland", "midleton": "Ireland",
    "japan": "Japan", "tokyo": "Japan", "hokkaido": "Japan",
    "canada": "Canada", "ontario": "Canada", "alberta": "Canada",
    "taiwan": "Taiwan", "india": "India", "australia": "Australia",
    "france": "France", "england": "England", "wales": "Wales",
    "sweden": "Sweden", "germany": "Germany", "netherlands": "Netherlands",
}

ALL_CATEGORIES = {"bourbon", "scotch", "irish", "japanese", "rye", "canadian", "single malt", "blended"}


def seed_badges(db: Session) -> None:
    """Insert badge definitions if they don't already exist."""
    existing = {b.slug for b in db.query(models.Badge).all()}
    for defn in BADGE_DEFINITIONS:
        if defn["slug"] not in existing:
            db.add(models.Badge(**defn))
    db.commit()


def evaluate_badges(user_id: str, db: Session) -> list[models.Badge]:
    """Check all badge conditions and award any new ones.  Returns newly awarded badges."""
    already = {
        ub.badge_slug
        for ub in db.query(models.UserBadge).filter(models.UserBadge.user_id == user_id).all()
    }

    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id)
        .all()
    )
    if not ratings:
        return []

    # Preload whiskeys for rated IDs
    rated_ids = [r.whiskey_id for r in ratings]
    whiskeys = {
        w.id: w
        for w in db.query(models.Whiskey).filter(models.Whiskey.id.in_(rated_ids)).all()
    }

    total = len(ratings)
    unique_ids = {r.whiskey_id for r in ratings}

    new_slugs: list[str] = []

    # ── Milestones ────────────────────────────────────────────────────────
    if "first_sip" not in already and total >= 1:
        new_slugs.append("first_sip")
    if "the_regular" not in already and total >= 25:
        new_slugs.append("the_regular")
    if "connoisseur" not in already and total >= 50:
        new_slugs.append("connoisseur")

    # ── Style: bourbon_trail (5 unique bourbons) ─────────────────────────
    if "bourbon_trail" not in already:
        bourbon_ids = {
            wid for wid in unique_ids
            if wid in whiskeys and (whiskeys[wid].category or "").lower() == "bourbon"
        }
        if len(bourbon_ids) >= 5:
            new_slugs.append("bourbon_trail")

    # ── Style: peat_freak (5 Islay scotches) ─────────────────────────────
    if "peat_freak" not in already:
        islay_ids = {
            wid for wid in unique_ids
            if wid in whiskeys
            and (whiskeys[wid].category or "").lower() in ("scotch", "single malt")
            and "islay" in (whiskeys[wid].region or "").lower()
        }
        if len(islay_ids) >= 5:
            new_slugs.append("peat_freak")

    # ── Style: master_blender (all 8 categories) ─────────────────────────
    if "master_blender" not in already:
        cats = {
            (whiskeys[wid].category or "").lower()
            for wid in unique_ids if wid in whiskeys
        }
        if cats >= ALL_CATEGORIES:
            new_slugs.append("master_blender")

    # ── Style: world_traveler (4+ countries) ─────────────────────────────
    if "world_traveler" not in already:
        countries = set()
        for wid in unique_ids:
            w = whiskeys.get(wid)
            if w and w.region:
                country = _REGION_COUNTRY.get(w.region.lower().strip())
                if country:
                    countries.add(country)
        if len(countries) >= 4:
            new_slugs.append("world_traveler")

    # ── Taste: high_roller ($200+) ───────────────────────────────────────
    if "high_roller" not in already:
        for wid in unique_ids:
            w = whiskeys.get(wid)
            if w and w.price_usd and w.price_usd >= 200:
                new_slugs.append("high_roller")
                break

    # ── Taste: cask_strength (55%+ ABV) ──────────────────────────────────
    if "cask_strength" not in already:
        for wid in unique_ids:
            w = whiskeys.get(wid)
            if w and w.abv and w.abv >= 55:
                new_slugs.append("cask_strength")
                break

    # ── Taste: top_shelf (5-star rating) ─────────────────────────────────
    if "top_shelf" not in already:
        if any(r.score >= 5.0 for r in ratings):
            new_slugs.append("top_shelf")

    # ── Award new badges ─────────────────────────────────────────────────
    awarded: list[models.Badge] = []
    for slug in new_slugs:
        badge = db.query(models.Badge).filter(models.Badge.slug == slug).first()
        if badge:
            db.add(models.UserBadge(user_id=user_id, badge_slug=slug))
            awarded.append(badge)

    if awarded:
        db.commit()
        logger.info("Awarded %d badge(s) to %s: %s", len(awarded), user_id, [b.slug for b in awarded])

    return awarded
