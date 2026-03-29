from sqlalchemy import Column, Integer, BigInteger, String, Float, Text, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    quiz_completed = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime(timezone=True))



class Whiskey(Base):
    __tablename__ = "whiskeys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    distillery = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)  # bourbon, scotch, irish, japanese, rye, etc.
    region = Column(String, index=True)                     # e.g. Speyside, Kentucky, Islay
    age = Column(Integer)                       # age in years, nullable for NAS
    abv = Column(Float, nullable=False)         # alcohol by volume %
    price_usd = Column(Float)
    description = Column(Text)
    flavor_profile = Column(Text)               # comma-separated tags: smoky, sweet, fruity, etc.
    rating_avg = Column(Float, default=0.0, index=True)  # may include ratings from external sources
    rating_count = Column(Integer, default=0)    # user ratings on this platform only; 0 with
                                                  # rating_avg > 0 means external-source rating
    upc = Column(String, index=True)            # barcode from OpenFoodFacts — enables label scan
    source = Column(String, default="manual")   # "ttb", "distiller", "wikidata", "openfoodfacts", etc.
    buy_links = Column(Text)                    # JSON: [{"retailer": "...", "url": "..."}]
    image_url = Column(String)                   # relative path to bottle image
    price_is_estimated = Column(Boolean, default=False)  # True if price was statistically estimated
    flavor_x = Column(Integer)   # 0 (sweet) → 100 (smoky), AI-scored
    flavor_y = Column(Integer)   # 0 (light) → 100 (bold),  AI-scored
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    ratings = relationship("UserRating", back_populates="whiskey", cascade="all, delete-orphan")


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class UserRating(Base):
    __tablename__ = "user_ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "whiskey_id", name="uq_user_rating"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)  # simple string ID for now
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, nullable=False)  # 1.0 to 5.0
    notes = Column(Text)
    serving_style = Column(String)  # neat, rocks, cocktail, highball
    location_note = Column(String)  # freeform: "The Macallan Bar, NYC"
    image_path = Column(String)     # relative path to uploaded rating photo
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey", back_populates="ratings")

    @property
    def image_url(self) -> str | None:
        """Expose image_path as image_url so Pydantic's from_attributes can map it."""
        if not self.image_path:
            return None
        from .storage import make_cdn_url
        return make_cdn_url(f"/uploads/{self.image_path}")

    toasts = relationship("Toast", back_populates="rating", cascade="all, delete-orphan")
    comments = relationship("CheckInComment", back_populates="rating", cascade="all, delete-orphan")
    flavor_tags = relationship("ReviewFlavorTag", back_populates="rating", cascade="all, delete-orphan")
    helpful_votes = relationship("ReviewHelpful", back_populates="rating", cascade="all, delete-orphan")


class UserMemory(Base):
    """Persistent memory of a user's whiskey preferences, extracted from conversations."""
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    # JSON blob: {likes: [], dislikes: [], budget: "", style: "", notes: ""}
    preferences = Column(Text, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ConversationSummary(Base):
    """Auto-generated summary of a chat session for cross-conversation memory."""
    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    topic_tags = Column(String)
    whiskeys_discussed = Column(String)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CollectionItem(Base):
    """A bottle in a user's personal shelf/collection."""
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="sealed")  # sealed, opened, finished
    purchase_price = Column(Float)
    purchase_location = Column(String)
    personal_notes = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class LiquorStore(Base):
    __tablename__ = "liquor_stores"

    id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String, default="Liquor Store")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    address = Column(String)
    phone = Column(String)
    website = Column(String)
    opening_hours = Column(String)
    shop_type = Column(String)  # "alcohol", "wine", etc. from OSM tags
    last_fetched = Column(DateTime(timezone=True), server_default=func.now())

    availability_reports = relationship("StoreAvailability", back_populates="store")


class StoreAvailability(Base):
    __tablename__ = "store_availability"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("liquor_stores.id", ondelete="CASCADE"), nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, nullable=False, default="in_stock")  # in_stock, out_of_stock, unknown
    reported_at = Column(DateTime(timezone=True), server_default=func.now())

    store = relationship("LiquorStore", back_populates="availability_reports")
    whiskey = relationship("Whiskey")


class Toast(Base):
    """A 'like' on a check-in (rating)."""
    __tablename__ = "toasts"
    __table_args__ = (
        UniqueConstraint("user_id", "rating_id", name="uq_toast_user_rating"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    rating_id = Column(Integer, ForeignKey("user_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("UserRating", back_populates="toasts")


class ReviewHelpful(Base):
    """A 'helpful' vote on a review (check-in). Separate from toasts."""
    __tablename__ = "review_helpful"
    __table_args__ = (
        UniqueConstraint("user_id", "rating_id", name="uq_helpful_user_rating"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    rating_id = Column(Integer, ForeignKey("user_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("UserRating", back_populates="helpful_votes")


class CheckInComment(Base):
    """A comment on a check-in (rating)."""
    __tablename__ = "checkin_comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    rating_id = Column(Integer, ForeignKey("user_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("UserRating", back_populates="comments")


class ReviewFlavorTag(Base):
    """A flavor tag submitted by a user as part of their check-in."""
    __tablename__ = "review_flavor_tags"
    __table_args__ = (
        UniqueConstraint("rating_id", "tag_name", name="uq_rating_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    rating_id = Column(Integer, ForeignKey("user_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("UserRating", back_populates="flavor_tags")


class Badge(Base):
    """Badge definition (seeded at startup)."""
    __tablename__ = "badges"

    slug = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    emoji = Column(String, nullable=False)
    category = Column(String, default="general")  # general, style, taste, milestone


class UserBadge(Base):
    """Junction: which users have earned which badges."""
    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_slug", name="uq_user_badge"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    badge_slug = Column(String, ForeignKey("badges.slug"), nullable=False, index=True)
    awarded_at = Column(DateTime(timezone=True), server_default=func.now())

    badge = relationship("Badge")


class Journey(Base):
    """A curated multi-step whiskey exploration path."""
    __tablename__ = "journeys"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)  # "bourbon", "scotch", "exploration", etc.
    difficulty = Column(String, default="beginner")  # beginner, intermediate, advanced
    bottle_count = Column(Integer, default=0)
    image_emoji = Column(String, default="\U0001f943")

    steps = relationship("JourneyStep", back_populates="journey", order_by="JourneyStep.step_number")


class JourneyStep(Base):
    """A single step within a journey."""
    __tablename__ = "journey_steps"

    id = Column(Integer, primary_key=True, index=True)
    journey_id = Column(Integer, ForeignKey("journeys.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_text = Column(Text)
    tasting_prompt = Column(Text)

    journey = relationship("Journey", back_populates="steps")
    whiskey = relationship("Whiskey")


class UserJourneyProgress(Base):
    """Tracks a user's progress through a journey."""
    __tablename__ = "user_journey_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "journey_id", name="uq_user_journey"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    journey_id = Column(Integer, ForeignKey("journeys.id"), nullable=False, index=True)
    current_step = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    journey = relationship("Journey")


class Follow(Base):
    """Social graph: user following another user."""
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follow"),
    )

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(String, nullable=False, index=True)   # username of the follower
    following_id = Column(String, nullable=False, index=True)  # username being followed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WatchlistItem(Base):
    """User watching a whiskey for activity alerts."""
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("username", "whiskey_id", name="uq_watchlist"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class WatchlistAlert(Base):
    """In-app notification (watchlist activity, follows, etc.)."""
    __tablename__ = "watchlist_alerts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    alert_type = Column(String, nullable=False, default="watchlist", index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=True, index=True)
    from_username = Column(String, nullable=True)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class PriceEnrichmentLog(Base):
    """Tracks how each whiskey price was determined for audit and rollback."""
    __tablename__ = "price_enrichment_log"

    id = Column(Integer, primary_key=True, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), unique=True, nullable=False)
    method = Column(String, nullable=False)       # exact_match, fuzzy_match, cross_ref, web_lookup, statistical
    confidence = Column(Float, nullable=False)     # 0.0 to 1.0
    source_detail = Column(String)                 # e.g. "matched: Ardbeg 10 (id=1234)" or "wine-searcher"
    original_price = Column(Float)                 # price before enrichment (for rollback)
    enriched_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Video ────────────────────────────────────────────────────────────────


class Video(Base):
    """A short-form video post (whiskey content, store visits, tastings)."""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String)
    description = Column(Text)
    video_path = Column(String, nullable=False)       # relative: "videos/<uuid>.mp4"
    thumbnail_path = Column(String)                    # relative: "videos/thumbs/<uuid>.jpg"
    duration_seconds = Column(Float)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), index=True)
    location_name = Column(String)                     # freeform location text
    price_tag = Column(Float)                          # optional price shown in video
    view_count = Column(Integer, default=0)
    is_sponsored = Column(Boolean, default=False)
    sponsor_label = Column(String)                     # e.g. "Sponsored by Maker's Mark"
    status = Column(String, default="active")          # active, removed, under_review
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")
    toasts = relationship("VideoToast", back_populates="video", cascade="all, delete-orphan")
    comments = relationship("VideoComment", back_populates="video", cascade="all, delete-orphan")


class VideoToast(Base):
    """A 'like' on a video — mirrors the Toast model pattern."""
    __tablename__ = "video_toasts"
    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_video_toast"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="toasts")


class VideoComment(Base):
    """A comment on a video."""
    __tablename__ = "video_comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video", back_populates="comments")


# ── Monetization ─────────────────────────────────────────────────────────


class AffiliateClick(Base):
    """Tracks clicks on buy links for commission/affiliate reporting."""
    __tablename__ = "affiliate_clicks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)               # nullable for anonymous
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    retailer = Column(String, nullable=False)
    clicked_at = Column(DateTime(timezone=True), server_default=func.now())
    source = Column(String, default="detail")           # detail, video, feed, search
    converted = Column(Boolean, default=False)
    commission_amount = Column(Float)


class UserSubscription(Base):
    """Premium subscription tracking."""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    tier = Column(String, nullable=False, default="premium")
    status = Column(String, nullable=False, default="active")  # active, canceled, expired
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    payment_provider = Column(String)                   # stripe, apple, etc.
    external_id = Column(String)                        # provider subscription ID


class SponsoredPlacement(Base):
    """A paid placement for a whiskey/brand in feeds, browse, or video sections."""
    __tablename__ = "sponsored_placements"

    id = Column(Integer, primary_key=True, index=True)
    advertiser_name = Column(String, nullable=False)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), index=True)
    placement_type = Column(String, nullable=False)     # feed, browse, video_slot, search
    title = Column(String)
    description = Column(Text)
    image_url = Column(String)
    link_url = Column(String)
    priority = Column(Integer, default=0)
    impression_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    starts_at = Column(DateTime(timezone=True))
    ends_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class PriceAlert(Base):
    """User subscribes to price drop notifications for a whiskey."""
    __tablename__ = "price_alerts"
    __table_args__ = (
        UniqueConstraint("username", "whiskey_id", name="uq_price_alert"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    target_price = Column(Float)               # alert when price drops below this (nullable = any drop)
    original_price = Column(Float)             # price when alert was created
    triggered = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class StripeEvent(Base):
    """Webhook event log for idempotency."""
    __tablename__ = "stripe_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Streaks & Challenges ──────────────────────────────────────────────────


class UserStreak(Base):
    """Tracks daily engagement streaks per user."""
    __tablename__ = "user_streaks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username"), unique=True, nullable=False)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_active_date = Column(String, nullable=True)  # ISO date string (YYYY-MM-DD)


class Challenge(Base):
    """Monthly community challenges for engagement."""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    challenge_type = Column(String, nullable=False)  # rate_category, rate_count, explore_region
    goal_count = Column(Integer, nullable=False, default=4)
    filters_json = Column(Text, nullable=True)  # JSON string e.g. {"category":"bourbon"}
    image_emoji = Column(String, default="🏆")
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)


class UserChallengeProgress(Base):
    """Per-user progress on a challenge."""
    __tablename__ = "user_challenge_progress"
    __table_args__ = (UniqueConstraint("user_id", "challenge_id", name="uq_user_challenge"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    progress_count = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    challenge = relationship("Challenge", lazy="joined")


# ── Password Reset & Email ────────────────────────────────────────────────


class PasswordResetToken(Base):
    """Secure password reset tokens (SHA-256 hashed)."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username"), nullable=False)
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmailPreference(Base):
    """Per-user email opt-in/out preferences."""
    __tablename__ = "email_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username"), unique=True, nullable=False)
    weekly_digest = Column(Boolean, default=True)
    re_engagement = Column(Boolean, default=True)
    onboarding_drip = Column(Boolean, default=True)
    marketing = Column(Boolean, default=True)
    push_social = Column(Boolean, default=True)
    push_price_drop = Column(Boolean, default=True)
    push_streak = Column(Boolean, default=True)
    push_weekly = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmailLog(Base):
    """Audit trail for all emails sent."""
    __tablename__ = "email_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username"), nullable=True)
    email_type = Column(String, nullable=False)  # welcome, reset, digest, re_engagement, drip
    subject = Column(String, nullable=True)
    ses_message_id = Column(String, nullable=True)
    status = Column(String, default="sent")  # sent, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PushSubscription(Base):
    """Browser push subscription endpoint per user per device."""
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_push_sub"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.username", ondelete="CASCADE"),
                     nullable=False, index=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)


# ── Top Lists ────────────────────────────────────────────────────────────


class TopList(Base):
    """A curated or dynamic ranked list of whiskeys."""
    __tablename__ = "top_lists"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    list_type = Column(String, nullable=False, default="dynamic")  # curated | dynamic
    category = Column(String, index=True)
    filters_json = Column(Text)  # JSON: {"max_price": 50, "min_rating": 4.0, ...}
    image_emoji = Column(String, default="\U0001f3c6")
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("TopListItem", back_populates="top_list",
                         order_by="TopListItem.rank", cascade="all, delete-orphan")


class TopListItem(Base):
    """A whiskey entry in a curated top list."""
    __tablename__ = "top_list_items"

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("top_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    note = Column(Text)

    top_list = relationship("TopList", back_populates="items")
    whiskey = relationship("Whiskey")



# ── User-Created Lists ───────────────────────────────────────────────


class UserList(Base):
    __tablename__ = "user_lists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship(
        "UserListItem",
        back_populates="user_list",
        order_by="UserListItem.position",
        cascade="all, delete-orphan",
    )


class UserListItem(Base):
    __tablename__ = "user_list_items"
    __table_args__ = (
        UniqueConstraint("list_id", "whiskey_id", name="uq_userlist_whiskey"),
    )

    id = Column(Integer, primary_key=True, index=True)
    list_id = Column(Integer, ForeignKey("user_lists.id", ondelete="CASCADE"), nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    note = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    user_list = relationship("UserList", back_populates="items")
    whiskey = relationship("Whiskey")


# ── Critic / Expert Scores ───────────────────────────────────────────


class CriticScore(Base):
    __tablename__ = "critic_scores"
    __table_args__ = (
        UniqueConstraint("whiskey_id", "source", name="uq_critic_whiskey_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(100), nullable=False, index=True)
    source_display = Column(String(200), nullable=False)
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False, default=100)
    review_year = Column(Integer)
    review_text = Column(Text)
    url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    whiskey = relationship("Whiskey")

# ── AI Response Cache ─────────────────────────────────────────────────


class AICache(Base):
    """Cache for AI-generated responses to avoid repeated API calls."""
    __tablename__ = "ai_cache"
    __table_args__ = (
        UniqueConstraint("cache_key", name="uq_ai_cache_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, nullable=False, index=True)  # e.g. "tasting_notes:42"
    response_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Analytics ────────────────────────────────────────────────────────────


class AnalyticsEvent(Base):
    """Server-side analytics: one row per API request."""
    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id = Column(String, index=True)
    ip_hash = Column(String(64))
    session_hash = Column(String(64), index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    route_pattern = Column(String(200))
    status_code = Column(Integer)
    response_time_ms = Column(Integer)
    user_agent = Column(String(500))
    referrer = Column(String(500))


class UserAction(Base):
    """Explicit user action tracking for funnel analysis and feature adoption."""
    __tablename__ = "user_actions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id = Column(String, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    detail_json = Column(Text, default="{}")
    whiskey_id = Column(Integer, index=True)
    category = Column(String(50))