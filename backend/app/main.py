import time
import logging
from collections import defaultdict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
load_dotenv()  # loads backend/.env into os.environ before anything else runs

from .database import engine, Base
from .routers import whiskeys, recommendations, quiz, favorites, chat, learn, flights, gift, palate, compare, stores, auth, trending, pairings, collection, personality, blindtasting, daily, feed, social, ai_features

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
# For production, swap for Redis-backed (e.g. slowapi).

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 120    # requests per window per IP
_rate_buckets: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    # Prune old entries
    _rate_buckets[client_ip] = [t for t in _rate_buckets[client_ip] if t > window_start]

    if len(_rate_buckets[client_ip]) >= RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    _rate_buckets[client_ip].append(now)
    response = await call_next(request)
    return response


# Allow the React dev server (and production origins) to call this API
import os
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "message": "Welcome to SipSense"}
