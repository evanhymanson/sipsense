"""Taste Identity — palate evolution, percentile rankings, and blind taste quiz.

GET /taste-identity/evolution     — monthly taste snapshots + narrative diff
GET /taste-identity/percentiles   — ranking against all users
GET /taste-identity/quiz-question — blind taste quiz (4 options)
POST /taste-identity/quiz-answer  — check answer, update streak
"""

import hashlib
import random
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func as sqlfunc, distinct, case, literal_column
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db, _is_sqlite
from ..auth import get_current_user, get_optional_user

router = APIRouter(prefix="/taste-identity", tags=["taste-identity"])


# ── Palate Evolution ────────────────────────────────────────────────────


@router.get("/evolution")
def get_evolution(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Monthly taste snapshots computed on-the-fly from ratings."""
    user_id = current_user.username

    # Group ratings by month
    if _is_sqlite:
        month_expr = sqlfunc.strftime("%Y-%m", models.UserRating.created_at)
    else:
        month_expr = sqlfunc.to_char(models.UserRating.created_at, "YYYY-MM")

    month_rows = (
        db.query(
            month_expr.label("month"),
            sqlfunc.count(models.UserRating.id).label("count"),
            sqlfunc.avg(models.UserRating.score).label("avg_score"),
        )
        .filter(models.UserRating.user_id == user_id)
        .group_by(month_expr)
        .order_by(month_expr)
        .all()
    )

    if not month_rows:
        return {"months": [], "evolution_narrative": None, "current_vs_3mo_ago": None}

    # Build monthly snapshots with category breakdown
    months = []
    for row in month_rows:
        # Get category distribution for this month
        if _is_sqlite:
            month_filter = sqlfunc.strftime("%Y-%m", models.UserRating.created_at) == row.month
        else:
            month_filter = sqlfunc.to_char(models.UserRating.created_at, "YYYY-MM") == row.month

        cat_rows = (
            db.query(
                models.Whiskey.category,
                sqlfunc.count(models.UserRating.id).label("cnt"),
            )
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(models.UserRating.user_id == user_id, month_filter)
            .group_by(models.Whiskey.category)
            .order_by(sqlfunc.count(models.UserRating.id).desc())
            .all()
        )

        cat_dist = {c.category: c.cnt for c in cat_rows if c.category}
        top_cat = cat_rows[0].category if cat_rows else None

        months.append({
            "month": row.month,
            "count": row.count,
            "avg_score": round(float(row.avg_score), 2) if row.avg_score else None,
            "top_category": top_cat,
            "category_distribution": cat_dist,
        })

    # Compare current month vs 3 months ago
    narrative = None
    comparison = None
    if len(months) >= 2:
        current = months[-1]
        # Find the snapshot from ~3 months ago (or the earliest available)
        past_idx = max(0, len(months) - 4)
        past = months[past_idx]

        current_cats = set(current.get("category_distribution", {}).keys())
        past_cats = set(past.get("category_distribution", {}).keys())
        new_cats = current_cats - past_cats

        score_diff = None
        if current["avg_score"] and past["avg_score"]:
            score_diff = round(current["avg_score"] - past["avg_score"], 1)

        comparison = {
            "new_categories": list(new_cats),
            "score_trend": f"{'+' if score_diff and score_diff > 0 else ''}{score_diff}" if score_diff else "0",
            "diversity_change": "expanded" if new_cats else "steady",
            "past_month": past["month"],
        }

        # Build narrative
        past_top = past.get("top_category", "whiskey")
        current_top = current.get("top_category", "whiskey")
        if new_cats:
            narrative = f"In {past['month']} you were mostly into {past_top}. Since then you've explored {', '.join(new_cats)} — your palate is evolving!"
        elif current_top != past_top:
            narrative = f"You've shifted from {past_top} to {current_top} — interesting evolution!"
        elif score_diff and abs(score_diff) >= 0.3:
            direction = "more generous" if score_diff > 0 else "more critical"
            narrative = f"Your ratings have gotten {direction} (avg {score_diff:+.1f} stars). Your palate is maturing."
        else:
            narrative = f"You've been consistently into {current_top}. Deep expertise in the making!"

    return {
        "months": months,
        "evolution_narrative": narrative,
        "current_vs_3mo_ago": comparison,
    }


# ── Percentile Rankings ─────────────────────────────────────────────────


@router.get("/percentiles")
def get_percentiles(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Percentile rankings compared to all users."""
    user_id = current_user.username

    # Total ratings per user
    user_counts = (
        db.query(
            models.UserRating.user_id,
            sqlfunc.count(models.UserRating.id).label("cnt"),
        )
        .group_by(models.UserRating.user_id)
        .all()
    )

    if not user_counts:
        return {
            "total_rated_percentile": 0,
            "top_category": None,
            "top_category_percentile": None,
            "top_category_count": None,
            "diversity_score": 0,
            "total_users": 0,
        }

    total_users = len(user_counts)
    count_map = {uc.user_id: uc.cnt for uc in user_counts}
    my_count = count_map.get(user_id, 0)

    # Percentile: % of users with fewer ratings
    below_me = sum(1 for uid, cnt in count_map.items() if cnt < my_count and uid != user_id)
    total_rated_percentile = round((below_me / max(total_users - 1, 1)) * 100)

    # Top category for this user
    top_cat_row = (
        db.query(
            models.Whiskey.category,
            sqlfunc.count(distinct(models.UserRating.whiskey_id)).label("cnt"),
        )
        .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(models.UserRating.user_id == user_id)
        .group_by(models.Whiskey.category)
        .order_by(sqlfunc.count(distinct(models.UserRating.whiskey_id)).desc())
        .first()
    )

    category_rank = None
    if top_cat_row and top_cat_row.category:
        cat = top_cat_row.category
        my_cat_count = top_cat_row.cnt

        # Count users with fewer ratings in this category
        cat_counts = (
            db.query(
                models.UserRating.user_id,
                sqlfunc.count(distinct(models.UserRating.whiskey_id)).label("cnt"),
            )
            .join(models.Whiskey, models.UserRating.whiskey_id == models.Whiskey.id)
            .filter(sqlfunc.lower(models.Whiskey.category) == cat.lower())
            .group_by(models.UserRating.user_id)
            .all()
        )
        cat_users = len(cat_counts)
        below_in_cat = sum(1 for _, cnt in cat_counts if cnt < my_cat_count)
        cat_percentile = round((below_in_cat / max(cat_users - 1, 1)) * 100)

        category_rank = {
            "category": cat,
            "user_count_in_category": my_cat_count,
            "percentile": cat_percentile,
        }

    # Diversity score: unique categories rated / 8 possible
    unique_cats = (
        db.query(sqlfunc.count(distinct(models.Whiskey.category)))
        .join(models.UserRating, models.UserRating.whiskey_id == models.Whiskey.id)
        .filter(models.UserRating.user_id == user_id)
        .scalar() or 0
    )
    diversity_score = round((unique_cats / 8) * 10, 1)

    return {
        "total_rated_percentile": total_rated_percentile,
        "top_category": category_rank["category"] if category_rank else None,
        "top_category_percentile": category_rank["percentile"] if category_rank else None,
        "top_category_count": category_rank["user_count_in_category"] if category_rank else None,
        "diversity_score": diversity_score,
        "total_users": total_users,
    }


# ── Blind Taste Quiz ────────────────────────────────────────────────────


@router.get("/quiz-question")
def get_quiz_question(db: Session = Depends(get_db)):
    """Return a blind taste quiz question with 4 options."""
    # Pick a random whiskey with flavor profile
    candidates = (
        db.query(models.Whiskey)
        .filter(
            models.Whiskey.flavor_profile != None,
            models.Whiskey.flavor_profile != "",
            models.Whiskey.category != None,
        )
        .all()
    )

    if len(candidates) < 4:
        return {"error": "Not enough whiskeys for a quiz"}

    # Use date-based seed for some determinism but allow multiple per day
    seed = int(hashlib.sha256(date.today().isoformat().encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    correct = rng.choice(candidates)

    # Pick 3 distractors from different categories
    other_cats = [w for w in candidates if w.id != correct.id]
    # Prefer different categories for variety
    diff_cat = [w for w in other_cats if (w.category or "").lower() != (correct.category or "").lower()]
    same_cat = [w for w in other_cats if (w.category or "").lower() == (correct.category or "").lower()]

    distractors = []
    if len(diff_cat) >= 3:
        distractors = rng.sample(diff_cat, 3)
    else:
        pool = diff_cat + same_cat
        distractors = rng.sample(pool, min(3, len(pool)))

    options = [correct] + distractors
    rng.shuffle(options)

    # Build flavor clues
    flavors = [f.strip() for f in (correct.flavor_profile or "").split(",") if f.strip()]

    clues = {
        "flavor_tags": flavors[:5],
        "abv_hint": f"{correct.abv:.0f}% ABV" if correct.abv else None,
        "price_range": _price_range(correct.price_usd),
    }

    return {
        "correct_id": correct.id,
        "clues": clues,
        "options": [
            {"id": w.id, "name": w.name, "distillery": w.distillery}
            for w in options
        ],
    }


@router.post("/quiz-answer")
def submit_quiz_answer(
    body: dict,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Check quiz answer.  If authenticated, records activity and updates streak."""
    correct_id = body.get("correct_id")
    answer_id = body.get("answer_id")
    is_correct = correct_id == answer_id

    # Look up the correct whiskey for the reveal
    correct_whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == correct_id).first()
    reveal = None
    if correct_whiskey:
        reveal = {
            "id": correct_whiskey.id,
            "name": correct_whiskey.name,
            "distillery": correct_whiskey.distillery,
            "category": correct_whiskey.category,
            "description": correct_whiskey.description,
        }

    streak_info = None
    if current_user:
        from ..streaks import record_daily_activity
        from ..track import track_action
        streak_data = record_daily_activity(current_user.username, db)
        track_action(db, current_user.username, "daily_quiz",
                     detail={"correct": is_correct})
        db.commit()
        streak_info = streak_data

    return {
        "correct": is_correct,
        "correct_whiskey": reveal,
        "streak": streak_info,
    }


def _price_range(price: float | None) -> str | None:
    """Convert price to a vague range hint."""
    if not price:
        return None
    if price < 30:
        return "Budget-friendly (under $30)"
    elif price < 60:
        return "Mid-range ($30-60)"
    elif price < 100:
        return "Premium ($60-100)"
    else:
        return "Top-shelf ($100+)"
