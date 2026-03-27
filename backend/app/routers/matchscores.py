"""Personal match scores: predicted compatibility between user and whiskeys."""

import time
import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user
from ..ml.taste_similarity import build_taste_vector, cosine_similarity
from ..ml.recommender import _whiskey_vector

router = APIRouter(prefix="/match-scores", tags=["match-scores"])

# Simple TTL cache for user taste vectors to avoid re-querying on every page
_taste_cache: dict[str, tuple[float, dict]] = {}
_TASTE_TTL = 300  # 5 minutes
_TASTE_MAX = 200


def _get_taste_vector(username: str, db: Session) -> dict:
    """Get user taste vector with caching."""
    now = time.time()
    cached = _taste_cache.get(username)
    if cached and now - cached[0] < _TASTE_TTL:
        return cached[1]

    profile = build_taste_vector(username, db)

    # Evict oldest entries if cache is full
    if len(_taste_cache) >= _TASTE_MAX:
        oldest = min(_taste_cache, key=lambda k: _taste_cache[k][0])
        del _taste_cache[oldest]

    _taste_cache[username] = (now, profile)
    return profile


@router.post("/batch")
def batch_match_scores(
    whiskey_ids: list[int],
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Compute personal match scores for a list of whiskey IDs.
    Returns {scores: {id: pct}, has_profile: bool}.
    Max 50 whiskeys per request.
    """
    if len(whiskey_ids) > 50:
        whiskey_ids = whiskey_ids[:50]

    profile = _get_taste_vector(current_user.username, db)
    if not profile["has_data"]:
        return {"scores": {}, "has_profile": False}

    user_vec = profile["vector"]

    whiskeys = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.id.in_(whiskey_ids))
        .all()
    )

    scores = {}
    for w in whiskeys:
        w_vec = _whiskey_vector(w)
        sim = cosine_similarity(user_vec, w_vec)
        scores[w.id] = max(0, min(100, int(sim * 100)))

    return {"scores": scores, "has_profile": True}
