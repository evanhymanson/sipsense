"""
Guided Tasting Journeys — structured multi-step whiskey exploration paths.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..auth import get_current_user, get_optional_user

router = APIRouter(prefix="/journeys", tags=["journeys"])


@router.get("/")
def list_journeys(
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """List all available journeys with user progress if logged in."""
    journeys = db.query(models.Journey).all()

    progress_map = {}
    if current_user:
        rows = (
            db.query(models.UserJourneyProgress)
            .filter(models.UserJourneyProgress.user_id == current_user.username)
            .all()
        )
        progress_map = {p.journey_id: p for p in rows}

    result = []
    for j in journeys:
        p = progress_map.get(j.id)
        result.append({
            "id": j.id,
            "slug": j.slug,
            "title": j.title,
            "description": j.description,
            "category": j.category,
            "difficulty": j.difficulty,
            "bottle_count": j.bottle_count,
            "image_emoji": j.image_emoji,
            "user_progress": {
                "current_step": p.current_step,
                "started_at": p.started_at.isoformat() if p.started_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            } if p else None,
        })

    return result


@router.get("/me")
def my_journeys(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's active and completed journeys."""
    rows = (
        db.query(models.UserJourneyProgress)
        .filter(models.UserJourneyProgress.user_id == current_user.username)
        .options(joinedload(models.UserJourneyProgress.journey))
        .all()
    )

    active, completed = [], []
    for p in rows:
        item = {
            "journey": {
                "id": p.journey.id,
                "slug": p.journey.slug,
                "title": p.journey.title,
                "bottle_count": p.journey.bottle_count,
                "image_emoji": p.journey.image_emoji,
            },
            "current_step": p.current_step,
            "started_at": p.started_at.isoformat() if p.started_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        if p.completed_at:
            completed.append(item)
        else:
            active.append(item)

    return {"active": active, "completed": completed}


@router.get("/{slug}")
def get_journey(
    slug: str,
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get journey details with all steps and whiskey info."""
    journey = (
        db.query(models.Journey)
        .filter(models.Journey.slug == slug)
        .options(joinedload(models.Journey.steps))
        .first()
    )
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    whiskey_ids = [s.whiskey_id for s in journey.steps]
    whiskeys = (
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()
        if whiskey_ids else []
    )
    whiskey_map = {w.id: w for w in whiskeys}

    progress = None
    if current_user:
        p = (
            db.query(models.UserJourneyProgress)
            .filter(
                models.UserJourneyProgress.user_id == current_user.username,
                models.UserJourneyProgress.journey_id == journey.id,
            )
            .first()
        )
        if p:
            progress = {
                "current_step": p.current_step,
                "started_at": p.started_at.isoformat() if p.started_at else None,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }

    steps = []
    for s in sorted(journey.steps, key=lambda x: x.step_number):
        w = whiskey_map.get(s.whiskey_id)
        steps.append({
            "step_number": s.step_number,
            "lesson_text": s.lesson_text,
            "tasting_prompt": s.tasting_prompt,
            "whiskey": {
                "id": w.id,
                "name": w.name,
                "distillery": w.distillery,
                "category": w.category,
                "region": w.region,
                "abv": w.abv,
                "price_usd": w.price_usd,
                "rating_avg": w.rating_avg,
                "flavor_profile": w.flavor_profile,
            } if w else None,
        })

    return {
        "id": journey.id,
        "slug": journey.slug,
        "title": journey.title,
        "description": journey.description,
        "category": journey.category,
        "difficulty": journey.difficulty,
        "bottle_count": journey.bottle_count,
        "image_emoji": journey.image_emoji,
        "steps": steps,
        "user_progress": progress,
    }


@router.post("/{slug}/start")
def start_journey(
    slug: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a journey (creates progress record at step 1)."""
    journey = db.query(models.Journey).filter(models.Journey.slug == slug).first()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    existing = (
        db.query(models.UserJourneyProgress)
        .filter(
            models.UserJourneyProgress.user_id == current_user.username,
            models.UserJourneyProgress.journey_id == journey.id,
        )
        .first()
    )
    if existing:
        return {"status": "already_started", "current_step": existing.current_step}

    progress = models.UserJourneyProgress(
        user_id=current_user.username,
        journey_id=journey.id,
        current_step=1,
    )
    db.add(progress)
    db.commit()
    return {"status": "started", "current_step": 1}


@router.post("/{slug}/steps/{step_number}/complete")
def complete_step(
    slug: str,
    step_number: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a journey step as completed, advance to next step."""
    journey = db.query(models.Journey).filter(models.Journey.slug == slug).first()
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")

    progress = (
        db.query(models.UserJourneyProgress)
        .filter(
            models.UserJourneyProgress.user_id == current_user.username,
            models.UserJourneyProgress.journey_id == journey.id,
        )
        .first()
    )
    if not progress:
        raise HTTPException(status_code=400, detail="Journey not started yet")

    if step_number != progress.current_step:
        raise HTTPException(
            status_code=400,
            detail=f"You're on step {progress.current_step}, not {step_number}",
        )

    if step_number >= journey.bottle_count:
        progress.current_step = journey.bottle_count
        progress.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "journey_complete", "current_step": journey.bottle_count}
    else:
        progress.current_step = step_number + 1
        db.commit()
        return {"status": "step_complete", "current_step": progress.current_step}
