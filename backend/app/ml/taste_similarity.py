"""Taste vector similarity for palate matching and user suggestions."""

import numpy as np
from collections import defaultdict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func as sqlfunc

from .. import models
from .recommender import FLAVOR_TAGS, CATEGORIES, _whiskey_vector


def _profile_from_ratings(ratings) -> dict:
    """Build a taste profile dict from a list of (score, whiskey) rating objects."""
    if len(ratings) < 2:
        return {"has_data": False, "vector": np.zeros(0), "total": len(ratings),
                "category_scores": {}, "top_flavors": [], "top_categories": []}

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

        cat = (r.whiskey.category or "unknown").lower()
        category_data.setdefault(cat, []).append(r.score)

        profile = (r.whiskey.flavor_profile or "").lower()
        for tag in FLAVOR_TAGS:
            if tag in profile:
                flavor_counts[tag] = flavor_counts.get(tag, 0) + 1

    if not vectors:
        return {"has_data": False, "vector": np.zeros(0), "total": len(ratings),
                "category_scores": {}, "top_flavors": [], "top_categories": []}

    vecs = np.array(vectors)
    w = np.array(weights, dtype=np.float32)
    centroid = np.average(vecs, axis=0, weights=w)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm

    category_scores = {
        cat: {"avg": round(sum(scores) / len(scores), 2), "count": len(scores)}
        for cat, scores in category_data.items()
    }

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


def build_taste_vector(username: str, db: Session) -> dict:
    """Build a user's aggregated taste profile vector from their ratings."""
    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == username)
        .options(joinedload(models.UserRating.whiskey))
        .all()
    )
    return _profile_from_ratings(ratings)


def _batch_build_taste_vectors(usernames: list[str], db: Session) -> dict[str, dict]:
    """Build taste profiles for multiple users in a single DB query."""
    if not usernames:
        return {}
    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id.in_(usernames))
        .options(joinedload(models.UserRating.whiskey))
        .all()
    )
    grouped: dict[str, list] = defaultdict(list)
    for r in ratings:
        grouped[r.user_id].append(r)
    return {uid: _profile_from_ratings(rs) for uid, rs in grouped.items()}


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def compute_palate_match(username_a: str, username_b: str, db: Session) -> dict:
    """Full palate match comparison between two users."""
    profiles = _batch_build_taste_vectors([username_a, username_b], db)
    empty = {"has_data": False, "vector": np.zeros(0), "total": 0,
             "category_scores": {}, "top_flavors": [], "top_categories": []}
    profile_a = profiles.get(username_a, empty)
    profile_b = profiles.get(username_b, empty)

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

    # Batch-load all candidate taste profiles in one query (instead of N queries)
    candidate_usernames = [u for u, _ in active_users]
    checkin_map = {u: cnt for u, cnt in active_users}
    candidate_profiles = _batch_build_taste_vectors(candidate_usernames, db)

    scored = []
    for candidate_username in candidate_usernames:
        candidate_profile = candidate_profiles.get(candidate_username)
        if not candidate_profile or not candidate_profile["has_data"]:
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
            "checkin_count": checkin_map[candidate_username],
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
