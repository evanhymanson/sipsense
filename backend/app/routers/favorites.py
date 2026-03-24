from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..track import track_action
from ..analytics_constants import ACTION_FAVORITE, ACTION_UNFAVORITE

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.post("/{whiskey_id}", response_model=schemas.FavoriteRead, status_code=201)
def add_favorite(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    existing = db.query(models.UserFavorite).filter(
        and_(models.UserFavorite.user_id == user_id, models.UserFavorite.whiskey_id == whiskey_id)
    ).first()
    if existing:
        return existing

    fav = models.UserFavorite(user_id=user_id, whiskey_id=whiskey_id)
    db.add(fav)
    track_action(db, user_id, ACTION_FAVORITE, whiskey_id=whiskey_id)
    db.commit()
    db.refresh(fav)
    return fav


@router.delete("/{whiskey_id}", status_code=204)
def remove_favorite(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username
    fav = db.query(models.UserFavorite).filter(
        and_(models.UserFavorite.user_id == user_id, models.UserFavorite.whiskey_id == whiskey_id)
    ).first()
    if fav:
        db.delete(fav)
        track_action(db, current_user.username, ACTION_UNFAVORITE, whiskey_id=whiskey_id)
        db.commit()


@router.get("/me", response_model=list[schemas.WhiskeyRead])
def get_my_favorites(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username
    favs = db.query(models.UserFavorite).filter(models.UserFavorite.user_id == user_id).all()
    whiskey_ids = [f.whiskey_id for f in favs]
    if not whiskey_ids:
        return []
    return db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()


@router.get("/me/ids")
def get_my_favorite_ids(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username
    favs = db.query(models.UserFavorite).filter(models.UserFavorite.user_id == user_id).all()
    return {"ids": [f.whiskey_id for f in favs]}
