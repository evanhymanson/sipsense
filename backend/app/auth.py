"""
Authentication utilities: password hashing, JWT creation/verification, FastAPI dependencies.
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from . import models

# ── Config ────────────────────────────────────────────────────────────────

_ENV = os.getenv("SIPSENSE_ENV", "development").lower()
_raw_secret = os.getenv("JWT_SECRET_KEY", "")

if not _raw_secret:
    if _ENV == "production":
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    # Auto-generate an ephemeral secret for local dev (tokens won't survive restarts)
    import secrets as _secrets
    import logging as _logging
    _raw_secret = _secrets.token_urlsafe(64)
    _logging.getLogger(__name__).warning(
        "JWT_SECRET_KEY is not set — using auto-generated ephemeral secret. "
        "Set JWT_SECRET_KEY env var before deploying."
    )

SECRET_KEY = _raw_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# ── Password hashing ─────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ────────────────────────────────────────────────────────────

def create_access_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "exp": now + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
        "iat": now,
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the username from a valid access token, or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Accept tokens without type (backward compat) or with type="access"
        token_type = payload.get("type")
        if token_type is not None and token_type != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_refresh_token(token: str) -> str | None:
    """Returns the username from a valid refresh token, or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ── FastAPI dependencies ──────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency that extracts and validates the current user from a JWT Bearer token."""
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return user


def get_optional_user(
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Like get_current_user but returns None instead of 401 for unauthenticated requests.
    Useful for endpoints that work for both authenticated and anonymous users."""
    if token is None:
        return None
    username = decode_access_token(token)
    if username is None:
        return None
    return db.query(models.User).filter(models.User.username == username, models.User.is_active == True).first()


def require_premium(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency that requires the user to have an active premium subscription."""
    # Check if premium has expired
    if current_user.is_premium and current_user.premium_until:
        if current_user.premium_until < datetime.now(timezone.utc):
            current_user.is_premium = False
            db.commit()
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires SipSense Premium",
        )
    return current_user
