"""Scheduled email job implementations.

Each function is called by APScheduler on a cron schedule.
Uses SessionLocal() for DB access (separate from web request sessions).
Handles exceptions per-user so one failure doesn't stop others.
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import func as sqlfunc

logger = logging.getLogger(__name__)


def send_weekly_digests():
    """Send weekly digest to all opted-in users.  Runs Sunday 10am UTC."""
    from .database import SessionLocal
    from . import models
    from .email_service import send_email
    from .email_templates import weekly_digest_email

    logger.info("Starting weekly digest job")
    db = SessionLocal()
    sent = 0
    try:
        users = db.query(models.User).filter(models.User.is_active == True).all()
        for user in users:
            try:
                # Check preference
                pref = (
                    db.query(models.EmailPreference)
                    .filter(models.EmailPreference.user_id == user.username)
                    .first()
                )
                if pref and not pref.weekly_digest:
                    continue

                # Build digest data
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                checkins = (
                    db.query(sqlfunc.count(models.UserRating.id))
                    .filter(
                        models.UserRating.user_id == user.username,
                        models.UserRating.created_at >= week_ago,
                    )
                    .scalar() or 0
                )

                # Get streak
                streak = (
                    db.query(models.UserStreak)
                    .filter(models.UserStreak.user_id == user.username)
                    .first()
                )

                # Get trending bottle
                trending = (
                    db.query(models.Whiskey.name)
                    .join(models.UserRating, models.UserRating.whiskey_id == models.Whiskey.id)
                    .filter(models.UserRating.created_at >= week_ago)
                    .group_by(models.Whiskey.name)
                    .order_by(sqlfunc.count(models.UserRating.id).desc())
                    .first()
                )

                data = {
                    "checkins_this_week": checkins,
                    "current_streak": streak.current_streak if streak else 0,
                    "trending_name": trending[0] if trending else None,
                }

                # Skip if nothing to report
                if checkins == 0 and not (streak and streak.current_streak > 0):
                    continue

                subject, html, text = weekly_digest_email(user.username, data)
                if send_email(user.email, subject, html, text,
                              user_id=user.username, email_type="weekly_digest"):
                    sent += 1
            except Exception:
                logger.exception("Failed to send digest to %s", user.username)
    finally:
        db.close()
    logger.info("Weekly digest: sent %d emails", sent)


def send_re_engagement_emails():
    """Send re-engagement to users inactive 14+ days.  Runs daily 2pm UTC."""
    from .database import SessionLocal
    from . import models
    from .email_service import send_email
    from .email_templates import re_engagement_email

    logger.info("Starting re-engagement job")
    db = SessionLocal()
    sent = 0
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Find users with no recent activity
        active_users = (
            db.query(models.UserAction.user_id)
            .filter(models.UserAction.timestamp >= cutoff)
            .distinct()
            .subquery()
        )

        inactive_users = (
            db.query(models.User)
            .filter(
                models.User.is_active == True,
                ~models.User.username.in_(
                    db.query(active_users.c.user_id)
                ),
            )
            .all()
        )

        for user in inactive_users:
            try:
                # Check preference
                pref = (
                    db.query(models.EmailPreference)
                    .filter(models.EmailPreference.user_id == user.username)
                    .first()
                )
                if pref and not pref.re_engagement:
                    continue

                # Check if we've sent re-engagement in last 30 days
                recent_email = (
                    db.query(models.EmailLog)
                    .filter(
                        models.EmailLog.user_id == user.username,
                        models.EmailLog.email_type == "re_engagement",
                        models.EmailLog.created_at >= thirty_days_ago,
                    )
                    .first()
                )
                if recent_email:
                    continue

                # Count new whiskeys added recently
                new_count = (
                    db.query(sqlfunc.count(models.Whiskey.id))
                    .filter(models.Whiskey.created_at >= cutoff)
                    .scalar() or 0
                )

                data = {
                    "new_whiskeys_added": new_count,
                    "daily_discovery": "today's featured whiskey",
                }

                subject, html, text = re_engagement_email(user.username, data)
                if send_email(user.email, subject, html, text,
                              user_id=user.username, email_type="re_engagement"):
                    sent += 1
            except Exception:
                logger.exception("Failed re-engagement for %s", user.username)
    finally:
        db.close()
    logger.info("Re-engagement: sent %d emails", sent)


def send_drip_emails():
    """Send onboarding drip at day 1, 3, 7, 14 after registration.  Runs daily 11am UTC."""
    from .database import SessionLocal
    from . import models
    from .email_service import send_email
    from .email_templates import drip_email

    logger.info("Starting drip email job")
    db = SessionLocal()
    sent = 0
    try:
        now = datetime.now(timezone.utc)
        for day_offset in [1, 3, 7, 14]:
            target_date = (now - timedelta(days=day_offset)).date()

            # Find users registered on target_date
            users = (
                db.query(models.User)
                .filter(models.User.is_active == True)
                .all()
            )

            for user in users:
                try:
                    # Check registration date
                    if user.created_at is None:
                        continue
                    reg_date = user.created_at
                    if hasattr(reg_date, 'date'):
                        reg_date = reg_date.date()
                    if reg_date != target_date:
                        continue

                    # Check preference
                    pref = (
                        db.query(models.EmailPreference)
                        .filter(models.EmailPreference.user_id == user.username)
                        .first()
                    )
                    if pref and not pref.onboarding_drip:
                        continue

                    # Check if already sent this drip
                    drip_type = f"drip_day{day_offset}"
                    existing = (
                        db.query(models.EmailLog)
                        .filter(
                            models.EmailLog.user_id == user.username,
                            models.EmailLog.email_type == drip_type,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    subject, html, text = drip_email(user.username, day_offset)
                    if send_email(user.email, subject, html, text,
                                  user_id=user.username, email_type=drip_type):
                        sent += 1
                except Exception:
                    logger.exception("Failed drip for %s (day %d)", user.username, day_offset)
    finally:
        db.close()
    logger.info("Drip emails: sent %d emails", sent)
