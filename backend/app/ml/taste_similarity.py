"""Taste vector similarity for palate matching and user suggestions."""

import numpy as np
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc

from .. import models
from .recommender import FLAVOR_TAGS, CATEGORIES, _whiskey_vector


def build_taste_vector(username: str, db: Session) -> dict:
    """Build a user's aggregated taste profile vector from their ratings.

    Returns a dict with:
      - has_data: bool
      - vector: np.ndarray (normalized)
      - total: int (number of ratings)
      - category_scores: {category: {avg, count}}
      - top_flavors: [str] (most common flavor tags)
      - top_categories: [str] (most rated categories)
    """
    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == username)
        .options(joinedload(models.UserRating.whiskey))
        .all()
    )

    if len(ratings) < 2:
        return {"has_data": False, "vector": np.zeros(0), "total": len(ratings),
                "category_scores": {}, "top_flavors": [], "top_categories": []}

    # Build weighted centroid of whiskey vectors (weighted by score)
    vectors = []
    weights = []
    category_data: dict[str, list[float]] = {}
    flavor_counts: dict[str, int] = {}

    for r in ratings:
        if not r.whiskey:
            continue
        vec = _whiskey_vector(r.whiskey)
        vectors.append(vec)
        weights.append(r.score)

        # Track category scores
        cat = (r.whiskey.category or "unknown").lower()
        category_data.setdefault(cat, []).append(r.score)

        # Track flavor mentions
        profile = (r.whiskey.flavor_profile or "").lower()
        for tag in FLAVOR_TAGS:
            if tag in profile:
                flavor_counts[tag] = flavor_counts.get(tag, 0) + 1

    if not vectors:
        return {"has_data": False, "vector": np.zeros(0), "total": len(ratings),
                "category_scores": {}, "top_flavors": [], "top_categories": []}

    # Weighted centroid
    vecs = np.array(vectors)
    w = np.array(weights, dtype=np.float32)
    centroid = np.average(vecs, axis=0, weights=w)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    # Category scores
    category_scores = {
        cat: {"avg": round(sum(scores) / len(scores), 2), "count": len(scores)}
        for cat, scores in category_data.items()
    }

    # Top flavors and categories
    top_flavors = sorted(flavor_counts, key=flavor_counts.get, reverse=True)[:8]
    top_categories = sorted(category_scores, key=lambda c: category_scores[c]["count"], reverse=True)[:5]

    return {
        "has_data": True,
        "vector": centroid,
        "total": len(ratings),
        "category_scores": category_scores,
        "top_flavors": top_flavors,
        "top_categories": top_categories,
    }


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def compute_palate_match(username_a: str, username_b: str, db: Session) -> dict:
    """Full palate match comparison between two users."""
    profile_a = build_taste_vector(username_a, db)
    profile_b = build_taste_vector(username_b, db)

    if not profile_a["has_data"] or not profile_b["has_data"]:
        return {
            "match_score": None,
            "shared_flavors": [],
            "agreements": [],
            "disagreements": [],
            "your_total_rated": profile_a["total"],
            "their_total_rated": profile_b["total"],
            "message": "Not enough ratings to compare (need at least 2 each)",
        }

    score = cosine_similarity(profile_a["vector"], profile_b["vector"])
    match_pct = int(score * 100)

    # Category agreement/disagreement
    agreements = []
    disagreements = []
    all_cats = set(profile_a["category_scores"]) | set(profile_b["category_scores"])
    for cat in all_cats:
        a_data = profile_a["category_scores"].get(cat)
        b_data = profile_b["category_scores"].get(cat)
        if a_data and b_data:
            a_avg = a_data["avg"]
            b_avg = b_data["avg"]
            entry = {"category": cat, "your_avg": a_avg, "their_avg": b_avg}
            if abs(a_avg - b_avg) < 0.8:
                agreements.append(entry)
            else:
                disagreements.append(entry)

    # Shared top flavors
    flavors_a = set(profile_a["top_flavors"][:5])
    flavors_b = set(profile_b["top_flavors"][:5])
    shared_flavors = list(flavors_a & flavors_b)

    return {
        "match_score": match_pct,
        "shared_flavors": shared_flavors,
        "agreements": agreements[:5],
        "disagreements": disagreements[:3],
        "your_total_rated": profile_a["total"],
        "their_total_rated": profile_b["total"],
        "message": None,
    }


def find_similar_users(
    username: str,
    db: Session,
    exclude_ids: set[str],
    limit: int = 5,
) -> list[dict]:
    """Find users with similar taste profiles.

    Returns list of {username, match_score, reason, checkin_count}.
    """
    my_profile = build_taste_vector(username, db)
    if not my_profile["has_data"]:
        return []

    # Find candidate users with >= 2 ratings, excluding already-followed and self
    all_exclude = exclude_ids | {username}
    active_users = (
        db.query(models.UserRating.user_id, sqlfunc.count(models.UserRating.id))
        .filter(models.UserRating.user_id.notin_(all_exclude))
        .group_by(models.UserRating.user_id)
        .having(sqlfunc.count(models.UserRating.id) >= 2)
        .limit(100)
        .all()
    )

    scored = []
    for candidate_username, checkin_count in active_users:
        candidate_profile = build_taste_vector(candidate_username, db)
        if not candidate_profile["has_data"]:
            continue
        sim = cosine_similarity(my_profile["vector"], candidate_profile["vector"])
        match_pct = int(sim * 100)

        # Generate reason
        shared = set(my_profile["top_flavors"][:5]) & set(candidate_profile["top_flavors"][:5])
        top_cats = candidate_profile.get("top_categories", [])
        if match_pct >= 85:
            reason = f"{match_pct}% palate match"
        elif shared:
            reason = f"Also loves {', '.join(list(shared)[:2])}"
        elif top_cats:
            reason = f"Into {top_cats[0]}"
        else:
            reason = f"{match_pct}% similar taste"

        scored.append({
            "username": candidate_username,
            "match_score": match_pct,
            "reason": reason,
            "checkin_count": checkin_count,
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
