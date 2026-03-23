import asyncio
import json
import os
import time
import logging
from collections import defaultdict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()  # loads backend/.env into os.environ before anything else runs

_ENV = os.getenv("SIPSENSE_ENV", "development").lower()


# ── Structured logging for staging/production ────────────────────────────
# JSON logs are easy to search in CloudWatch, journald, or with jq.
# Local dev keeps human-readable format.
class _JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


if _ENV in ("staging", "production"):
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JSONFormatter())
    logging.root.handlers = [_handler]
    logging.root.setLevel(logging.INFO)

from .database import engine, Base
from .routers import whiskeys, recommendations, quiz, favorites, chat, learn, flights, gift, palate, compare, stores, auth, trending, pairings, collection, personality, blindtasting, daily, feed, social, ai_features, journal, sharecard, journeys, watchlist, discover, videos, affiliate, subscription, sponsored

logger = logging.getLogger(__name__)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

# Seed badge definitions
from .badges import seed_badges
from .database import SessionLocal
_seed_db = SessionLocal()
try:
    seed_badges(_seed_db)
finally:
    _seed_db.close()

app = FastAPI(
    title="SipSense API",
    description="AI-powered whiskey recommendation engine",
    version="0.2.0",
)

# ── Rate limiting middleware ──────────────────────────────────────────────
# Simple in-memory rate limiter: max requests per IP per window.
# NOTE: Not shared across workers — each gunicorn worker has its own bucket.
# TODO: For production with multiple workers, replace with Redis-backed
# rate limiting (e.g., slowapi with Redis backend) so limits are enforced globally.

def _safe_int(env_key: str, default: int) -> int:
    try:
        return int(os.getenv(env_key, str(default)))
    except (ValueError, TypeError):
        logger.warning("Invalid %s value, using default %d", env_key, default)
        return default

RATE_LIMIT_WINDOW = _safe_int("RATE_LIMIT_WINDOW", 60)   # seconds
RATE_LIMIT_MAX = _safe_int("RATE_LIMIT_MAX", 300)         # requests per window per IP
_RATE_CLEANUP_INTERVAL = 300  # purge stale IPs every 5 minutes
_RATE_MAX_BUCKETS = 10_000  # cap tracked IPs to prevent memory exhaustion
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_last_cleanup = time.time()
_rate_lock = asyncio.Lock()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    global _last_cleanup
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    async with _rate_lock:
        # Prune old entries for this IP
        _rate_buckets[client_ip] = [t for t in _rate_buckets[client_ip] if t > window_start]

        # Periodically purge stale IPs to prevent memory leak
        if now - _last_cleanup > _RATE_CLEANUP_INTERVAL:
            stale = [ip for ip, ts in _rate_buckets.items() if not ts or ts[-1] < window_start]
            for ip in stale:
                del _rate_buckets[ip]
            _last_cleanup = now

        # Cap total tracked IPs to prevent memory exhaustion under DDoS
        if len(_rate_buckets) > _RATE_MAX_BUCKETS:
            sorted_ips = sorted(
                _rate_buckets.items(),
                key=lambda kv: kv[1][-1] if kv[1] else 0,
            )
            for ip, _ in sorted_ips[: len(_rate_buckets) - _RATE_MAX_BUCKETS]:
                del _rate_buckets[ip]

        if len(_rate_buckets[client_ip]) >= RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
            )

        _rate_buckets[client_ip].append(now)

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"

    return response


# Allow the React dev server (and production origins) to call this API
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth.router)
app.include_router(whiskeys.router)
app.include_router(recommendations.router)
app.include_router(quiz.router)
app.include_router(favorites.router)
app.include_router(chat.router)
app.include_router(learn.router)
app.include_router(flights.router)
app.include_router(gift.router)
app.include_router(palate.router)
app.include_router(compare.router)
app.include_router(stores.router)
app.include_router(trending.router)
app.include_router(pairings.router)
app.include_router(collection.router)
app.include_router(personality.router)
app.include_router(blindtasting.router)
app.include_router(daily.router)
app.include_router(feed.router)
app.include_router(social.router)
app.include_router(ai_features.router)
app.include_router(journal.router)
app.include_router(sharecard.router)
app.include_router(journeys.router)
app.include_router(watchlist.router)
app.include_router(discover.router)
app.include_router(videos.router)
app.include_router(affiliate.router)
app.include_router(subscription.router)
app.include_router(sponsored.router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "environment": _ENV, "version": "0.2.0"}


@app.get("/health", tags=["health"])
def health_check():
    """Detailed health check — returns 503 if any dependency is down."""
    checks = {"api": "ok"}
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = "error: unavailable"
        logger.error(f"Health check DB error: {e}")
    finally:
        db.close()

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "degraded",
            "environment": _ENV,
            "checks": checks,
        },
    )


# Serve uploaded files (bottle images, rating photos, etc.)
_uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")
