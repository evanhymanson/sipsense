import logging
import os
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(_BASE_DIR, 'sipsense.db')}"
)

_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread=False; PostgreSQL doesn't use it
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

_pool_kwargs = {} if _is_sqlite else {"pool_size": 10, "max_overflow": 20, "pool_recycle": 3600}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    **_pool_kwargs,
)


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        """Enable WAL mode and other performance pragmas for SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _run_migrations():
    """Add any columns that exist in models but are missing from the actual DB.
    SQLAlchemy's create_all() only creates new tables, not new columns."""
    import sqlalchemy as sa
    with engine.connect() as conn:
        inspector = sa.inspect(engine)
        if "users" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("users")}
            if "is_premium" not in existing:
                conn.execute(sa.text("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0"))
            if "premium_until" not in existing:
                conn.execute(sa.text("ALTER TABLE users ADD COLUMN premium_until DATETIME"))
            conn.commit()
        if "whiskeys" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("whiskeys")}
            if "price_is_estimated" not in existing:
                conn.execute(sa.text(
                    "ALTER TABLE whiskeys ADD COLUMN price_is_estimated BOOLEAN DEFAULT 0"
                ))
                conn.commit()
            if "created_at" not in existing:
                conn.execute(sa.text(
                    "ALTER TABLE whiskeys ADD COLUMN created_at DATETIME"
                ))
                conn.execute(sa.text(
                    "UPDATE whiskeys SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
                ))
                conn.commit()
        if "watchlist_alerts" in inspector.get_table_names():
            existing = {c["name"] for c in inspector.get_columns("watchlist_alerts")}
            if "alert_type" not in existing:
                conn.execute(sa.text(
                    "ALTER TABLE watchlist_alerts ADD COLUMN alert_type VARCHAR NOT NULL DEFAULT 'watchlist'"
                ))
            if "from_username" not in existing:
                conn.execute(sa.text(
                    "ALTER TABLE watchlist_alerts ADD COLUMN from_username VARCHAR"
                ))
            conn.commit()
        # Upgrade osm_id from INTEGER to BIGINT for large OSM node IDs (PostgreSQL only;
        # SQLite INTEGER already supports 64-bit values natively)
        if not _is_sqlite and "liquor_stores" in inspector.get_table_names():
            for col in inspector.get_columns("liquor_stores"):
                if col["name"] == "osm_id" and str(col["type"]) == "INTEGER":
                    conn.execute(sa.text(
                        "ALTER TABLE liquor_stores ALTER COLUMN osm_id TYPE BIGINT"
                    ))
                    conn.commit()
                    break

_run_migrations()


def _ensure_indexes():
    """Create indexes on foreign key columns for existing databases.
    New databases get them automatically via create_all(), but existing ones need this."""
    import sqlalchemy as sa
    _indexes = [
        ("idx_userfav_whiskey", "user_favorites", "whiskey_id"),
        ("idx_userfav_user", "user_favorites", "user_id"),
        ("idx_userrating_whiskey", "user_ratings", "whiskey_id"),
        ("idx_userrating_user", "user_ratings", "user_id"),
        ("idx_collection_whiskey", "collection_items", "whiskey_id"),
        ("idx_collection_user", "collection_items", "user_id"),
        ("idx_storeavail_store", "store_availability", "store_id"),
        ("idx_storeavail_whiskey", "store_availability", "whiskey_id"),
        ("idx_journeystep_journey", "journey_steps", "journey_id"),
        ("idx_journeystep_whiskey", "journey_steps", "whiskey_id"),
        ("idx_userjprog_journey", "user_journey_progress", "journey_id"),
        ("idx_watchlist_whiskey", "watchlist_items", "whiskey_id"),
        ("idx_watchlist_user", "watchlist_items", "user_id"),
        ("idx_watchalert_whiskey", "watchlist_alerts", "whiskey_id"),
        ("idx_watchalert_user", "watchlist_alerts", "user_id"),
        ("idx_watchalert_type", "watchlist_alerts", "alert_type"),
        ("idx_video_whiskey", "videos", "whiskey_id"),
        ("idx_video_user", "videos", "user_id"),
        ("idx_affclick_whiskey", "affiliate_clicks", "whiskey_id"),
        ("idx_sponsored_whiskey", "sponsored_placements", "whiskey_id"),
        ("idx_follow_follower", "follows", "follower_id"),
        ("idx_follow_following", "follows", "following_id"),
        ("idx_toast_rating", "toasts", "rating_id"),
        ("idx_toast_user", "toasts", "user_id"),
        ("idx_userrating_created", "user_ratings", "created_at"),
        ("idx_userfav_created", "user_favorites", "created_at"),
        ("idx_whiskey_rating_avg", "whiskeys", "rating_avg"),
        # Analytics
        ("idx_analytics_timestamp", "analytics_events", "timestamp"),
        ("idx_analytics_user", "analytics_events", "user_id"),
        ("idx_analytics_session", "analytics_events", "session_hash"),
        ("idx_analytics_path", "analytics_events", "path"),
        ("idx_actions_timestamp", "user_actions", "timestamp"),
        ("idx_actions_user", "user_actions", "user_id"),
        ("idx_actions_action", "user_actions", "action"),
        ("idx_actions_whiskey", "user_actions", "whiskey_id"),
    ]
    # Composite indexes for common query patterns (e.g. feed: WHERE user_id=? ORDER BY created_at DESC)
    _composite_indexes = [
        ("idx_userrating_user_created", "user_ratings", "user_id, created_at DESC"),
    ]
    with engine.connect() as conn:
        for idx_name, table, columns in _composite_indexes:
            try:
                conn.execute(sa.text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})"
                ))
            except Exception as e:
                logger.debug(f"Composite index {idx_name} on {table}: {e}")
        for idx_name, table, column in _indexes:
            try:
                conn.execute(sa.text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"
                ))
            except Exception as e:
                logger.debug(f"Index {idx_name} on {table}: {e}")
        conn.commit()


_ensure_indexes()


# ── Slow query detection ─────────────────────────────────────────────────
_SLOW_QUERY_THRESHOLD_MS = float(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500"))


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["_query_start"] = time.perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start = conn.info.pop("_query_start", None)
    if start is None:
        return
    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > _SLOW_QUERY_THRESHOLD_MS:
        logger.warning("SLOW QUERY (%.0fms): %s", elapsed_ms, statement[:500])


def get_db():
    """Dependency that provides a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()