from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Boolean, UniqueConstraint
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



class Whiskey(Base):
    __tablename__ = "whiskeys"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    distillery = Column(String, nullable=False)
    category = Column(String, nullable=False)  # bourbon, scotch, irish, japanese, rye, etc.
    region = Column(String)                     # e.g. Speyside, Kentucky, Islay
    age = Column(Integer)                       # age in years, nullable for NAS
    abv = Column(Float, nullable=False)         # alcohol by volume %
    price_usd = Column(Float)
    description = Column(Text)
    flavor_profile = Column(Text)               # comma-separated tags: smoky, sweet, fruity, etc.
    rating_avg = Column(Float, default=0.0)     # may include ratings from external sources
    rating_count = Column(Integer, default=0)    # user ratings on this platform only; 0 with
                                                  # rating_avg > 0 means external-source rating
    upc = Column(String, index=True)            # barcode from OpenFoodFacts — enables label scan
    source = Column(String, default="manual")   # "ttb", "distiller", "wikidata", "openfoodfacts", etc.

    ratings = relationship("UserRating", back_populates="whiskey")


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class UserRating(Base):
    __tablename__ = "user_ratings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)  # simple string ID for now
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), nullable=False)
    score = Column(Float, nullable=False)  # 1.0 to 5.0
    notes = Column(Text)
    serving_style = Column(String)  # neat, rocks, cocktail, highball
    location_note = Column(String)  # freeform: "The Macallan Bar, NYC"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey", back_populates="ratings")
    toasts = relationship("Toast", back_populates="rating", cascade="all, delete-orphan")


class UserMemory(Base):
    """Persistent memory of a user's whiskey preferences, extracted from conversations."""
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    # JSON blob: {likes: [], dislikes: [], budget: "", style: "", notes: ""}
    preferences = Column(Text, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CollectionItem(Base):
    """A bottle in a user's personal shelf/collection."""
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), nullable=False)
    status = Column(String, default="sealed")  # sealed, opened, finished
    purchase_price = Column(Float)
    purchase_location = Column(String)
    personal_notes = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    whiskey = relationship("Whiskey")


class LiquorStore(Base):
    __tablename__ = "liquor_stores"

    id = Column(Integer, primary_key=True, index=True)
    osm_id = Column(Integer, unique=True, nullable=False, index=True)
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
    store_id = Column(Integer, ForeignKey("liquor_stores.id"), nullable=False)
    whiskey_id = Column(Integer, ForeignKey("whiskeys.id"), nullable=False)
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
    rating_id = Column(Integer, ForeignKey("user_ratings.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("UserRating", back_populates="toasts")


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