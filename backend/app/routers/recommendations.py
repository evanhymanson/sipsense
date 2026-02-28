import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from .. import schemas, models
from ..database import get_db
from ..ml.recommender import content_based_recommendations
from ..ml.inference import get_ncf_recommendations, model_available
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/", response_model=list[schemas.RecommendationResponse])
def get_recommendations(
    top_n: int = Query(default=5, ge=1, le=20),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Try PyTorch NCF model first
    if model_available():
        ncf_results = get_ncf_recommendations(
            username=current_user.username,
            db=db,
            top_n=top_n,
        )
        if ncf_results:
            logger.info("Serving NCF recommendations for %s", current_user.username)
            return [
                schemas.RecommendationResponse(whiskey=whiskey, score=score)
                for whiskey, score in ncf_results
            ]

    # Fallback to content-based cosine similarity
    results = content_based_recommendations(
        user_id=current_user.username,
        db=db,
        top_n=top_n,
    )
    return [
        schemas.RecommendationResponse(whiskey=whiskey, score=score)
        for whiskey, score in results
    ]
