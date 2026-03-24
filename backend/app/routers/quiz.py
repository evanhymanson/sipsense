from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import schemas, models
from ..database import get_db
from ..ml.recommender import quiz_recommendations
from ..auth import get_optional_user
from ..track import track_action
from ..analytics_constants import ACTION_QUIZ_COMPLETE

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/", response_model=list[schemas.QuizRecommendation])
def submit_quiz(
    answers: schemas.QuizAnswers,
    top_n: int = 6,
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    results = quiz_recommendations(answers, db, top_n=top_n)

    # Mark quiz as completed for authenticated users
    if current_user and not current_user.quiz_completed:
        current_user.quiz_completed = True
        track_action(db, current_user.username, ACTION_QUIZ_COMPLETE)
        db.commit()

    return [
        schemas.QuizRecommendation(
            whiskey=schemas.WhiskeyRead.model_validate(w),
            score=round(score, 4),
            reason=reason,
        )
        for w, score, reason in results
    ]
