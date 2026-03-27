"""Critic / expert score endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/critics", tags=["critics"])

KNOWN_SOURCES = {
    "whisky_advocate": "Whisky Advocate",
    "jim_murray": "Jim Murray's Whisky Bible",
    "wine_enthusiast": "Wine Enthusiast",
    "scotch_whisky": "Scotch Whisky Magazine",
}


@router.get("/whiskey/{whiskey_id}", response_model=schemas.WhiskeyCriticScores)
def get_critic_scores(whiskey_id: int, db: Session = Depends(get_db)):
    """Get all critic scores for a whiskey."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    rows = (
        db.query(models.CriticScore)
        .filter(models.CriticScore.whiskey_id == whiskey_id)
        .order_by(models.CriticScore.source)
        .all()
    )

    scores = []
    for r in rows:
        normalized = (r.score / r.max_score * 100) if r.max_score else 0
        scores.append(schemas.CriticScoreRead(
            id=r.id,
            source=r.source,
            source_display=r.source_display,
            score=r.score,
            max_score=r.max_score,
            normalized_score=round(normalized, 1),
            review_year=r.review_year,
            review_text=r.review_text,
            url=r.url,
        ))

    avg = None
    if scores:
        avg = round(sum(s.normalized_score for s in scores) / len(scores), 1)

    return schemas.WhiskeyCriticScores(
        whiskey_id=whiskey_id,
        scores=scores,
        avg_critic_score=avg,
    )


@router.post("/", response_model=schemas.CriticScoreRead, status_code=201)
def add_critic_score(
    body: schemas.CriticScoreCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a critic score (authenticated users only)."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == body.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    existing = (
        db.query(models.CriticScore)
        .filter(
            models.CriticScore.whiskey_id == body.whiskey_id,
            models.CriticScore.source == body.source,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Score from this source already exists")

    cs = models.CriticScore(
        whiskey_id=body.whiskey_id,
        source=body.source,
        source_display=body.source_display,
        score=body.score,
        max_score=body.max_score,
        review_year=body.review_year,
        review_text=body.review_text,
        url=body.url,
    )
    db.add(cs)
    db.commit()
    db.refresh(cs)

    normalized = (cs.score / cs.max_score * 100) if cs.max_score else 0
    return schemas.CriticScoreRead(
        id=cs.id,
        source=cs.source,
        source_display=cs.source_display,
        score=cs.score,
        max_score=cs.max_score,
        normalized_score=round(normalized, 1),
        review_year=cs.review_year,
        review_text=cs.review_text,
        url=cs.url,
    )


@router.get("/sources")
def list_sources():
    """List known critic sources."""
    return [
        {"key": k, "name": v}
        for k, v in KNOWN_SOURCES.items()
    ]
