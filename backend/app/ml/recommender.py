"""
SipSense Recommender

Current approach: Content-based filtering using whiskey feature vectors.

Plan for PyTorch upgrade:
  - Collaborative filtering with an embedding model (user_id + whiskey_id -> score)
  - Training loop using user ratings from the DB
  - Model saved to backend/app/ml/model.pt

For now this uses cosine similarity over normalized feature vectors so the
API is fully functional while we wire up the PyTorch training pipeline.
"""

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .. import models

# Hard cap on candidate set size for vector scoring to prevent loading
# the entire whiskeys table into memory on every request.
_MAX_CANDIDATES = 500


# Features used to build the whiskey content vector
FLAVOR_TAGS = [
    "smoky", "peaty", "sweet", "fruity", "floral", "spicy",
    "vanilla", "caramel", "honey", "oak", "nutty", "citrus",
    "chocolate", "leather", "herbal", "grain",
]

CATEGORIES = ["bourbon", "scotch", "irish", "japanese", "rye", "canadian", "single malt", "blended"]


def _whiskey_vector(whiskey: models.Whiskey) -> np.ndarray:
    """Convert a Whiskey DB row into a normalized feature vector."""
    vec = []

    # One-hot encode category
    cat = (whiskey.category or "").lower()
    vec += [1.0 if cat == c else 0.0 for c in CATEGORIES]

    # Numeric features (normalized to ~[0,1])
    vec.append(min((whiskey.abv or 40.0) / 70.0, 1.0))
    vec.append(min((whiskey.age or 10) / 30.0, 1.0))
    vec.append(min((whiskey.price_usd or 50.0) / 300.0, 1.0))

    # Flavor profile one-hot
    profile = (whiskey.flavor_profile or "").lower()
    vec += [1.0 if tag in profile else 0.0 for tag in FLAVOR_TAGS]

    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr


def content_based_recommendations(
    user_id: str,
    db: Session,
    top_n: int = 5,
) -> list[tuple[models.Whiskey, float]]:
    """
    Return top_n whiskeys the user hasn't rated yet, ranked by similarity
    to the centroid of whiskeys they rated highly (score >= 3.5).
    """
    # Fetch user's ratings
    all_ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id)
        .all()
    )
    rated_ids = {r.whiskey_id for r in all_ratings}
    liked_ratings = [r for r in all_ratings if r.score >= 3.5]

    if not liked_ratings:
        # Cold start: return highest-rated whiskeys the user hasn't touched
        q = db.query(models.Whiskey).order_by(models.Whiskey.rating_avg.desc())
        if rated_ids:
            q = q.filter(models.Whiskey.id.notin_(rated_ids))
        unrated = q.limit(top_n).all()
        return [(w, (w.rating_avg or 0) / 5.0) for w in unrated]

    # Build centroid of liked whiskeys (batch query instead of N+1)
    liked_ids = [r.whiskey_id for r in liked_ratings]
    liked_whiskeys = (
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(liked_ids)).all()
        if liked_ids else []
    )
    centroid = np.mean([_whiskey_vector(w) for w in liked_whiskeys], axis=0)

    # SQL prefilter: match on liked categories + flavor keywords
    liked_cats = list({(w.category or "").lower() for w in liked_whiskeys if w.category})
    flavor_tokens = []
    for w in liked_whiskeys:
        if w.flavor_profile:
            for tag in FLAVOR_TAGS:
                if tag in (w.flavor_profile or "").lower():
                    flavor_tokens.append(tag)
    top_flavor_tokens = list(dict.fromkeys(flavor_tokens))[:5]  # dedupe, keep order

    prefilters = []
    if liked_cats:
        prefilters.append(models.Whiskey.category.in_(liked_cats))
    for token in top_flavor_tokens:
        prefilters.append(models.Whiskey.flavor_profile.ilike(f"%{token}%"))

    candidate_q = db.query(models.Whiskey)
    if rated_ids:
        candidate_q = candidate_q.filter(models.Whiskey.id.notin_(rated_ids))
    if prefilters:
        candidate_q = candidate_q.filter(or_(*prefilters))

    candidates = candidate_q.limit(_MAX_CANDIDATES).all()

    # Broaden if prefilter yields too few results
    if len(candidates) < top_n:
        broad_q = db.query(models.Whiskey).order_by(models.Whiskey.rating_avg.desc())
        if rated_ids:
            broad_q = broad_q.filter(models.Whiskey.id.notin_(rated_ids))
        candidates = broad_q.limit(_MAX_CANDIDATES).all()

    # Score candidates by cosine similarity to centroid
    scored = [(w, float(np.dot(_whiskey_vector(w), centroid))) for w in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[:top_n]


# ── Quiz recommendations ────────────────────────────────────────────────────

_BUDGET_PRICE = {
    "budget":  25.0,
    "mid":     55.0,
    "premium": 130.0,
    "luxury":  250.0,
}

_BODY_ABV = {
    "light":  40.0,
    "medium": 46.0,
    "full":   55.0,
}


def _quiz_vector(answers) -> np.ndarray:
    """Build a normalized target vector from quiz answers."""
    vec = []

    # Category — full weight if preference given, neutral (0.5) if "any"
    if answers.style and answers.style != "any":
        cat = answers.style.lower()
        vec += [1.0 if cat == c else 0.0 for c in CATEGORIES]
    else:
        vec += [0.5] * len(CATEGORIES)

    # ABV
    abv = _BODY_ABV.get(answers.body, 46.0)
    vec.append(min(abv / 70.0, 1.0))

    # Age — neutral preference
    vec.append(15.0 / 30.0)

    # Price
    price = _BUDGET_PRICE.get(answers.budget, 55.0)
    vec.append(min(price / 300.0, 1.0))

    # Flavor tags — smokiness drives smoky/peaty; everything else from flavors list
    smoky_val = {"none": 0.0, "light": 0.5, "heavy": 1.0}.get(answers.smokiness, 0.0)
    active = {f.lower() for f in (answers.flavors or [])}

    for tag in FLAVOR_TAGS:
        if tag in ("smoky", "peaty"):
            vec.append(smoky_val)
        elif tag in active:
            vec.append(1.0)
        else:
            vec.append(0.0)

    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr


def _generate_reason(whiskey: models.Whiskey, answers) -> str:
    """Plain-English explanation of why this whiskey matches the quiz."""
    parts = []

    cat = (whiskey.category or "").lower()
    profile = (whiskey.flavor_profile or "").lower()

    # Style match
    if answers.style != "any" and cat == answers.style.lower():
        parts.append(f"a {cat} that hits your style preference")
    elif cat:
        parts.append(f"a {cat}")

    # Flavor overlap (show up to 3 matching tags)
    matched = [f for f in (answers.flavors or []) if f.lower() in profile]
    if matched:
        parts.append(f"with {', '.join(matched[:3])} notes you'll love")

    # Smokiness
    is_smoky = "smoky" in profile or "peaty" in profile
    if answers.smokiness == "heavy" and is_smoky:
        parts.append("bringing the peat you're after")
    elif answers.smokiness == "none" and not is_smoky:
        parts.append("clean with no harsh smoke")

    # Budget
    price = whiskey.price_usd
    ranges = {"budget": (0, 35), "mid": (30, 90), "premium": (80, 210), "luxury": (190, 99999)}
    lo, hi = ranges.get(answers.budget, (0, 99999))
    if price and lo <= price <= hi:
        parts.append(f"fits your {answers.budget} budget")

    if not parts:
        return "A strong match based on your taste profile."
    return "It's " + ", ".join(parts) + "."


def similar_whiskeys(
    whiskey: models.Whiskey,
    db: Session,
    top_n: int = 5,
) -> list[tuple[models.Whiskey, float]]:
    """Return top_n whiskeys most similar to the given one by cosine similarity."""
    target = _whiskey_vector(whiskey)

    # Prefilter: same category or region first, then broaden if needed
    base = db.query(models.Whiskey).filter(models.Whiskey.id != whiskey.id)
    prefilters = []
    if whiskey.category:
        prefilters.append(models.Whiskey.category == whiskey.category)
    if whiskey.region:
        prefilters.append(models.Whiskey.region == whiskey.region)

    if prefilters:
        candidates = base.filter(or_(*prefilters)).limit(_MAX_CANDIDATES).all()
    else:
        candidates = base.limit(_MAX_CANDIDATES).all()

    # Broaden if too few
    if len(candidates) < top_n:
        candidates = (
            base.order_by(models.Whiskey.rating_avg.desc())
            .limit(_MAX_CANDIDATES)
            .all()
        )

    scored = [(w, float(np.dot(_whiskey_vector(w), target))) for w in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def quiz_recommendations(
    answers,
    db: Session,
    top_n: int = 6,
) -> list[tuple[models.Whiskey, float, str]]:
    """Return top_n whiskeys that best match the quiz answers."""
    target = _quiz_vector(answers)

    # SQL prefilter based on quiz answers
    q = db.query(models.Whiskey)
    prefilters = []
    if answers.style and answers.style != "any":
        prefilters.append(models.Whiskey.category.ilike(f"%{answers.style}%"))

    budget_max = _BUDGET_PRICE.get(answers.budget)
    if budget_max:
        # Allow headroom (1.5x) to not over-restrict
        q = q.filter(
            (models.Whiskey.price_usd <= budget_max * 1.5) | (models.Whiskey.price_usd.is_(None))
        )

    if answers.smokiness == "heavy":
        prefilters.append(models.Whiskey.flavor_profile.ilike("%smoky%"))
        prefilters.append(models.Whiskey.flavor_profile.ilike("%peaty%"))

    if prefilters:
        q = q.filter(or_(*prefilters))

    candidates = q.limit(_MAX_CANDIDATES).all()

    # Broaden if needed
    if len(candidates) < top_n:
        candidates = (
            db.query(models.Whiskey)
            .order_by(models.Whiskey.rating_avg.desc())
            .limit(_MAX_CANDIDATES)
            .all()
        )

    scored = []
    for w in candidates:
        v = _whiskey_vector(w)
        score = float(np.dot(v, target))
        scored.append((w, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_n]

    # Attach reasons
    return [(w, score, _generate_reason(w, answers)) for w, score in top]
