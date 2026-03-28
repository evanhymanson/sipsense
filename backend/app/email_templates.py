"""Email templates for SipSense.

Each function returns (subject, html_body, text_body).
Uses inline CSS for email client compatibility.
"""

import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://sipsense.ai")


def _base_template(content: str, unsubscribe_url: str = "") -> str:
    """Wrap content in branded email template."""
    unsub = ""
    if unsubscribe_url:
        unsub = f'<p style="font-size:12px;color:#999;margin-top:24px;"><a href="{unsubscribe_url}" style="color:#999;">Unsubscribe</a></p>'

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#1a1a1a;font-family:system-ui,-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#1a1a1a;">
<tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr><td style="padding:24px 0;text-align:center;">
    <span style="font-size:24px;font-weight:700;color:#c9a84c;letter-spacing:1px;">SipSense</span>
  </td></tr>
  <tr><td style="background:#222;border-radius:12px;padding:32px;color:#ece8e3;">
    {content}
  </td></tr>
  <tr><td style="padding:24px 0;text-align:center;font-size:12px;color:#666;">
    <p>SipSense — AI-Powered Whiskey Discovery</p>
    <p><a href="{FRONTEND_URL}" style="color:#c9a84c;">sipsense.ai</a></p>
    {unsub}
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def welcome_email(username: str) -> tuple[str, str, str]:
    """Welcome email sent after registration."""
    subject = f"Welcome to SipSense, {username}!"

    content = f"""
    <h2 style="color:#c9a84c;margin:0 0 16px;">Welcome, {username}!</h2>
    <p style="margin:0 0 16px;line-height:1.6;">
      You've just joined a community of whiskey enthusiasts who use AI to discover,
      track, and explore the world of whiskey. Here's how to get started:
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
      <tr><td style="padding:12px 0;border-bottom:1px solid #333;">
        <strong style="color:#c9a84c;">1. Take the Taste Quiz</strong><br>
        <span style="color:#d0c9c0;">Answer a few questions and we'll recommend your perfect pour.</span>
      </td></tr>
      <tr><td style="padding:12px 0;border-bottom:1px solid #333;">
        <strong style="color:#c9a84c;">2. Check In Your First Whiskey</strong><br>
        <span style="color:#d0c9c0;">Rate it, add tasting notes, and start building your palate profile.</span>
      </td></tr>
      <tr><td style="padding:12px 0;">
        <strong style="color:#c9a84c;">3. Ask the AI Anything</strong><br>
        <span style="color:#d0c9c0;">Our chat assistant knows whiskey inside and out. Try it!</span>
      </td></tr>
    </table>
    <a href="{FRONTEND_URL}/quiz" style="display:inline-block;padding:12px 32px;background:#c9a84c;color:#1a1a1a;text-decoration:none;border-radius:8px;font-weight:700;">Start Your Journey</a>
    """

    text = f"""Welcome to SipSense, {username}!

Here's how to get started:
1. Take the Taste Quiz — {FRONTEND_URL}/quiz
2. Check in your first whiskey
3. Ask the AI anything

Visit {FRONTEND_URL} to begin your whiskey journey."""

    return subject, _base_template(content), text


def password_reset_email(username: str, reset_url: str) -> tuple[str, str, str]:
    """Password reset email with secure link."""
    subject = "Reset your SipSense password"

    content = f"""
    <h2 style="color:#c9a84c;margin:0 0 16px;">Password Reset</h2>
    <p style="margin:0 0 16px;line-height:1.6;">
      Hi {username}, we received a request to reset your password.
      Click the button below to choose a new one:
    </p>
    <p style="text-align:center;margin:24px 0;">
      <a href="{reset_url}" style="display:inline-block;padding:14px 40px;background:#c9a84c;color:#1a1a1a;text-decoration:none;border-radius:8px;font-weight:700;font-size:16px;">Reset Password</a>
    </p>
    <p style="color:#999;font-size:13px;margin:16px 0 0;">
      This link expires in 1 hour. If you didn't request this, you can safely ignore this email.
    </p>
    """

    text = f"""Hi {username},

We received a request to reset your SipSense password.
Visit this link to choose a new one: {reset_url}

This link expires in 1 hour. If you didn't request this, ignore this email."""

    return subject, _base_template(content), text


def weekly_digest_email(username: str, data: dict) -> tuple[str, str, str]:
    """Weekly activity digest."""
    subject = f"Your week in whiskey, {username}"

    checkins = data.get("checkins_this_week", 0)
    streak = data.get("current_streak", 0)
    trending = data.get("trending_name", "")

    content = f"""
    <h2 style="color:#c9a84c;margin:0 0 16px;">This Week in Whiskey</h2>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
      <tr>
        <td style="text-align:center;padding:16px;background:#2a2a2a;border-radius:8px;width:33%;">
          <div style="font-size:28px;font-weight:700;color:#c9a84c;">{checkins}</div>
          <div style="font-size:12px;color:#999;margin-top:4px;">Check-ins</div>
        </td>
        <td style="width:8px;"></td>
        <td style="text-align:center;padding:16px;background:#2a2a2a;border-radius:8px;width:33%;">
          <div style="font-size:28px;font-weight:700;color:#c9a84c;">{streak}</div>
          <div style="font-size:12px;color:#999;margin-top:4px;">Day Streak</div>
        </td>
      </tr>
    </table>
    {"<p style='margin:0 0 16px;'><strong style=\"color:#c9a84c;\">Trending:</strong> " + trending + " is popular this week.</p>" if trending else ""}
    <a href="{FRONTEND_URL}/discover" style="display:inline-block;padding:12px 32px;background:#c9a84c;color:#1a1a1a;text-decoration:none;border-radius:8px;font-weight:700;">Discover More</a>
    """

    text = f"""Your week in whiskey, {username}

Check-ins: {checkins}
Streak: {streak} days
{"Trending: " + trending if trending else ""}

Visit {FRONTEND_URL}/discover"""

    return subject, _base_template(content), text


def re_engagement_email(username: str, data: dict) -> tuple[str, str, str]:
    """Re-engagement email for inactive users."""
    subject = f"We miss you, {username} — here's what's new"

    daily_name = data.get("daily_discovery", "a new whiskey")
    new_count = data.get("new_whiskeys_added", 0)

    content = f"""
    <h2 style="color:#c9a84c;margin:0 0 16px;">It's Been a While!</h2>
    <p style="margin:0 0 16px;line-height:1.6;">
      The whiskey world doesn't stop, {username}. Here's what you've been missing:
    </p>
    <ul style="color:#d0c9c0;line-height:2;">
      {"<li><strong>" + str(new_count) + " new whiskeys</strong> added to the catalog</li>" if new_count else ""}
      <li>Today's discovery: <strong style="color:#c9a84c;">{daily_name}</strong></li>
      <li>Your palate profile is waiting for its next data point</li>
    </ul>
    <p style="margin:24px 0;text-align:center;">
      <a href="{FRONTEND_URL}/discover" style="display:inline-block;padding:12px 32px;background:#c9a84c;color:#1a1a1a;text-decoration:none;border-radius:8px;font-weight:700;">Come Back &amp; Explore</a>
    </p>
    """

    text = f"""It's been a while, {username}!

Here's what you've been missing:
- {new_count} new whiskeys added
- Today's discovery: {daily_name}

Visit {FRONTEND_URL}/discover"""

    return subject, _base_template(content), text


def drip_email(username: str, day: int) -> tuple[str, str, str]:
    """Onboarding drip at day 1, 3, 7, or 14 after registration."""
    templates = {
        1: {
            "subject": f"Getting started with SipSense, {username}",
            "heading": "Your First Steps",
            "body": "Welcome aboard! Start by taking the taste quiz — it only takes 2 minutes and helps us personalize your experience.",
            "cta_text": "Take the Quiz",
            "cta_url": f"{FRONTEND_URL}/quiz",
        },
        3: {
            "subject": f"Have you tried the AI chat yet, {username}?",
            "heading": "Meet Your Whiskey Assistant",
            "body": "Our AI chat knows about 5,000+ whiskeys. Ask it anything — \"What's a good bourbon under $40?\" or \"What pairs with smoked brisket?\"",
            "cta_text": "Chat Now",
            "cta_url": f"{FRONTEND_URL}",
        },
        7: {
            "subject": f"Your palate profile is growing, {username}",
            "heading": "One Week In!",
            "body": "Every check-in teaches us more about your taste. The more you rate, the better your recommendations get. Check your palate profile to see what we've learned so far.",
            "cta_text": "View Your Profile",
            "cta_url": f"{FRONTEND_URL}/profile",
        },
        14: {
            "subject": f"Ready for your next bottle, {username}?",
            "heading": "Two Weeks of Discovery",
            "body": "You've been building your palate profile for two weeks now. Ready for a personalized recommendation? Our AI has some ideas for your next pour.",
            "cta_text": "Get Recommendations",
            "cta_url": f"{FRONTEND_URL}/discover",
        },
    }

    t = templates.get(day, templates[1])

    content = f"""
    <h2 style="color:#c9a84c;margin:0 0 16px;">{t['heading']}</h2>
    <p style="margin:0 0 24px;line-height:1.6;">{t['body']}</p>
    <a href="{t['cta_url']}" style="display:inline-block;padding:12px 32px;background:#c9a84c;color:#1a1a1a;text-decoration:none;border-radius:8px;font-weight:700;">{t['cta_text']}</a>
    """

    text = f"""{t['heading']}

{t['body']}

Visit: {t['cta_url']}"""

    return t["subject"], _base_template(content), text
