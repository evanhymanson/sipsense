"""Email preference management.

GET  /email-preferences/           — get preferences
PUT  /email-preferences/           — update preferences
GET  /email-preferences/unsubscribe — one-click unsubscribe (no auth)
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/email-preferences", tags=["email"])


@router.get("/", response_model=schemas.EmailPreferenceRead)
def get_preferences(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user's email preferences.  Creates defaults if none exist."""
    pref = (
        db.query(models.EmailPreference)
        .filter(models.EmailPreference.user_id == current_user.username)
        .first()
    )
    if not pref:
        pref = models.EmailPreference(user_id=current_user.username)
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/", response_model=schemas.EmailPreferenceRead)
def update_preferences(
    body: schemas.EmailPreferenceUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update email preferences."""
    pref = (
        db.query(models.EmailPreference)
        .filter(models.EmailPreference.user_id == current_user.username)
        .first()
    )
    if not pref:
        pref = models.EmailPreference(user_id=current_user.username)
        db.add(pref)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pref, field, value)

    db.commit()
    db.refresh(pref)
    return pref


@router.get("/unsubscribe")
def unsubscribe(
    token: str = Query(...),
    email_type: str = Query(...),
    db: Session = Depends(get_db),
):
    """One-click unsubscribe via signed token.  No auth required."""
    from jose import jwt, JWTError
    secret = os.getenv("JWT_SECRET_KEY", "")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    pref = (
        db.query(models.EmailPreference)
        .filter(models.EmailPreference.user_id == user_id)
        .first()
    )
    if not pref:
        pref = models.EmailPreference(user_id=user_id)
        db.add(pref)

    valid_types = {"weekly_digest", "re_engagement", "onboarding_drip", "marketing"}
    if email_type in valid_types:
        setattr(pref, email_type, False)
        db.commit()

    return {"status": "unsubscribed", "email_type": email_type}
