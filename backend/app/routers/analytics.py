"""
Analytics dashboard API — admin-only endpoints for usage metrics.

GET /analytics/overview         — DAU, WAU, MAU, totals, error rate
GET /analytics/funnel           — registration -> quiz -> rating -> favorite -> return
GET /analytics/top-whiskeys     — most viewed/rated in a time window
GET /analytics/feature-adoption — distinct users per action type
GET /analytics/performance      — API response time percentiles
POST /analytics/track           — receive frontend page view events (no auth required)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, distinct, case, text
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_ADMIN_USERS = {
    u.strip() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()
}


def _require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.username not in _ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Overview ─────────────────────────────────────────────────────────────


@router.get("/overview")
def get_overview(
    _admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Key metrics: DAU, WAU, MAU, totals, avg response time, error rate."""
    now = datetime.now(timezone.utc)

    def _active_users(days):
        return (
            db.query(func.count(distinct(models.AnalyticsEvent.user_id)))
            .filter(
                models.AnalyticsEvent.user_id.isnot(None),
                models.AnalyticsEvent.timestamp >= now - timedelta(days=days),
            )
            .scalar() or 0
        )

    dau = _active_users(1)
    wau = _active_users(7)
    mau = _active_users(30)

    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_whiskeys = db.query(func.count(models.Whiskey.id)).scalar() or 0
    total_ratings = db.query(func.count(models.UserRating.id)).scalar() or 0
    total_favorites = db.query(func.count(models.UserFavorite.id)).scalar() or 0

    # Today's requests and performance
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_stats = (
        db.query(
            func.count(models.AnalyticsEvent.id),
            func.avg(models.AnalyticsEvent.response_time_ms),
        )
        .filter(models.AnalyticsEvent.timestamp >= today_start)
        .first()
    )
    requests_today = today_stats[0] or 0
    avg_response_ms = round(float(today_stats[1]), 1) if today_stats[1] else 0

    # Error rate (4xx + 5xx)
    error_count = (
        db.query(func.count(models.AnalyticsEvent.id))
        .filter(
            models.AnalyticsEvent.timestamp >= today_start,
            models.AnalyticsEvent.status_code >= 400,
        )
        .scalar() or 0
    )
    error_rate = round(error_count / requests_today * 100, 2) if requests_today else 0

    return {
        "dau": dau,
        "wau": wau,
        "mau": mau,
        "total_users": total_users,
        "total_whiskeys": total_whiskeys,
        "total_ratings": total_ratings,
        "total_favorites": total_favorites,
        "requests_today": requests_today,
        "avg_response_time_ms": avg_response_ms,
        "error_rate_pct": error_rate,
    }


# ── Funnel ───────────────────────────────────────────────────────────────


@router.get("/funnel")
def get_funnel(
    _admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Conversion funnel: registered -> quiz -> first rating -> first favorite -> return -> premium."""
    registered = db.query(func.count(models.User.id)).scalar() or 0

    quiz_completed = (
        db.query(func.count(models.User.id))
        .filter(models.User.quiz_completed == True)
        .scalar() or 0
    )

    users_with_rating = (
        db.query(func.count(distinct(models.UserRating.user_id))).scalar() or 0
    )

    users_with_favorite = (
        db.query(func.count(distinct(models.UserFavorite.user_id))).scalar() or 0
    )

    # Return visitors: users with analytics events on 2+ distinct days
    now = datetime.now(timezone.utc)
    return_visitors = (
        db.query(func.count(distinct(models.UserAction.user_id)))
        .filter(models.UserAction.action == "login")
        .scalar() or 0
    )

    premium = (
        db.query(func.count(models.User.id))
        .filter(models.User.is_premium == True)
        .scalar() or 0
    )

    return {
        "registered": registered,
        "quiz_completed": quiz_completed,
        "first_rating": users_with_rating,
        "first_favorite": users_with_favorite,
        "return_login": return_visitors,
        "premium": premium,
    }


# ── Top Whiskeys ─────────────────────────────────────────────────────────


@router.get("/top-whiskeys")
def get_top_whiskeys(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
    _admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Most viewed and most rated whiskeys in a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Most viewed (from UserAction tracking)
    most_viewed = (
        db.query(
            models.UserAction.whiskey_id,
            func.count(models.UserAction.id).label("views"),
        )
        .filter(
            models.UserAction.action == "whiskey_view",
            models.UserAction.whiskey_id.isnot(None),
            models.UserAction.timestamp >= cutoff,
        )
        .group_by(models.UserAction.whiskey_id)
        .order_by(func.count(models.UserAction.id).desc())
        .limit(limit)
        .all()
    )

    # Enrich with whiskey names
    viewed_ids = [row[0] for row in most_viewed]
    whiskey_map = {}
    if viewed_ids:
        whiskeys = db.query(models.Whiskey).filter(models.Whiskey.id.in_(viewed_ids)).all()
        whiskey_map = {w.id: w for w in whiskeys}

    top_viewed = [
        {
            "whiskey_id": wid,
            "name": whiskey_map[wid].name if wid in whiskey_map else "Unknown",
            "category": whiskey_map[wid].category if wid in whiskey_map else None,
            "views": views,
        }
        for wid, views in most_viewed
    ]

    # Most rated in period
    most_rated = (
        db.query(
            models.UserRating.whiskey_id,
            func.count(models.UserRating.id).label("ratings"),
        )
        .filter(models.UserRating.created_at >= cutoff)
        .group_by(models.UserRating.whiskey_id)
        .order_by(func.count(models.UserRating.id).desc())
        .limit(limit)
        .all()
    )

    rated_ids = [row[0] for row in most_rated]
    if rated_ids:
        whiskeys2 = db.query(models.Whiskey).filter(models.Whiskey.id.in_(rated_ids)).all()
        whiskey_map.update({w.id: w for w in whiskeys2})

    top_rated = [
        {
            "whiskey_id": wid,
            "name": whiskey_map[wid].name if wid in whiskey_map else "Unknown",
            "category": whiskey_map[wid].category if wid in whiskey_map else None,
            "ratings": cnt,
        }
        for wid, cnt in most_rated
    ]

    return {"most_viewed": top_viewed, "most_rated": top_rated}


# ── Feature Adoption ─────────────────────────────────────────────────────


@router.get("/feature-adoption")
def get_feature_adoption(
    days: int = Query(30, ge=1, le=365),
    _admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Distinct users and total events per action type in a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(
            models.UserAction.action,
            func.count(models.UserAction.id).label("total"),
            func.count(distinct(models.UserAction.user_id)).label("unique_users"),
        )
        .filter(models.UserAction.timestamp >= cutoff)
        .group_by(models.UserAction.action)
        .order_by(func.count(models.UserAction.id).desc())
        .all()
    )

    return [
        {"action": action, "total": total, "unique_users": unique_users}
        for action, total, unique_users in rows
    ]


# ── Performance ──────────────────────────────────────────────────────────


@router.get("/performance")
def get_performance(
    days: int = Query(7, ge=1, le=90),
    _admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """API response time stats over a time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    base = db.query(models.AnalyticsEvent.response_time_ms).filter(
        models.AnalyticsEvent.timestamp >= cutoff,
        models.AnalyticsEvent.response_time_ms.isnot(None),
    )

    total = base.count()
    if total == 0:
        return {"total_requests": 0, "p50": 0, "p95": 0, "p99": 0, "avg": 0}

    avg_ms = (
        db.query(func.avg(models.AnalyticsEvent.response_time_ms))
        .filter(
            models.AnalyticsEvent.timestamp >= cutoff,
            models.AnalyticsEvent.response_time_ms.isnot(None),
        )
        .scalar() or 0
    )

    # Percentile approximation via sorting + offset
    def _percentile(pct):
        offset = int(total * pct)
        row = (
            base.order_by(models.AnalyticsEvent.response_time_ms.asc())
            .offset(offset)
            .limit(1)
            .first()
        )
        return row[0] if row else 0

    p50 = _percentile(0.50)
    p95 = _percentile(0.95)
    p99 = _percentile(0.99)

    # Slowest endpoints
    slow_endpoints = (
        db.query(
            models.AnalyticsEvent.route_pattern,
            func.avg(models.AnalyticsEvent.response_time_ms).label("avg_ms"),
            func.count(models.AnalyticsEvent.id).label("count"),
        )
        .filter(
            models.AnalyticsEvent.timestamp >= cutoff,
            models.AnalyticsEvent.route_pattern.isnot(None),
            models.AnalyticsEvent.response_time_ms.isnot(None),
        )
        .group_by(models.AnalyticsEvent.route_pattern)
        .having(func.count(models.AnalyticsEvent.id) >= 5)
        .order_by(func.avg(models.AnalyticsEvent.response_time_ms).desc())
        .limit(10)
        .all()
    )

    return {
        "total_requests": total,
        "avg_ms": round(float(avg_ms), 1),
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "slowest_endpoints": [
            {"route": route, "avg_ms": round(float(avg), 1), "count": cnt}
            for route, avg, cnt in slow_endpoints
        ],
    }


# ── Frontend Event Tracking ──────────────────────────────────────────────

# Rate limit for anonymous tracking endpoint
_TRACK_RATE: dict[str, list[float]] = {}
_TRACK_LAST_CLEANUP = 0.0
_TRACK_CLEANUP_INTERVAL = 300  # 5 minutes
_TRACK_MAX_IPS = 5000

@router.post("/track")
async def track_frontend_event(request: Request, db: Session = Depends(get_db)):
    """Receive frontend analytics events (page views, time-on-page).
    No auth required so it works for the onboarding page."""
    import time
    global _TRACK_LAST_CLEANUP

    # Simple rate limit: 60 events/minute per IP
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = now - 60

    # Periodic cleanup: evict stale IPs and cap total entries
    if now - _TRACK_LAST_CLEANUP > _TRACK_CLEANUP_INTERVAL:
        stale = [ip for ip, ts in _TRACK_RATE.items() if not ts or ts[-1] < window]
        for ip in stale:
            del _TRACK_RATE[ip]
        if len(_TRACK_RATE) > _TRACK_MAX_IPS:
            by_recency = sorted(_TRACK_RATE, key=lambda ip: _TRACK_RATE[ip][-1] if _TRACK_RATE[ip] else 0)
            for ip in by_recency[:len(_TRACK_RATE) - _TRACK_MAX_IPS]:
                del _TRACK_RATE[ip]
        _TRACK_LAST_CLEANUP = now

    hits = _TRACK_RATE.get(client_ip, [])
    hits = [t for t in hits if t > window]
    if len(hits) >= 60:
        return {"status": "rate_limited"}
    hits.append(now)
    _TRACK_RATE[client_ip] = hits

    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid"}

    event_type = body.get("event", "")
    path = str(body.get("path", ""))[:500]

    if event_type == "page_view":
        event = models.AnalyticsEvent(
            method="PAGE",
            path=path,
            route_pattern=path,
            status_code=200,
            response_time_ms=0,
            referrer=str(body.get("referrer", ""))[:500] or None,
            user_agent=request.headers.get("user-agent", "")[:500],
        )
        # Try to extract user from auth header
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            from ..auth import decode_access_token
            event.user_id = decode_access_token(auth[7:])
        db.add(event)
        db.commit()

    elif event_type == "time_on_page":
        # Log as a special analytics event
        seconds = body.get("data", {}).get("seconds", 0)
        if isinstance(seconds, (int, float)) and 1 < seconds < 3600:
            event = models.AnalyticsEvent(
                method="TIME",
                path=path,
                route_pattern=path,
                status_code=200,
                response_time_ms=int(seconds * 1000),
            )
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                from ..auth import decode_access_token
                event.user_id = decode_access_token(auth[7:])
            db.add(event)
            db.commit()

    return {"status": "ok"}
