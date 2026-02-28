from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    username: str = Field(..., min_length=2, max_length=30, pattern=r'^[a-zA-Z0-9_]+$')
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


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
    name: str
    distillery: str
    category: str
    region: Optional[str] = None
    age: Optional[int] = None
    abv: float
    price_usd: Optional[float] = None
    description: Optional[str] = None
    flavor_profile: Optional[str] = None


class WhiskeyCreate(WhiskeyBase):
    pass


class WhiskeyRead(WhiskeyBase):
    id: int
    rating_avg: float
    rating_count: int

    model_config = {"from_attributes": True}


# ── UserRating ─────────────────────────────────────────────────────────────

class RatingCreate(BaseModel):
    score: float = Field(..., ge=1.0, le=5.0)
    notes: Optional[str] = None
    serving_style: Optional[Literal["neat", "rocks", "cocktail", "highball"]] = None
    location_note: Optional[str] = None


class RatingRead(BaseModel):
    id: int
    user_id: str
    whiskey_id: int
    score: float
    notes: Optional[str] = None
    serving_style: Optional[str] = None
    location_note: Optional[str] = None
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


class PublicProfile(BaseModel):
    username: str
    member_since: datetime | None = None
    total_checkins: int
    unique_whiskeys: int
    avg_score: float | None = None
    top_categories: list[dict] = []
    badges: list[UserBadgeRead] = []
    recent_checkins: list[FeedItem] = []
