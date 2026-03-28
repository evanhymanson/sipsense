"""Community challenges — monthly goals for engagement.

GET  /challenges/         — list active challenges (with user progress if auth)
GET  /challenges/{slug}   — challenge detail + leaderboard
POST /challenges/{slug}/join — join a challenge
GET  /challenges/me       — user's joined challenges
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user, get_optional_user

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("/")
def list_challenges(
    current_user=Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """List active challenges.  Includes user progress if authenticated."""
    now = datetime.now(timezone.utc)
    challenges = (
        db.query(models.Challenge)
        .filter(
            models.Challenge.is_active == True,
            models.Challenge.starts_at <= now,
            models.Challenge.ends_at >= now,
        )
        .all()
    )

    # Look up user progress if authenticated
    user_progress = {}
    if current_user:
        progs = (
            db.query(models.UserChallengeProgress)
            .filter(models.UserChallengeProgress.user_id == current_user.username)
            .all()
        )
        user_progress = {p.challenge_id: p for p in progs}

    results = []
    for c in challenges:
        prog = user_progress.get(c.id)
        results.append({
            "id": c.id,
            "slug": c.slug,
            "title": c.title,
            "description": c.description,
            "challenge_type": c.challenge_type,
            "goal_count": c.goal_count,
            "image_emoji": c.image_emoji,
            "starts_at": c.starts_at.isoformat() if c.starts_at else None,
            "ends_at": c.ends_at.isoformat() if c.ends_at else None,
            "joined": prog is not None,
            "progress": prog.progress_count if prog else 0,
            "completed": prog.completed if prog else False,
        })

    return results


@router.get("/me")
def my_challenges(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List challenges the user has joined with progress."""
    progs = (
        db.query(models.UserChallengeProgress)
        .join(models.Challenge)
        .filter(models.UserChallengeProgress.user_id == current_user.username)
        .order_by(models.UserChallengeProgress.joined_at.desc())
        .all()
    )

    return [
        {
            "slug": p.challenge.slug,
            "title": p.challenge.title,
            "image_emoji": p.challenge.image_emoji,
            "goal_count": p.challenge.goal_count,
            "progress": p.progress_count,
            "completed": p.completed,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        }
        for p in progs
    ]


@router.get("/{slug}")
def get_challenge(
    slug: str,
    db: Session = Depends(get_db),
):
    """Challenge detail with leaderboard (top 10)."""
    challenge = (
        db.query(models.Challenge)
        .filter(models.Challenge.slug == slug)
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Leaderboard: top 10 by progress
    leaders = (
        db.query(
            models.UserChallengeProgress.user_id,
            models.UserChallengeProgress.progress_count,
            models.UserChallengeProgress.completed,
        )
        .filter(models.UserChallengeProgress.challenge_id == challenge.id)
        .order_by(
            models.UserChallengeProgress.completed.desc(),
            models.UserChallengeProgress.progress_count.desc(),
        )
        .limit(10)
        .all()
    )

    return {
        "id": challenge.id,
        "slug": challenge.slug,
        "title": challenge.title,
        "description": challenge.description,
        "challenge_type": challenge.challenge_type,
        "goal_count": challenge.goal_count,
        "image_emoji": challenge.image_emoji,
        "starts_at": challenge.starts_at.isoformat() if challenge.starts_at else None,
        "ends_at": challenge.ends_at.isoformat() if challenge.ends_at else None,
        "leaderboard": [
            {"username": l.user_id, "progress": l.progress_count, "completed": l.completed}
            for l in leaders
        ],
    }


@router.post("/{slug}/join")
def join_challenge(
    slug: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Join a challenge."""
    challenge = (
        db.query(models.Challenge)
        .filter(models.Challenge.slug == slug, models.Challenge.is_active == True)
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    existing = (
        db.query(models.UserChallengeProgress)
        .filter(
            models.UserChallengeProgress.user_id == current_user.username,
            models.UserChallengeProgress.challenge_id == challenge.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already joined this challenge")

    prog = models.UserChallengeProgress(
        user_id=current_user.username,
        challenge_id=challenge.id,
        progress_count=0,
    )
    db.add(prog)
    db.commit()

    return {"status": "joined", "challenge": challenge.title}
