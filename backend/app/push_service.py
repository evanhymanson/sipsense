"""Web Push delivery via VAPID (W3C Web Push standard).

Gracefully degrades if VAPID keys are not configured — logs a warning and skips.
Checks push preferences on EmailPreference before sending.
Marks subscriptions as inactive (410 Gone) when browsers revoke them.
"""

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_vapid_available = None  # None = not checked yet
_vapid_private_key = None
_vapid_claims = None


def _get_vapid():
    """Lazy-initialize VAPID config.  Returns (private_key, claims) or (None, None)."""
    global _vapid_available, _vapid_private_key, _vapid_claims
    if _vapid_available is False:
        return None, None
    if _vapid_available is True:
        return _vapid_private_key, _vapid_claims

    private_key = os.getenv("VAPID_PRIVATE_KEY")
    if not private_key:
        logger.warning("VAPID_PRIVATE_KEY not configured — push delivery disabled")
        _vapid_available = False
        return None, None

    try:
        from pywebpush import webpush  # noqa: F401 — verify import works
        _vapid_private_key = private_key
        _vapid_claims = {
            "sub": os.getenv("VAPID_CLAIMS_EMAIL", "mailto:noreply@sipsense.ai")
        }
        _vapid_available = True
        logger.info("VAPID push delivery enabled")
        return _vapid_private_key, _vapid_claims
    except Exception as e:
        logger.warning("Failed to initialize pywebpush: %s", e)
        _vapid_available = False
        return None, None


def send_push_to_user(
    user_id: str,
    title: str,
    body: str,
    url: str = "/alerts",
    icon: str = "/icons/icon-192.png",
    tag: str | None = None,
) -> int:
    """Send a push notification to ALL active subscriptions for a user.

    Returns number of successful sends.
    Marks invalid subscriptions as inactive (handles 410 Gone).
    """
    private_key, claims = _get_vapid()
    if private_key is None:
        env = os.getenv("SIPSENSE_ENV", "development").lower()
        if env == "development":
            logger.info(
                "PUSH (dev, not sent) → user=%s title=%r body=%r url=%s",
                user_id, title, body, url,
            )
        return 0

    from .database import SessionLocal
    from . import models

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": icon,
        "tag": tag or title,
    })

    db = SessionLocal()
    sent = 0
    try:
        subs = (
            db.query(models.PushSubscription)
            .filter(
                models.PushSubscription.user_id == user_id,
                models.PushSubscription.is_active == True,  # noqa: E712
            )
            .all()
        )
        for sub in subs:
            try:
                from pywebpush import webpush
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=private_key,
                    vapid_claims=claims,
                    ttl=86400,
                )
                sub.last_used_at = datetime.now(timezone.utc)
                sent += 1
            except Exception as exc:
                # 410 Gone = subscription revoked by browser — deactivate
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code in (404, 410):
                    logger.info("Push sub gone (%d) — deactivating sub %d", status_code, sub.id)
                    sub.is_active = False
                else:
                    logger.error("Push failed for sub %d (user=%s): %s", sub.id, user_id, exc)
        db.commit()
    finally:
        db.close()

    return sent


def send_push_notification(
    user_id: str,
    alert_type: str,
    **kwargs,
) -> bool:
    """Convenience wrapper — checks push preferences before sending.

    alert_type: 'social', 'price_drop', 'streak', 'weekly'
    Returns True if at least one push was delivered.
    """
    if not _should_push(user_id, alert_type):
        logger.info("User %s opted out of %s push notifications", user_id, alert_type)
        return False
    sent = send_push_to_user(user_id, **kwargs)
    return sent > 0


def _should_push(user_id: str, push_type: str) -> bool:
    """Check if user has opted into this push type."""
    from .database import SessionLocal
    from . import models

    db = SessionLocal()
    try:
        pref = (
            db.query(models.EmailPreference)
            .filter(models.EmailPreference.user_id == user_id)
            .first()
        )
        if not pref:
            return True  # No preferences row = all defaults (opted in)

        mapping = {
            "social": pref.push_social,
            "price_drop": pref.push_price_drop,
            "streak": pref.push_streak,
            "weekly": pref.push_weekly,
        }
        return mapping.get(push_type, True)
    finally:
        db.close()
