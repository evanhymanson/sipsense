"""
Auth Router — register, login, password reset, and current user info.

POST /auth/register         — create a new account
POST /auth/login            — authenticate and receive a JWT
POST /auth/forgot-password  — request password reset email
POST /auth/reset-password   — reset password with token
GET  /auth/me               — get current user info (requires token)
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenResponse, status_code=201)
def register(body: schemas.UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db), _: None = Depends(auth_rate_limit)):
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

    # Create default email preferences (all opted in)
    db.add(models.EmailPreference(user_id=user.username))
    db.commit()

    track_action(db, user.username, ACTION_REGISTER)
    db.commit()

    # Send welcome email in background
    try:
        from ..email_service import send_email
        from ..email_templates import welcome_email
        subject, html, text = welcome_email(user.username)
        background_tasks.add_task(send_email, user.email, subject, html, text, user.username, "welcome")
    except Exception:
        logger.debug("Welcome email skipped (SES not configured)")

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
    refresh = create_refresh_token(user.username, remember_me=body.remember_me)
    return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=user.username)


class _RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=schemas.TokenResponse)
def refresh_token(body: _RefreshRequest, db: Session = Depends(get_db)):
    result = decode_refresh_token(body.refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    username, remember_me = result
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    new_access = create_access_token(user.username)
    new_refresh = create_refresh_token(user.username, remember_me=remember_me)
    return schemas.TokenResponse(access_token=new_access, refresh_token=new_refresh, username=user.username)


@router.get("/me", response_model=schemas.UserRead)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(
    body: schemas.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit),
):
    """Request a password reset email. Always returns 200 to prevent enumeration."""
    import os
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if user:
        # Generate token and store hash
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        reset = models.PasswordResetToken(
            user_id=user.username,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset)
        db.commit()

        # Send reset email
        frontend_url = os.getenv("FRONTEND_URL", "https://sipsense.ai")
        reset_url = f"{frontend_url}/onboarding?reset_token={token}"
        try:
            from ..email_service import send_email
            from ..email_templates import password_reset_email
            subject, html, text = password_reset_email(user.username, reset_url)
            background_tasks.add_task(send_email, user.email, subject, html, text, user.username, "reset")
        except Exception:
            logger.debug("Reset email skipped (SES not configured)")

    return {"status": "If an account with that email exists, we've sent a reset link."}


@router.post("/reset-password")
def reset_password(body: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a token from the forgot-password email."""
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    reset = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token_hash == token_hash,
            models.PasswordResetToken.used == False,
        )
        .first()
    )
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if reset.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    # Update password
    user = db.query(models.User).filter(models.User.username == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    user.hashed_password = hash_password(body.new_password)
    reset.used = True
    db.commit()

    return {"status": "Password reset successfully"}


# ── Gap 6: Social OAuth ──────────────────────────────────────────────────────


@router.post("/oauth/google", response_model=schemas.TokenResponse)
def google_oauth(body: schemas.OAuthLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate via Google OAuth. Expects the ID token from Google Sign-In.
    Creates an account on first login; returns JWT on subsequent logins.
    """
    import os
    if not body.token:
        raise HTTPException(status_code=400, detail="OAuth token is required")

    # Verify the Google ID token server-side
    google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    if google_client_id:
        try:
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests
            idinfo = google_id_token.verify_oauth2_token(
                body.token, google_requests.Request(), google_client_id
            )
            # Override client-provided fields with verified data
            verified_email = idinfo.get("email")
            verified_sub = idinfo.get("sub")
            if verified_email:
                body.email = verified_email
            if verified_sub:
                body.oauth_id = verified_sub
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid or expired Google token")
    else:
        logger.warning("GOOGLE_OAUTH_CLIENT_ID not set — skipping token verification")

    # Check for existing OAuth user
    existing = (
        db.query(models.User)
        .filter(models.User.oauth_provider == "google", models.User.oauth_id == body.oauth_id)
        .first()
    )
    if existing:
        token = create_access_token(existing.username)
        refresh = create_refresh_token(existing.username)
        return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=existing.username)

    # Check if email already registered with password
    email_user = db.query(models.User).filter(models.User.email == body.email).first()
    if email_user:
        # Link OAuth to existing account
        email_user.oauth_provider = "google"
        email_user.oauth_id = body.oauth_id
        db.commit()
        token = create_access_token(email_user.username)
        refresh = create_refresh_token(email_user.username)
        return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=email_user.username)

    # Create new user from OAuth
    username = body.username or body.email.split("@")[0]
    # Ensure unique username
    base_username = username
    counter = 1
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    user = models.User(
        username=username,
        email=body.email,
        hashed_password="",  # No password for OAuth users
        oauth_provider="google",
        oauth_id=body.oauth_id,
    )
    db.add(user)
    db.commit()

    # Create default email preferences
    db.add(models.EmailPreference(user_id=user.username))
    db.commit()

    track_action(db, user.username, ACTION_REGISTER, detail={"method": "google_oauth"})
    db.commit()

    token = create_access_token(user.username)
    refresh = create_refresh_token(user.username)
    return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=user.username)


@router.post("/oauth/apple", response_model=schemas.TokenResponse)
def apple_oauth(body: schemas.OAuthLoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate via Apple Sign-In. Same flow as Google OAuth.
    """
    if not body.token:
        raise HTTPException(status_code=400, detail="OAuth token is required")

    existing = (
        db.query(models.User)
        .filter(models.User.oauth_provider == "apple", models.User.oauth_id == body.oauth_id)
        .first()
    )
    if existing:
        token = create_access_token(existing.username)
        refresh = create_refresh_token(existing.username)
        return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=existing.username)

    email_user = db.query(models.User).filter(models.User.email == body.email).first() if body.email else None
    if email_user:
        email_user.oauth_provider = "apple"
        email_user.oauth_id = body.oauth_id
        db.commit()
        token = create_access_token(email_user.username)
        refresh = create_refresh_token(email_user.username)
        return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=email_user.username)

    username = body.username or (body.email.split("@")[0] if body.email else f"user_{body.oauth_id[:8]}")
    base_username = username
    counter = 1
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{base_username}{counter}"
        counter += 1

    user = models.User(
        username=username,
        email=body.email or f"{username}@private.apple.com",
        hashed_password="",
        oauth_provider="apple",
        oauth_id=body.oauth_id,
    )
    db.add(user)
    db.commit()

    db.add(models.EmailPreference(user_id=user.username))
    db.commit()

    track_action(db, user.username, ACTION_REGISTER, detail={"method": "apple_oauth"})
    db.commit()

    token = create_access_token(user.username)
    refresh = create_refresh_token(user.username)
    return schemas.TokenResponse(access_token=token, refresh_token=refresh, username=user.username)
