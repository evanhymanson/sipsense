"""
Auth Router — register, login, and current user info.

POST /auth/register  — create a new account
POST /auth/login     — authenticate and receive a JWT
GET  /auth/me        — get current user info (requires token)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_refresh_token, get_current_user,
)
from ..rate_limit import auth_rate_limit
from ..track import track_action
from ..analytics_constants import ACTION_REGISTER, ACTION_LOGIN

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=201)
def register(body: schemas.UserRegister, db: Session = Depends(get_db), _: None = Depends(auth_rate_limit)):
    # Check for existing username or email (generic message to prevent enumeration)
    if db.query(models.User).filter(models.User.username == body.username).first() or \
       db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already in use",
        )

    user = models.User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    track_action(db, user.username, ACTION_REGISTER)
    db.commit()
    token = create_access_token(user.username)
    refresh = create_refresh_token(user.username)
    return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=user.username)


@router.post("/login", response_model=schemas.TokenResponse)
def login(body: schemas.UserLogin, db: Session = Depends(get_db), _: None = Depends(auth_rate_limit)):
    user = db.query(models.User).filter(models.User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    track_action(db, user.username, ACTION_LOGIN)
    db.commit()
    token = create_access_token(user.username)
    refresh = create_refresh_token(user.username)
    return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=user.username)


class _RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(body: _RefreshRequest, db: Session = Depends(get_db)):
    username = decode_refresh_token(body.refresh_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    new_access = create_access_token(user.username)
    new_refresh = create_refresh_token(user.username)
    return schemas.TokenResponse(access_token=new_access, refresh_token=new_refresh, username=user.username)


@router.get("/me", response_model=schemas.UserRead)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user
