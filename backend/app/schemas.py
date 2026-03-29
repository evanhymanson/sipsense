from enum import Enum

import re

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, Literal
from datetime import datetime

from .storage import get_nobg_set, make_cdn_url


WHISKEY_FLAVOR_TAGS = [
    "vanilla", "caramel", "oak", "smoke", "honey", "spice", "cherry",
    "apple", "citrus", "chocolate", "leather", "tobacco", "cinnamon",
    "nutmeg", "pepper", "butterscotch", "maple", "dried fruit", "floral",
    "grain", "toffee", "peat", "brine", "mint", "coconut",
]


def _prefer_nobg(url: str | None) -> str | None:
    """Rewrite /uploads/bottles/X.png → /uploads/bottles_nobg/X.png if nobg version exists."""
    if not url or "/bottles/" not in url or "/bottles_nobg/" in url:
        return url
    filename = url.split("/")[-1]
    if filename in get_nobg_set():
        return url.replace("/uploads/bottles/", "/uploads/bottles_nobg/")
    return url


# ── Auth ──────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def password_complexity(self):
        pw = self.password
        if not re.search(r"[A-Z]", pw):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", pw):
            raise ValueError("Password must contain at least one digit")
        return self


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    quiz_completed: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Whiskey ────────────────────────────────────────────────────────────────

class WhiskeyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    distillery: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)
    region: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=200)
    abv: float = Field(..., ge=0.0, le=100.0)
    price_usd: Optional[float] = Field(None, ge=0.0, le=100000.0)
    description: Optional[str] = Field(None, max_length=5000)
    flavor_profile: Optional[str] = Field(None, max_length=500)


class WhiskeyCreate(WhiskeyBase):
    pass


class WhiskeyRead(WhiskeyBase):
    id: int
    rating_avg: float
    rating_count: int
    buy_links: Optional[str] = None
    image_url: Optional[str] = None
    price_is_estimated: bool = False
    flavor_x: Optional[int] = None   # 0 (sweet) → 100 (smoky)
    flavor_y: Optional[int] = None   # 0 (light) → 100 (bold)

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def prefer_nobg_image(self):
        """Serve background-removed bottle image when available, with CDN URL."""
        self.image_url = make_cdn_url(_prefer_nobg(self.image_url))
        return self


class WhiskeyListResponse(BaseModel):
    items: list[WhiskeyRead]
    total: int


# ── UserRating ─────────────────────────────────────────────────────────────

class RatingCreate(BaseModel):
    score: float = Field(..., ge=1.0, le=5.0)
    notes: Optional[str] = Field(None, max_length=2000)
    serving_style: Optional[Literal["neat", "rocks", "cocktail", "highball"]] = None
    location_note: Optional[str] = Field(None, max_length=200)
    flavor_tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_flavor_tags(self):
        # Snap score to nearest 0.5 increment
        self.score = round(self.score * 2) / 2
        if self.flavor_tags:
            valid = set(WHISKEY_FLAVOR_TAGS)
            self.flavor_tags = [t.lower().strip() for t in self.flavor_tags]
            invalid = [t for t in self.flavor_tags if t not in valid]
            if invalid:
                raise ValueError(f"Invalid flavor tags: {invalid}")
            self.flavor_tags = list(dict.fromkeys(self.flavor_tags))  # dedupe
            if len(self.flavor_tags) > 10:
                raise ValueError("Maximum 10 flavor tags allowed")
        return self


class RatingRead(BaseModel):
    id: int
    user_id: str
    whiskey_id: int
    score: float
    notes: Optional[str] = None
    serving_style: Optional[str] = None
    location_note: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    toast_count: int = 0
    helpful_count: int = 0
    user_marked_helpful: bool = False
    username: str = ""
    flavor_tags: list[str] = []

    model_config = {"from_attributes": True}


# ── Recommendation ─────────────────────────────────────────────────────────

class RecommendationRequest(BaseModel):
    user_id: str
    top_n: int = Field(default=5, ge=1, le=20)


class RecommendationResponse(BaseModel):
    whiskey: WhiskeyRead
    score: float  # recommendation confidence score


# ── Quiz ───────────────────────────────────────────────────────────────────

class QuizAnswers(BaseModel):
    flavors: list[str] = Field(default_factory=list)
    smokiness: str = "none"   # "none" | "light" | "heavy"
    body: str = "medium"      # "light" | "medium" | "full"
    budget: str = "mid"       # "budget" | "mid" | "premium" | "luxury"
    style: str = "any"        # "bourbon" | "scotch" | "irish" | "japanese" | "rye" | "any"


class QuizRecommendation(BaseModel):
    whiskey: WhiskeyRead
    score: float
    reason: str


# ── Favorites ───────────────────────────────────────────────────────────────

class FavoriteRead(BaseModel):
    id: int
    user_id: str
    whiskey_id: int

    model_config = {"from_attributes": True}


# ── Liquor Stores ──────────────────────────────────────────────────────────

class LiquorStoreRead(BaseModel):
    id: int
    osm_id: int
    name: str
    lat: float
    lng: float
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Optional[str] = None
    shop_type: Optional[str] = None
    distance_m: Optional[float] = None  # computed, not in DB

    model_config = {"from_attributes": True}


class StoreAvailabilityCreate(BaseModel):
    whiskey_id: int
    status: Literal["in_stock", "out_of_stock", "unknown"] = "in_stock"


class StoreAvailabilityRead(BaseModel):
    id: int
    user_id: str
    store_id: int
    whiskey_id: int
    status: str
    reported_at: datetime

    model_config = {"from_attributes": True}


class StoreWithAvailability(LiquorStoreRead):
    availability: list[StoreAvailabilityRead] = []
    latest_status: Optional[str] = None
    report_count: int = 0


# ── Social / Feed ─────────────────────────────────────────────────────────

class ToastRead(BaseModel):
    id: int
    user_id: str
    rating_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BadgeRead(BaseModel):
    slug: str
    name: str
    description: str
    emoji: str
    category: str

    model_config = {"from_attributes": True}


class UserBadgeRead(BaseModel):
    badge: BadgeRead
    awarded_at: datetime

    model_config = {"from_attributes": True}


class CheckInCommentRead(BaseModel):
    id: int
    user_id: str
    rating_id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckInCommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class FeedItem(BaseModel):
    rating: RatingRead
    whiskey: WhiskeyRead
    username: str
    toast_count: int = 0
    user_toasted: bool = False  # whether the requesting user has toasted this
    helpful_count: int = 0
    user_marked_helpful: bool = False
    comment_count: int = 0


class FeedResponse(BaseModel):
    items: list[FeedItem]
    has_more: bool


class UserRatingsResponse(BaseModel):
    items: list[FeedItem]
    total: int
    has_more: bool


class StreakInfo(BaseModel):
    current_streak: int
    longest_streak: int
    is_new_day: bool


class ChallengeUpdate(BaseModel):
    challenge_title: str
    progress: int
    goal: int
    completed: bool


class CheckInResponse(BaseModel):
    """Returned after a successful check-in (rate_whiskey)."""
    rating: RatingRead
    new_badges: list[BadgeRead] = []
    insights: list[str] = []
    streak: Optional[StreakInfo] = None
    challenge_updates: list[ChallengeUpdate] = []


class ReviewSortOption(str, Enum):
    recent = "recent"
    helpful = "helpful"
    highest = "highest"
    lowest = "lowest"


class RatingDistribution(BaseModel):
    star_1: int = 0
    star_2: int = 0
    star_3: int = 0
    star_4: int = 0
    star_5: int = 0
    total: int = 0
    average: float = 0.0


class CommunityFlavorTag(BaseModel):
    tag: str
    count: int
    percentage: float


class WhiskeyReviewSummary(BaseModel):
    distribution: RatingDistribution
    community_tags: list[CommunityFlavorTag] = []
    serving_style_counts: dict[str, int] = {}


class UserSearchResult(BaseModel):
    username: str
    total_checkins: int = 0
    follower_count: int = 0
    is_following: bool = False


class SuggestedUserResult(BaseModel):
    username: str
    total_checkins: int = 0
    follower_count: int = 0
    is_following: bool = False
    match_score: int = 0
    reason: str = ""


class PalateMatchResult(BaseModel):
    match_score: int | None = None  # 0-100 or None if insufficient data
    shared_flavors: list[str] = []
    agreements: list[dict] = []
    disagreements: list[dict] = []
    your_total_rated: int = 0
    their_total_rated: int = 0
    message: str | None = None


class PublicProfile(BaseModel):
    username: str
    member_since: datetime | None = None
    total_checkins: int
    unique_whiskeys: int
    avg_score: float | None = None
    top_categories: list[dict] = []
    badges: list[UserBadgeRead] = []
    recent_checkins: list[FeedItem] = []
    follower_count: int = 0
    following_count: int = 0
    is_following: bool = False
    level: dict | None = None
    user_lists: list[dict] = []


# ── Watchlist & Alerts ────────────────────────────────────────────────────

class WatchlistItemRead(BaseModel):
    id: int
    whiskey_id: int
    whiskey_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistAlertRead(BaseModel):
    id: int
    alert_type: str = "watchlist"
    whiskey_id: int | None = None
    whiskey_name: str | None = None
    from_username: str | None = None
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Video ────────────────────────────────────────────────────────────────


class VideoRead(BaseModel):
    id: int
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: str
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    whiskey_id: Optional[int] = None
    whiskey_name: Optional[str] = None
    whiskey_image_url: Optional[str] = None
    location_name: Optional[str] = None
    price_tag: Optional[float] = None
    view_count: int = 0
    toast_count: int = 0
    comment_count: int = 0
    user_toasted: bool = False
    is_sponsored: bool = False
    sponsor_label: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def prefer_nobg_image(self):
        """Serve background-removed bottle image when available, with CDN URL."""
        self.whiskey_image_url = make_cdn_url(_prefer_nobg(self.whiskey_image_url))
        return self


class VideoFeedResponse(BaseModel):
    items: list[VideoRead]
    has_more: bool


class VideoCommentRead(BaseModel):
    id: int
    user_id: str
    video_id: int
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoCommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


# ── Affiliate ────────────────────────────────────────────────────────────


class AffiliateClickCreate(BaseModel):
    whiskey_id: int
    retailer: str
    source: str = "detail"


class AffiliateStats(BaseModel):
    total_clicks: int
    clicks_by_retailer: dict[str, int]
    clicks_by_source: dict[str, int]
    conversion_count: int
    total_commission: float


# ── Subscription ─────────────────────────────────────────────────────────


class SubscriptionStatus(BaseModel):
    is_premium: bool
    tier: Optional[str] = None
    expires_at: Optional[datetime] = None
    has_stripe: bool = False


class FeatureComparison(BaseModel):
    feature: str
    free_tier: str
    premium_tier: str


# ── Price Alerts ──────────────────────────────────────────────────────────


class PriceAlertCreate(BaseModel):
    whiskey_id: int
    target_price: Optional[float] = None


class PriceAlertRead(BaseModel):
    id: int
    whiskey_id: int
    whiskey_name: str
    target_price: Optional[float] = None
    original_price: Optional[float] = None
    triggered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Stripe ───────────────────────────────────────────────────────────────


class StripeCheckoutCreate(BaseModel):
    plan: Literal["monthly", "yearly"] = "monthly"


class StripeCheckoutResponse(BaseModel):
    checkout_url: str


# ── Sponsored ────────────────────────────────────────────────────────────


class SponsoredPlacementRead(BaseModel):
    id: int
    advertiser_name: str
    whiskey_id: Optional[int] = None
    placement_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    whiskey: Optional[WhiskeyRead] = None

    model_config = {"from_attributes": True}


# ── Top Lists ────────────────────────────────────────────────────────────


class TopListItemRead(BaseModel):
    rank: int
    whiskey: WhiskeyRead
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class TopListSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: Optional[str] = None
    list_type: str
    category: Optional[str] = None
    image_emoji: str = "\U0001f3c6"
    item_count: int = 0

    model_config = {"from_attributes": True}


class TopListDetail(TopListSummary):
    items: list[TopListItemRead] = []

# ── User Levels ──────────────────────────────────────────────────────────


class UserLevel(BaseModel):
    rank: int
    name: str
    emoji: str
    points: int
    next_level_name: str | None = None
    next_level_points: int | None = None
    progress_pct: float = 0.0


# ── User-Created Lists ──────────────────────────────────────────────────


class UserListCreate(BaseModel):
    title: str
    description: str | None = None
    is_public: bool = True
    whiskey_ids: list[int] = []


class UserListUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    is_public: bool | None = None


class UserListItemAdd(BaseModel):
    whiskey_id: int
    note: str | None = None


class UserListReorder(BaseModel):
    whiskey_ids: list[int]


class UserListItemRead(BaseModel):
    position: int
    whiskey: WhiskeyRead
    note: str | None = None
    added_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserListSummary(BaseModel):
    id: int
    slug: str
    title: str
    description: str | None = None
    is_public: bool = True
    username: str
    item_count: int = 0
    preview_whiskeys: list[WhiskeyRead] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserListDetail(UserListSummary):
    items: list[UserListItemRead] = []


# ── Critic / Expert Scores ──────────────────────────────────────────────


class CriticScoreRead(BaseModel):
    id: int
    source: str
    source_display: str
    score: float
    max_score: float = 100.0
    normalized_score: float = 0.0
    review_year: int | None = None
    review_text: str | None = None
    url: str | None = None

    model_config = {"from_attributes": True}


class CriticScoreCreate(BaseModel):
    whiskey_id: int
    source: str
    source_display: str
    score: float
    max_score: float = 100.0
    review_year: int | None = None
    review_text: str | None = None
    url: str | None = None


class WhiskeyCriticScores(BaseModel):
    whiskey_id: int
    scores: list[CriticScoreRead] = []
    avg_critic_score: float | None = None


# ── Password Reset ──────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


# ── Email Preferences ──────────────────────────────────────────────────


class EmailPreferenceRead(BaseModel):
    weekly_digest: bool = True
    re_engagement: bool = True
    onboarding_drip: bool = True
    marketing: bool = True

    model_config = {"from_attributes": True}


class EmailPreferenceUpdate(BaseModel):
    weekly_digest: bool | None = None
    re_engagement: bool | None = None
    onboarding_drip: bool | None = None
    marketing: bool | None = None


# ── Admin ────────────────────────────────────────────────────────────────

class WhiskeyAdminUpdate(BaseModel):
    name: str | None = None
    distillery: str | None = None
    category: str | None = None
    region: str | None = None
    age: int | None = None
    abv: float | None = None
    price_usd: float | None = None
    description: str | None = None
    flavor_profile: str | None = None
    image_url: str | None = None
    upc: str | None = None


class WhiskeyBatchClearImages(BaseModel):
    whiskey_ids: list[int]
