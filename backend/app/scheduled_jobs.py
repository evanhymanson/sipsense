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
        users = db.query(models.User).filter(models.User.is_active == True).yield_per(100)
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

            # Find users registered on target_date (filter in DB instead of loading all)
            target_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            target_end = target_start + timedelta(days=1)
            users = (
                db.query(models.User)
                .filter(
                    models.User.is_active == True,
                    models.User.created_at >= target_start,
                    models.User.created_at < target_end,
                )
                .all()
            )

            for user in users:
                try:

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
        # Batch load all whiskeys referenced by alerts to avoid N+1 queries
        whiskey_ids = list({a.whiskey_id for a in alerts})
        whiskeys_by_id = {}
        if whiskey_ids:
            whiskeys_by_id = {
                w.id: w
                for w in db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()
            }
        for alert in alerts:
            try:
                whiskey = whiskeys_by_id.get(alert.whiskey_id)
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


def retrain_recommendation_model():
    """Retrain the NCF recommendation model if enough new data exists.

    Steps:
    1. Check if enough new ratings since last training
    2. Train new model with quality gating
    3. Log results to ModelTrainingLog table
    """
    from .database import SessionLocal
    from . import models

    logger.info("Starting model retraining check")
    db = SessionLocal()

    try:
        # Guard: prevent concurrent training runs
        running = (
            db.query(models.ModelTrainingLog)
            .filter(models.ModelTrainingLog.status == "running")
            .first()
        )
        if running:
            logger.warning("Training already in progress (log id=%d). Skipping.", running.id)
            return

        # 1. Check if enough new ratings exist since last training
        last_log = (
            db.query(models.ModelTrainingLog)
            .filter(models.ModelTrainingLog.status == "completed")
            .order_by(models.ModelTrainingLog.completed_at.desc())
            .first()
        )

        if last_log and last_log.completed_at:
            new_ratings_count = (
                db.query(models.UserRating)
                .filter(models.UserRating.created_at > last_log.completed_at)
                .count()
            )
        else:
            new_ratings_count = db.query(models.UserRating).count()

        min_new_ratings = 10
        if new_ratings_count < min_new_ratings:
            logger.info(
                "Only %d new ratings (need %d). Skipping retraining.",
                new_ratings_count, min_new_ratings,
            )
            return

        # 2. Create log entry
        log = models.ModelTrainingLog(status="running")
        db.add(log)
        db.commit()
        db.refresh(log)

        # 3. Train
        try:
            from .ml.train import train, META_PATH
            train(epochs=30, lr=0.001, batch_size=256, embedding_dim=32)
        except Exception as e:
            log.status = "failed"
            log.rejection_reason = str(e)[:500]
            log.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.exception("Model training failed")
            return

        # 4. Validate quality
        import json
        if META_PATH.exists():
            meta = json.loads(META_PATH.read_text())
            new_rmse = meta.get("rmse", float("inf"))
        else:
            log.status = "failed"
            log.rejection_reason = "No meta file after training"
            log.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Reject if RMSE is unreasonably high (predictions off by >1.5 stars)
        max_rmse = 1.5
        if new_rmse > max_rmse:
            log.status = "rejected"
            log.rejection_reason = f"RMSE {new_rmse:.4f} exceeds threshold {max_rmse}"
            log.val_rmse = new_rmse
            log.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning("Model rejected: RMSE %.4f exceeds threshold", new_rmse)
            return

        # 5. Update log with success
        log.status = "completed"
        log.n_ratings = meta.get("n_ratings")
        log.n_users = meta.get("n_users")
        log.n_items = meta.get("n_items")
        log.val_rmse = new_rmse
        log.val_mae = meta.get("mae")
        log.train_rmse = meta.get("train_rmse")
        log.epochs_run = meta.get("epochs")
        log.completed_at = datetime.now(timezone.utc)
        db.commit()

        # 6. Signal backend to reload model on next request
        try:
            from .ml.inference import reload_model
            reload_model()
        except Exception:
            pass  # Backend will pick up new model on next cache miss

        logger.info(
            "Model retrained successfully: RMSE=%.4f, %d ratings",
            new_rmse, meta.get("n_ratings", 0),
        )

    except Exception:
        logger.exception("Unexpected error in model retraining")
    finally:
        db.close()
