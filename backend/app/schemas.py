import os
from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, Literal
from datetime import datetime

# Absolute path to backend/uploads for nobg file existence checks
_UPLOADS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))


def _prefer_nobg(url: str | None) -> str | None:
    """Rewrite /uploads/bottles/X.png → /uploads/bottles_nobg/X.png if the file exists."""
    if not url or "/uploads/bottles/" not in url or "/bottles_nobg/" in url:
        return url
    nobg_url = url.replace("/uploads/bottles/", "/uploads/bottles_nobg/")
    nobg_path = os.path.join(_UPLOADS_ROOT, *nobg_url.lstrip("/").split("/")[1:])
    return nobg_url if os.path.isfile(nobg_path) else url


# ── Auth ──────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
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
        """Serve background-removed bottle image when available."""
        self.image_url = _prefer_nobg(self.image_url)
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


class FeedItem(BaseModel):
    rating: RatingRead
    whiskey: WhiskeyRead
    username: str
    toast_count: int = 0
    user_toasted: bool = False  # whether the requesting user has toasted this


class FeedResponse(BaseModel):
    items: list[FeedItem]
    has_more: bool


class CheckInResponse(BaseModel):
    """Returned after a successful check-in (rate_whiskey)."""
    rating: RatingRead
    new_badges: list[BadgeRead] = []


class UserSearchResult(BaseModel):
    username: str
    total_checkins: int = 0
    follower_count: int = 0
    is_following: bool = False


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
        """Serve background-removed bottle image when available."""
        self.whiskey_image_url = _prefer_nobg(self.whiskey_image_url)
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


class FeatureComparison(BaseModel):
    feature: str
    free_tier: str
    premium_tier: str


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
