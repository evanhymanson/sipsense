"""
Lightweight request analytics middleware.

Captures method, path, user, response time, and status for every API request.
Writes to the analytics_events table via a background thread to avoid blocking responses.

Configurable via environment:
  ANALYTICS_ENABLED=true          (default true)
  ANALYTICS_SAMPLE_RATE=1.0       (0.0-1.0, default 1.0 = log everything)
  ANALYTICS_SALT=<random>         (for IP hashing, auto-generated if not set)
  ANALYTICS_SKIP_PATHS=/health,/uploads,/docs  (comma-separated prefixes to skip)
  ANALYTICS_RETENTION_DAYS=90     (auto-delete older events on startup)
"""

import hashlib
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import Request

from .auth import decode_access_token
from .database import SessionLocal

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("ANALYTICS_ENABLED", "true").lower() in ("true", "1", "yes")
_SAMPLE_RATE = float(os.getenv("ANALYTICS_SAMPLE_RATE", "1.0"))
_SALT = os.getenv("ANALYTICS_SALT", "sipsense-analytics-default-salt")
_SKIP_PREFIXES = tuple(
    p.strip()
    for p in os.getenv("ANALYTICS_SKIP_PATHS", "/health,/uploads,/docs,/openapi").split(",")
    if p.strip()
)
_RETENTION_DAYS = int(os.getenv("ANALYTICS_RETENTION_DAYS", "90"))

# Single-thread executor for non-blocking DB writes
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analytics")


def _hash_ip(ip: str) -> str:
    """SHA-256 hash of IP with salt, truncated to 16 chars."""
    return hashlib.sha256((_SALT + ip).encode()).hexdigest()[:16]


def _write_event(event_data: dict):
    """Write an analytics event to the DB (runs in background thread)."""
    from . import models  # deferred to avoid circular imports

    db = SessionLocal()
    try:
        event = models.AnalyticsEvent(**event_data)
        db.add(event)
        db.commit()
    except Exception:
        logger.debug("Failed to write analytics event", exc_info=True)
        db.rollback()
    finally:
        db.close()


async def analytics_middleware(request: Request, call_next):
    """ASGI middleware that logs every API request with timing and user info."""
    if not _ENABLED:
        return await call_next(request)

    path = request.url.path

    # Skip non-API paths
    if path.startswith(_SKIP_PREFIXES):
        return await call_next(request)

    # Sampling
    if _SAMPLE_RATE < 1.0 and random.random() > _SAMPLE_RATE:
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Extract user from JWT (cheap decode, no DB hit)
    user_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        user_id = decode_access_token(auth_header[7:])

    # Hash IP for privacy
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = _hash_ip(client_ip)

    # Session hash: IP + User-Agent for approximate anonymous session grouping
    user_agent = request.headers.get("user-agent", "")
    session_hash = hashlib.sha256(
        (ip_hash + user_agent).encode()
    ).hexdigest()[:16]

    # Get the route pattern (e.g., /whiskeys/{whiskey_id}) for grouping
    route_pattern = None
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        route_pattern = route.path

    event_data = {
        "user_id": user_id,
        "ip_hash": ip_hash,
        "session_hash": session_hash,
        "method": request.method,
        "path": path[:500],
        "route_pattern": route_pattern[:200] if route_pattern else None,
        "status_code": response.status_code,
        "response_time_ms": elapsed_ms,
        "user_agent": user_agent[:500] if user_agent else None,
        "referrer": (request.headers.get("referer") or "")[:500] or None,
    }

    # Fire-and-forget write in background thread
    _executor.submit(_write_event, event_data)

    return response


def cleanup_old_events():
    """Delete analytics events older than the retention period. Call on startup."""
    from . import models

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
        deleted = db.query(models.AnalyticsEvent).filter(
            models.AnalyticsEvent.timestamp < cutoff
        ).delete()
        db.commit()
        if deleted:
            logger.info("Cleaned up %d analytics events older than %d days", deleted, _RETENTION_DAYS)
    except Exception:
        logger.debug("Analytics cleanup failed", exc_info=True)
        db.rollback()
    finally:
        db.close()
