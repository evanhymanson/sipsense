"""Post-check-in contextual insights engine.

After a user rates a whiskey, generates 1-3 short insight strings like:
- "This is your 4th peated scotch"
- "You rate Japanese whisky 0.8 stars above your average"
- "First Canadian whisky — welcome to a new world!"
- "You keep coming back to smoky whiskeys — 5 of your last 10"
- "You've now tried whiskeys from 5 different regions!"
"""

import logging

from sqlalchemy import func as sqlfunc, distinct
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

    # ── Category insights ──────────────────────────────────────────────

    if category:
        category_count = (
            db.query(sqlfunc.count(distinct(models.UserRating.whiskey_id)))
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(
                models.UserRating.user_id == user_id,
                sqlfunc.lower(models.Whiskey.category) == category.lower(),
            )
            .scalar() or 0
        )

        if category_count == 1:
            insights.append(f"First {category} — welcome to a new world!")
        elif category_count > 1:
            ordinal = _ordinal(category_count)
            insights.append(f"This is your {ordinal} {category}")

        # Score vs category average
        if category_count > 2:
            category_avg = (
                db.query(sqlfunc.avg(models.UserRating.score))
                .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
                .filter(
                    models.UserRating.user_id == user_id,
                    sqlfunc.lower(models.Whiskey.category) == category.lower(),
                )
                .scalar()
            )
            if category_avg is not None:
                diff = round(score - float(category_avg), 1)
                if abs(diff) >= 0.5:
                    direction = "above" if diff > 0 else "below"
                    insights.append(
                        f"You rate {category} {abs(diff):.1f} stars {direction} your average"
                    )

        # New personal favorite in category
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

    # ── Region insights ────────────────────────────────────────────────

    region = (whiskey.region or "").strip()
    if region:
        region_count = (
            db.query(sqlfunc.count(distinct(models.UserRating.whiskey_id)))
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(
                models.UserRating.user_id == user_id,
                sqlfunc.lower(models.Whiskey.region) == region.lower(),
            )
            .scalar() or 0
        )

        if region_count == 1:
            insights.append(f"First from {region} — new territory unlocked!")
        elif region_count >= 3 and region_count % 3 == 0:
            insights.append(f"This is your {_ordinal(region_count)} from {region} — you're drawn to the region")

    # ── Region exploration milestone ───────────────────────────────────

    total_regions = (
        db.query(sqlfunc.count(distinct(models.Whiskey.region)))
        .join(models.UserRating, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(
            models.UserRating.user_id == user_id,
            models.Whiskey.region != None,
            models.Whiskey.region != "",
        )
        .scalar() or 0
    )
    if total_regions in (5, 10, 15, 20):
        insights.append(f"You've now tried whiskeys from {total_regions} different regions!")

    # ── Flavor profile insights ────────────────────────────────────────

    whiskey_flavors = {
        f.strip().lower()
        for f in (whiskey.flavor_profile or "").split(",")
        if f.strip()
    }
    if whiskey_flavors:
        # Check recent 10 check-ins for recurring flavor tags
        recent_whiskey_ids = (
            db.query(models.UserRating.whiskey_id)
            .filter(models.UserRating.user_id == user_id)
            .order_by(models.UserRating.created_at.desc())
            .limit(10)
            .subquery()
        )
        recent_whiskey_select = db.query(recent_whiskey_ids.c.whiskey_id)
        recent_whiskeys = (
            db.query(models.Whiskey.flavor_profile)
            .filter(
                models.Whiskey.id.in_(recent_whiskey_select),
                models.Whiskey.flavor_profile != None,
            )
            .all()
        )

        if len(recent_whiskeys) >= 5:
            # Count flavor occurrences across recent check-ins
            flavor_counts: dict[str, int] = {}
            for (fp,) in recent_whiskeys:
                for tag in (fp or "").split(","):
                    tag = tag.strip().lower()
                    if tag:
                        flavor_counts[tag] = flavor_counts.get(tag, 0) + 1

            # Find flavors in this whiskey that appear in 50%+ of recent check-ins
            for flavor in whiskey_flavors:
                count = flavor_counts.get(flavor, 0)
                if count >= len(recent_whiskeys) // 2 and count >= 3:
                    insights.append(
                        f"You keep coming back to {flavor} whiskeys — {count} of your last {len(recent_whiskeys)}"
                    )
                    break  # Only one flavor insight

    # ── Score trend insight ────────────────────────────────────────────

    recent_scores = (
        db.query(models.UserRating.score)
        .filter(models.UserRating.user_id == user_id)
        .order_by(models.UserRating.created_at.desc())
        .limit(4)
        .all()
    )
    if len(recent_scores) >= 4 and all(s.score >= 4.0 for s in recent_scores):
        insights.append("You've rated your last 4 check-ins 4+ stars — on a hot streak!")

    # ── Serving style pattern ──────────────────────────────────────────

    # Get the serving style from the just-submitted rating
    current_rating = (
        db.query(models.UserRating)
        .filter(
            models.UserRating.user_id == user_id,
            models.UserRating.whiskey_id == whiskey_id,
        )
        .first()
    )
    serving_style = (current_rating.serving_style or "").strip().lower() if current_rating else ""

    if serving_style and category:
        # How does the user typically serve this category?
        style_rows = (
            db.query(models.UserRating.serving_style)
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(
                models.UserRating.user_id == user_id,
                sqlfunc.lower(models.Whiskey.category) == category.lower(),
                models.UserRating.serving_style != None,
                models.UserRating.serving_style != "",
            )
            .all()
        )
        if len(style_rows) >= 4:
            style_counts: dict[str, int] = {}
            for (s,) in style_rows:
                s_lower = (s or "").strip().lower()
                if s_lower:
                    style_counts[s_lower] = style_counts.get(s_lower, 0) + 1

            dominant_style = max(style_counts, key=style_counts.get) if style_counts else None
            dominant_count = style_counts.get(dominant_style, 0) if dominant_style else 0

            if dominant_style and dominant_count >= len(style_rows) * 0.75:
                alt = _suggest_alt_serving(dominant_style)
                if alt and serving_style == dominant_style:
                    insights.append(
                        f"You almost always drink {category} {dominant_style} — have you tried it {alt}?"
                    )

    # Return top 3, prioritizing category insights first (they're at the front)
    return insights[:3]


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string: 1->1st, 2->2nd, etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _suggest_alt_serving(style: str) -> str | None:
    """Suggest an alternative serving style."""
    alts = {
        "neat": "on the rocks",
        "rocks": "neat",
        "cocktail": "neat",
        "highball": "neat",
    }
    return alts.get(style)
