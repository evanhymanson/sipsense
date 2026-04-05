"""
Action name constants for user analytics tracking.
Used by track.py and the analytics dashboard.
"""

# Auth
ACTION_LOGIN = "login"
ACTION_REGISTER = "register"

# Core engagement
ACTION_SEARCH = "search"
ACTION_WHISKEY_VIEW = "whiskey_view"
ACTION_RATING = "rating"
ACTION_FAVORITE = "favorite"
ACTION_UNFAVORITE = "unfavorite"

# AI features
ACTION_CHAT_MESSAGE = "chat_message"
ACTION_AI_TASTING = "ai_tasting"
ACTION_AI_PALATE = "ai_palate"

# Discovery
ACTION_QUIZ_COMPLETE = "quiz_complete"
ACTION_SCAN_ATTEMPT = "scan_attempt"

# Social
ACTION_FOLLOW = "follow"
ACTION_TOAST = "toast"
ACTION_COMMENT = "comment"
ACTION_VIDEO_WATCH = "video_watch"

# Commerce
ACTION_BUY_CLICK = "buy_click"
ACTION_PREMIUM_VIEW = "premium_view"

# Journeys
ACTION_JOURNEY_START = "journey_start"
ACTION_JOURNEY_COMPLETE = "journey_complete"

# Recommendation tracking
ACTION_CHAT_TOOL_CALL = "chat_tool_call"
ACTION_REC_IMPRESSION = "rec_impression"
