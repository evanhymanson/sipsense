"""
Lightweight analytics tracking helper.

Usage in any router:
    from ..track import track_action
    from ..analytics_constants import ACTION_WHISKEY_VIEW

    track_action(db, current_user.username, ACTION_WHISKEY_VIEW,
                 whiskey_id=42, detail={"whiskey_name": "Ardbeg 10"})
"""

import json
import logging
from . import models

logger = logging.getLogger(__name__)


def track_action(
    db,
    user_id: str,
    action: str,
    *,
    whiskey_id: int | None = None,
    category: str | None = None,
    detail: dict | None = None,
):
    """Record a user action. Fails silently -- analytics should never break the app."""
    try:
        event = models.UserAction(
            user_id=user_id,
            action=action,
            whiskey_id=whiskey_id,
            category=category,
            detail_json=json.dumps(detail) if detail else "{}",
        )
        db.add(event)
        # Don't commit here — let the router's existing commit handle it.
        # The event will be committed atomically with the business transaction.
    except Exception:
        logger.exception("Failed to track action %s for user %s", action, user_id)
