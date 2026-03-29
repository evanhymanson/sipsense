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

                # Gap 5: Personalized recommendation based on taste profile
                personal_rec = None
                try:
                    user_ratings = (
                        db.query(models.UserRating)
                        .filter(models.UserRating.user_id == user.username)
                        .order_by(models.UserRating.score.desc())
                        .limit(5)
                        .all()
                    )
                    if user_ratings:
                        rated_ids = [r.whiskey_id for r in user_ratings]
                        top_rated = db.query(models.Whiskey).filter(
                            models.Whiskey.id == user_ratings[0].whiskey_id
                        ).first()
                        if top_rated and top_rated.category:
                            rec = (
                                db.query(models.Whiskey)
                                .filter(
                                    models.Whiskey.category.ilike(f"%{top_rated.category}%"),
                                    models.Whiskey.id.notin_(rated_ids),
                                    models.Whiskey.rating_avg >= 3.5,
                                )
                                .order_by(models.Whiskey.rating_avg.desc())
                                .first()
                            )
                            if rec:
                                personal_rec = {
                                    "name": rec.name,
                                    "category": rec.category,
                                    "reason": f"Because you loved {top_rated.name}",
                                }
                except Exception:
                    pass

                data = {
                    "checkins_this_week": checkins,
                    "current_streak": streak.current_streak if streak else 0,
                    "trending_name": trending[0] if trending else None,
                    "personal_recommendation": personal_rec,
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


def send_streak_push_reminders():
    """Send daily push to users with active streaks who haven't checked in today.
    Runs daily 8pm UTC."""
    from .database import SessionLocal
    from . import models
    from .push_service import send_push_notification

    logger.info("Starting streak push reminder job")
    db = SessionLocal()
    sent = 0
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        streaks = (
            db.query(models.UserStreak)
            .filter(
                models.UserStreak.current_streak > 0,
                models.UserStreak.last_active_date != today,
            )
            .all()
        )
        for streak in streaks:
            try:
                if send_push_notification(
                    user_id=streak.user_id,
                    alert_type="streak",
                    title="Keep your streak alive!",
                    body=f"You're on a {streak.current_streak}-day streak. Check in today!",
                    url="/discover",
                    tag="streak_reminder",
                ):
                    sent += 1
            except Exception:
                logger.exception("Failed streak push for %s", streak.user_id)
    finally:
        db.close()
    logger.info("Streak push reminders: sent %d", sent)


def check_price_alerts():
    """Fire price drop push + in-app alerts for triggered PriceAlerts.
    Runs daily 9am UTC."""
    from .database import SessionLocal
    from . import models
    from .push_service import send_push_notification

    logger.info("Starting price alert check job")
    db = SessionLocal()
    triggered = 0
    try:
        alerts = (
            db.query(models.PriceAlert)
            .filter(models.PriceAlert.triggered == False)  # noqa: E712
            .all()
        )
        for alert in alerts:
            try:
                whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == alert.whiskey_id).first()
                if not whiskey or not whiskey.price_usd:
                    continue
                current_price = whiskey.price_usd

                should_fire = False
                if alert.target_price and current_price <= alert.target_price:
                    should_fire = True
                elif alert.original_price and current_price < alert.original_price * 0.95:
                    should_fire = True

                if not should_fire:
                    continue

                # In-app alert
                db.add(models.WatchlistAlert(
                    username=alert.username,
                    alert_type="price_drop",
                    whiskey_id=alert.whiskey_id,
                    message=f"{whiskey.name} dropped to ${current_price:.2f}!",
                ))

                # Push notification
                send_push_notification(
                    user_id=alert.username,
                    alert_type="price_drop",
                    title="Price drop alert",
                    body=f"{whiskey.name} is now ${current_price:.2f}",
                    url=f"/whiskey/{alert.whiskey_id}",
                    tag=f"price_{alert.whiskey_id}",
                )

                alert.triggered = True
                triggered += 1
            except Exception:
                logger.exception("Failed price alert for %s whiskey %d",
                                 alert.username, alert.whiskey_id)
        db.commit()
    finally:
        db.close()
    logger.info("Price alerts: triggered %d", triggered)
