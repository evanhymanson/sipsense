"""Gap 15: Internationalization scaffolding.

Simple translation dict infrastructure with a t() helper.
Currently English-only; additional languages can be added as dicts.
"""

from typing import Optional

TRANSLATIONS = {
    "en": {
        "app.name": "SipSense",
        "app.tagline": "AI-Powered Whiskey Discovery",
        "nav.browse": "Browse",
        "nav.discover": "Discover",
        "nav.feed": "Feed",
        "nav.profile": "Profile",
        "nav.scan": "Scan",
        "nav.learn": "Learn",
        "nav.premium": "Premium",
        "nav.alerts": "Alerts",
        "nav.regions": "Regions",
        "nav.leaderboard": "Leaderboard",
        "nav.awards": "Awards",
        "auth.login": "Log In",
        "auth.register": "Sign Up",
        "auth.logout": "Log Out",
        "auth.forgot_password": "Forgot Password?",
        "auth.reset_password": "Reset Password",
        "whiskey.check_in": "Check In",
        "whiskey.add_to_favorites": "Add to Favorites",
        "whiskey.remove_from_favorites": "Remove from Favorites",
        "whiskey.add_to_collection": "Add to Collection",
        "whiskey.share": "Share",
        "whiskey.compare": "Compare",
        "whiskey.buy": "Buy",
        "whiskey.no_results": "No whiskeys found",
        "rating.stars": "{count} stars",
        "rating.notes_placeholder": "How was it? Share your tasting notes...",
        "social.toast": "Toast",
        "social.comment": "Comment",
        "social.follow": "Follow",
        "social.unfollow": "Unfollow",
        "social.followers": "Followers",
        "social.following": "Following",
        "quiz.start": "Take the Taste Quiz",
        "quiz.next": "Next",
        "quiz.finish": "See My Results",
        "common.loading": "Loading...",
        "common.error": "Something went wrong",
        "common.save": "Save",
        "common.cancel": "Cancel",
        "common.delete": "Delete",
        "common.edit": "Edit",
        "common.see_more": "See More",
        "common.see_all": "See All",
    },
}

DEFAULT_LOCALE = "en"


def t(key: str, locale: Optional[str] = None, **kwargs) -> str:
    """Translate a key to the given locale (or default).

    Supports simple string interpolation:
        t("rating.stars", count=5)  ->  "5 stars"
    """
    lang = locale or DEFAULT_LOCALE
    strings = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LOCALE])
    value = strings.get(key, key)
    if kwargs:
        try:
            value = value.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return value


def get_available_locales() -> list[str]:
    """Return list of available locale codes."""
    return list(TRANSLATIONS.keys())
