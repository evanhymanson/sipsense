import logging
import time

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from .. import schemas, models
from ..database import get_db
from ..ml.recommender import content_based_recommendations
from ..ml.inference import get_ncf_recommendations, model_available
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# TTL cache for recommendation results: {(username, top_n): (timestamp, results)}
_rec_cache: dict[tuple, tuple[float, list]] = {}
_REC_TTL = 300  # 5 minutes
_REC_MAX_ENTRIES = 200


@router.get("/", response_model=list[schemas.RecommendationResponse])
def get_recommendations(
    top_n: int = Query(default=5, ge=1, le=20),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cache_key = (current_user.username, top_n)
    now = time.time()

    # Check cache
    entry = _rec_cache.get(cache_key)
    if entry and now - entry[0] < _REC_TTL:
        return entry[1]

    # Try PyTorch NCF model first
    if model_available():
        ncf_results = get_ncf_recommendations(
            username=current_user.username,
            db=db,
            top_n=top_n,
        )
        if ncf_results:
            logger.info("Serving NCF recommendations for %s", current_user.username)
            results = [
                schemas.RecommendationResponse(whiskey=whiskey, score=score)
                for whiskey, score in ncf_results
            ]
            _cache_recs(cache_key, now, results)
            return results

    # Fallback to content-based cosine similarity
    raw = content_based_recommendations(
        user_id=current_user.username,
        db=db,
        top_n=top_n,
    )
    results = [
        schemas.RecommendationResponse(whiskey=whiskey, score=score)
        for whiskey, score in raw
    ]
    _cache_recs(cache_key, now, results)
    return results


def _cache_recs(key: tuple, now: float, results: list):
    if len(_rec_cache) >= _REC_MAX_ENTRIES:
        oldest = min(_rec_cache, key=lambda k: _rec_cache[k][0])
        del _rec_cache[oldest]
    _rec_cache[key] = (now, results)


def invalidate_user_recs(username: str):
    """Clear cached recommendations for a user (e.g. after they rate a whiskey)."""
    stale = [k for k in _rec_cache if k[0] == username]
    for k in stale:
        del _rec_cache[k]
