"""Email delivery via AWS SES.

Gracefully degrades if SES is not configured — logs a warning and skips.
Checks EmailPreference before sending non-transactional emails.
Logs all attempts to EmailLog table.
"""

import logging
import os

logger = logging.getLogger(__name__)

_ses_client = None
_ses_available = None  # None = not checked yet


def _get_ses_client():
    """Lazy-initialize SES client.  Returns None if credentials missing."""
    global _ses_client, _ses_available
    if _ses_available is False:
        return None
    if _ses_client is not None:
        return _ses_client

    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        logger.warning("AWS credentials not configured — email delivery disabled")
        _ses_available = False
        return None

    try:
        import boto3
        _ses_client = boto3.client(
            "ses",
            region_name=os.getenv("AWS_SES_REGION", "us-east-2"),
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        _ses_available = True
        return _ses_client
    except Exception as e:
        logger.warning("Failed to initialize SES client: %s", e)
        _ses_available = False
        return None


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    user_id: str | None = None,
    email_type: str = "transactional",
) -> bool:
    """Send email via SES.  Returns True on success."""
    # Check preferences for non-transactional emails
    if user_id and email_type not in ("welcome", "password_reset", "transactional"):
        if not _should_send(user_id, email_type):
            logger.info("User %s opted out of %s emails", user_id, email_type)
            return False

    client = _get_ses_client()
    if client is None:
        logger.info("SES not available — skipping email to %s (%s)", to_email, email_type)
        _log_email(user_id, email_type, subject, None, "skipped")
        return False

    from_email = os.getenv("SES_FROM_EMAIL", "noreply@sipsense.ai")
    try:
        response = client.send_email(
            Source=f"SipSense <{from_email}>",
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
        message_id = response.get("MessageId")
        _log_email(user_id, email_type, subject, message_id, "sent")
        logger.info("Email sent to %s: %s (type=%s)", to_email, message_id, email_type)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        _log_email(user_id, email_type, subject, None, "failed")
        return False


def _should_send(user_id: str, email_type: str) -> bool:
    """Check if user has opted into this email type."""
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
            "weekly_digest": pref.weekly_digest,
            "re_engagement": pref.re_engagement,
            "onboarding_drip": pref.onboarding_drip,
            "marketing": pref.marketing,
        }
        return mapping.get(email_type, True)
    finally:
        db.close()


def _log_email(
    user_id: str | None,
    email_type: str,
    subject: str,
    ses_message_id: str | None,
    status: str,
):
    """Log email send attempt to the database."""
    from .database import SessionLocal
    from . import models

    db = SessionLocal()
    try:
        db.add(models.EmailLog(
            user_id=user_id or "unknown",
            email_type=email_type,
            subject=subject,
            ses_message_id=ses_message_id,
            status=status,
        ))
        db.commit()
    except Exception:
        logger.exception("Failed to log email")
    finally:
        db.close()
