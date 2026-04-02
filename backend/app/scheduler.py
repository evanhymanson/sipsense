"""Background scheduler for periodic email jobs.

Run as a standalone service: python -m app.scheduler
Uses APScheduler with BlockingScheduler (no Redis needed).
"""

import logging
import os
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("scheduler")


def main():
    env = os.getenv("SIPSENSE_ENV", "development").lower()

    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler()

    from .scheduled_jobs import (
        send_weekly_digests,
        send_re_engagement_emails,
        send_drip_emails,
        send_streak_push_reminders,
        check_price_alerts,
        retrain_recommendation_model,
    )

    # Weekly digest: Sunday 10am UTC
    scheduler.add_job(
        send_weekly_digests,
        CronTrigger(day_of_week="sun", hour=10),
        id="weekly_digest",
    )

    # Re-engagement: Daily 2pm UTC
    scheduler.add_job(
        send_re_engagement_emails,
        CronTrigger(hour=14),
        id="re_engagement",
    )

    # Onboarding drip: Daily 11am UTC
    scheduler.add_job(
        send_drip_emails,
        CronTrigger(hour=11),
        id="drip_emails",
    )

    # Streak push reminder: Daily 8pm UTC
    scheduler.add_job(
        send_streak_push_reminders,
        CronTrigger(hour=20),
        id="streak_push_reminders",
    )

    # Price alerts: Daily 9am UTC
    scheduler.add_job(
        check_price_alerts,
        CronTrigger(hour=9),
        id="price_alerts",
    )

    # Model retrain: Weekly Monday 3am UTC (off-peak)
    scheduler.add_job(
        retrain_recommendation_model,
        CronTrigger(day_of_week="mon", hour=3),
        id="model_retrain",
        misfire_grace_time=3600,
    )

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("Scheduler started with %d jobs (env=%s)", len(scheduler.get_jobs()), env)
    for job in scheduler.get_jobs():
        logger.info("  Job: %s — next run: %s", job.id, job.next_run_time)

    scheduler.start()


if __name__ == "__main__":
    main()
