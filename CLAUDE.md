# SipSense

AI-powered whiskey discovery app. Rate, review, and explore whiskeys with ML recommendations and an AI chat agent. Live at **sipsense.ai**.

---

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL 16 (prod) / SQLite (dev), Gunicorn
- **Frontend:** React 19, Vite 7, React Router v7, Leaflet (maps)
- **ML/AI:** PyTorch NCF recommender, LangGraph + Claude chat agent, Claude API (tasting notes, pairings, flavor analysis)
- **Infra:** Docker Compose, GitHub Actions CI/CD, AWS EC2, nginx (SSL), S3 (image storage), Sentry (error tracking)

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app, middleware, router registration
    models.py            # SQLAlchemy ORM (30+ tables)
    schemas.py           # Pydantic v2 request/response models
    database.py          # DB setup, auto-migration, indexing
    auth.py              # JWT auth (HS256 + bcrypt)
    routers/             # 30+ API routers (116+ endpoints)
    ml/
      collaborative_filter.py  # NCF PyTorch model
      recommender.py           # Content-based fallback (cosine similarity)
      agent.py                 # LangGraph chat agent with tools
      model.pt                 # Trained model weights
  tests/                 # pytest suite (20+ test files)

frontend/
  src/
    App.jsx              # Router, auth state, layout
    App.css              # Single global stylesheet (all styles here)
    api/client.js        # Centralized API client (JWT, dedup, retry)
    pages/               # 15 lazy-loaded pages
    components/          # 27+ reusable components
    utils/               # Helpers (stars, analytics)

.github/workflows/
  ci.yml                 # Tests + lint + build on PRs
  deploy.yml             # Auto-deploy to EC2 on merge to main
```

## Local Development

```bash
# Full stack via Docker
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build

# Backend only (for development)
cd backend && pip install -r requirements.txt
SIPSENSE_ENV=development python -m uvicorn app.main:app --reload

# Frontend only (for development)
cd frontend && npm install && npm run dev
```

## Testing

```bash
# Backend (pytest, 50% coverage minimum)
cd backend && python -m pytest tests/ -v --cov=app --cov-fail-under=50

# Frontend (vitest + eslint)
cd frontend && npm test && npm run lint
```

CI runs both on every PR and push to main.

## Key Patterns

- API routes prefixed with `/api` — frontend client adds this automatically
- JWT auth via Bearer tokens stored in localStorage (`sipsense_token`)
- Pydantic v2 schemas validate all request/response data
- SQLAlchemy 2.0 ORM with auto-migration for new columns in `database.py`
- React pages are lazy-loaded via `React.lazy()` + `Suspense`
- All CSS lives in `App.css` — no CSS-in-JS, no CSS modules
- API client (`api/client.js`) deduplicates concurrent GET requests and handles token refresh
- Sentry integrated on both frontend and backend for error tracking
- Rate limiting: 300 requests/60s per IP

## Database

- **Production:** PostgreSQL 16 in Docker with persistent volume
- **Development:** SQLite with WAL mode (auto-detected)
- **Migrations:** Alembic + custom auto-migration in `database.py` that adds missing columns/indexes on startup
- **Key tables:** users, whiskeys, user_ratings (check-ins), follows, toasts, checkin_comments, collection_items, videos, journeys, badges, analytics_events

## What This App Does

SipSense is a whiskey discovery and social platform. Users browse a catalog of 1000+ whiskeys, rate bottles ("check-ins"), get AI-powered personalized recommendations, and engage with a community of whiskey enthusiasts. Think Untappd/Vivino but for whiskey, with a built-in AI sommelier.

## User Flow

1. **Land** on `/` (Browse) — search/filter the whiskey catalog, no login required
2. **Register** at `/onboarding` — single form handles register, login, forgot/reset password
3. **Taste Quiz** at `/quiz` — 6 everyday-analogy questions (coffee strength, chocolate pref, smoke pref, dessert, budget, style) → maps to flavor vector → returns 6 personalized recommendations. Also accessible without login for SEO
4. **Browse & Discover** — filter by category/region/flavor/price/ABV, sort by rating/price/age, compare bottles side-by-side, view trending whiskeys
5. **Whiskey Detail** at `/whiskey/:id` — the richest page: bottle info, flavor map, AI tasting notes (nose/palate/finish), food pairings, cocktails, buy links, store locator map, critic scores, similar bottles, all reviews, check-in form
6. **Check In** — rate 1-5 stars with notes, serving style, location, optional photo. After submitting: earn badges, update streak, track challenge progress, get a post-check-in recommendation
7. **Discover** at `/discover` — daily featured bottle, streak tracker, daily knowledge quiz, community challenges
8. **Profile** at `/me` — 6 tabs: Palate stats, For You recs, Favorites, Collection shelf, Journal timeline, Badges. Shows personality archetype and palate evolution
9. **Social** — follow users, activity feed at `/feed`, toast (like) and comment on check-ins, TikTok-style video feed at `/videos`
10. **AI Chat** — floating sidebar on all pages, LangGraph agent with 20+ tools, SSE streaming with rich UI (whiskey cards, maps, comparison tables, flights)

## Core Features

### Discovery & Browsing
- Full catalog with text search, multi-filter (category, region, flavor, ABV, price), sort options
- **Flavor map** — 2D scatter plot (Sweet/Smoky x Light/Bold), each whiskey plotted by flavor tag coordinates
- **Daily Discovery** — one featured bottle per day (deterministic by date hash)
- **Taste quiz** — cold-start onboarding, maps answers to cosine-similarity recommendations
- **Tasting flights** — themed 3-5 bottle progressions (beginner, smoky journey, bourbon ladder, scotch regions, world tour)
- **Blind tasting** — 3 difficulty levels, strips bottle identity, user guesses from clues
- **Trending** — most-active whiskeys in recent window
- **Compare drawer** — select 2 bottles for side-by-side comparison with winner highlighting

### Rating & Check-ins
- 1-5 star ratings with tasting notes, serving style, location, optional photo
- Post-check-in flow: new badges, streak update, challenge progress, recommendation
- Helpful votes on reviews, flavor tags per review

### AI & ML
- **NCF recommender** (`ml/collaborative_filter.py`) — PyTorch neural collaborative filtering (32-dim embeddings, MLP tower), falls back to content-based
- **Content-based recommender** (`ml/recommender.py`) — cosine similarity over feature vectors (category, ABV, age, price, 16 flavor tags)
- **Personal match scores** — per-whiskey % match via cosine similarity, batched up to 50 at a time
- **AI tasting notes** — Claude generates nose/palate/finish/overall, cached in `AICache`
- **AI palate summary** — Claude writes a narrative about user's taste history
- **Bottle scan** — photo → Claude vision identifies whiskey; also UPC barcode lookup
- **Chat agent** (`ml/agent.py`) — LangGraph ReAct agent with `claude-sonnet-4-5`, 20+ tools (search, recommend, compare, rate, remember preferences, find stores, build flights, gift finder, etc.), SSE streaming with rich UI rendering (whiskey cards with buy CTAs, Leaflet maps, comparison tables, flight visualizations, radar charts)
- **Chat memory** — `UserMemory` stores persistent preferences (JSON blob), `ConversationSummary` stores session summaries, both injected into system prompt

### Social
- Follow/unfollow users, suggested follows
- Activity feed at `/feed` with category filtering and friends-only mode
- **Toasts** (likes) on check-ins and videos
- Comments on check-ins and videos
- **Video feed** at `/videos` — TikTok-style vertical scroll, auto-play, upload support

### Personal
- **Collection shelf** — track bottles as Sealed/Opened/Finished with purchase details
- **Favorites** — wishlist-style saves
- **Watchlist** with price alerts (email via AWS SES when price drops)
- **Journeys** — multi-step guided tasting paths with lesson text and progress tracking
- **Badges** — gamification milestones (emoji, name, description, category)
- **Streaks** — daily engagement streak (heartbeat/quiz completion)
- **Challenges** — monthly community goals ("rate 4 bourbons") with progress tracking and leaderboard
- **Personality archetype** — e.g. "The Campfire Poet", "The Smooth Operator", based on rating patterns
- **Palate evolution** — monthly flavor trend snapshots, percentile ranking vs all users

### Commerce & Content
- **Affiliate buy links** on detail pages, in chat, and after check-ins
- **Premium subscription** via Stripe (checkout session, webhook handler)
- **Sponsored placements** in feed, browse, video, search
- **Gift finder** — recommend a bottle by recipient's drink preference, budget, occasion
- **Share cards** — server-side PNG generation (Pillow) for social sharing
- **Learn hub** at `/learn` — category guides, distillery stories, glossary
- **Top lists** and **user-created lists**

## Key Data Models

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | Account with username, email, hashed_password, quiz_completed, is_premium |
| `Whiskey` | `whiskeys` | Catalog entry: name, distillery, category, region, age, abv, price_usd, flavor_profile, flavor_x/flavor_y (map coords), buy_links (JSON), upc |
| `UserRating` | `user_ratings` | Check-in: user_id, whiskey_id, score (1-5), notes, serving_style, location_note, image_path. Unique per (user, whiskey) |
| `Follow` | `follows` | Social graph: follower_id → following_id (usernames) |
| `Toast` | `toasts` | Like on a check-in. Unique per (user, rating) |
| `CollectionItem` | `collection_items` | Personal shelf: status (sealed/opened/finished), purchase_price |
| `UserFavorite` | `user_favorites` | Wishlist save: user_id + whiskey_id |
| `Video` | `videos` | Short-form video post with whiskey_id, view_count, is_sponsored |
| `Journey` / `JourneyStep` | `journeys` / `journey_steps` | Multi-step tasting paths with lessons |
| `Badge` / `UserBadge` | `badges` / `user_badges` | Gamification awards |
| `UserMemory` | `user_memories` | Persistent chat preferences (JSON blob) |
| `AICache` | `ai_cache` | Cached AI responses keyed by e.g. `v1:tasting_notes:42` |
| `AnalyticsEvent` | `analytics_events` | Per-request logging: path, method, user, response_time_ms, status_code |

## API Routers

All in `backend/app/routers/`, all prefixed with `/api` at the app level.

| Router | Prefix | Purpose |
|---|---|---|
| `auth.py` | `/auth` | Register, login, refresh, forgot/reset password, `/me` |
| `whiskeys.py` | `/whiskeys` | Catalog CRUD, search/filter, ratings, favorites, collection, watchlist, buy links |
| `recommendations.py` | `/recommendations` | NCF → content-based fallback recs, 5-min TTL cache |
| `quiz.py` | `/quiz` | Taste quiz submission → 6 recommendations with reasons |
| `ai_features.py` | — | AI tasting notes, palate summary, bottle scan, explained recs |
| `chat.py` | `/chat` | SSE streaming chat, conversation summarizer |
| `palate.py` | `/palate` | User palate stats, palate match scores |
| `taste_identity.py` | `/taste-identity` | Palate evolution, percentile ranking, daily quiz |
| `matchscores.py` | `/match-scores` | Batch match scores for up to 50 whiskeys |
| `personality.py` | `/personality` | Whiskey personality archetype |
| `daily.py` | `/daily` | Today's Daily Discovery bottle |
| `discover.py` | `/discover` | Knowledge graph nodes/links |
| `trending.py` | `/trending` | Most-active whiskeys |
| `social.py` | — | Toasts, helpful votes, comments, follow/unfollow, profiles |
| `feed.py` | `/feed` | Activity feed (paginated, filterable) |
| `journeys.py` | `/journeys` | Journey CRUD and progress tracking |
| `challenges.py` | `/challenges` | Active challenges, join, leaderboard |
| `streaks.py` | `/streaks` | Current streak, heartbeat |
| `flights.py` | `/flights` | Themed tasting flights |
| `blindtasting.py` | `/blind-tasting` | Blind challenge generation and guess submission |
| `compare.py` | `/compare` | Side-by-side whiskey comparison |
| `pairings.py` | — | Food pairings and cocktail suggestions |
| `stores.py` | `/stores` | Nearby liquor stores (Overpass API + cache) |
| `videos.py` | `/videos` | Video feed, upload, toasts, comments |
| `collection.py` | `/collection` | Personal bottle shelf |
| `favorites.py` | `/favorites` | Add/remove/list favorites |
| `watchlist.py` | `/watchlist` | Watchlist management |
| `price_alerts.py` | `/price-alerts` | Price drop alert subscriptions |
| `toplists.py` | `/toplists` | Curated/dynamic ranked lists |
| `userlists.py` | `/user-lists` | User-created custom lists |
| `critics.py` | `/critics` | Professional critic scores |
| `journal.py` | — | Photo upload, journal timeline |
| `sharecard.py` | `/share` | PNG share card generation |
| `analytics.py` | `/analytics` | Admin-only dashboard data |
| `sponsored.py` | — | Sponsored placement injection |
| `affiliate.py` | — | Affiliate click tracking |
| `subscription.py` | `/subscription` | Premium status and features |
| `stripe_billing.py` | `/billing` | Stripe checkout and webhooks |
| `email_prefs.py` | `/email-prefs` | Email preference management |
| `gift.py` | `/gift` | Gift recommendation |
| `seo.py` | — | sitemap.xml, robots.txt |
| `learn.py` | `/learn` | Category guides, distillery stories, glossary |
| `admin.py` | `/admin` | Admin user management and moderation |

## Auth Tiers

- `get_current_user` — requires valid Bearer token (most endpoints)
- `get_optional_user` — returns user if authenticated, `None` otherwise (browse, detail pages)
- `require_premium` — checks `is_premium=True` and expiry
- `_require_admin` — checks username against `ADMIN_USERS` env var

## Frontend Pages

| Page | Route | Auth | Purpose |
|---|---|---|---|
| `Browse.jsx` | `/` | No | Main catalog with search, filters, carousels, compare |
| `Onboarding.jsx` | `/onboarding` | No | Register/login/forgot/reset password |
| `TasteQuiz.jsx` | `/quiz` | No | 6-question onboarding quiz |
| `WhiskeyDetail.jsx` | `/whiskey/:id` | Optional | Bottle details, reviews, check-in, AI notes, pairings |
| `Discover.jsx` | `/discover` | Yes | Daily Discovery, streak, quiz, challenges |
| `Profile.jsx` | `/me` | Yes | 6-tab personal profile |
| `UserProfile.jsx` | `/user/:username` | Yes | Public profile of another user |
| `Feed.jsx` | `/feed` | Yes | Community activity feed |
| `VideoFeed.jsx` | `/videos` | Yes | TikTok-style video feed |
| `ScanBottle.jsx` | `/scan` | Yes | Label photo scan / UPC lookup |
| `JourneyDetail.jsx` | `/journeys/:slug` | Yes | Multi-step tasting journey |
| `Alerts.jsx` | `/alerts` | Yes | Notification inbox |
| `Premium.jsx` | `/premium` | Yes | Subscription upsell |
| `TopLists.jsx` | `/lists` | No | Curated ranked lists |
| `UserLists.jsx` | `/my-lists` | Yes | Personal custom lists |
| `Learn.jsx` | `/learn` | No | Educational hub |
| `AdminDashboard.jsx` | `/admin` | Admin | Analytics dashboard |

## Key Components

| Component | Purpose |
|---|---|
| `ChatSidebar.jsx` | Floating AI chat, SSE streaming, renders rich UI (cards, maps, tables, flights, charts) |
| `WhiskeyCard.jsx` | Reusable bottle card (image, name, distillery, category, price, rating, match score) |
| `FlavorMap.jsx` | 2D SVG scatter plot (Sweet/Smoky x Light/Bold), clickable dots |
| `CompareDrawer.jsx` | Bottom slide-up side-by-side comparison |
| `CheckInCard.jsx` | Single check-in in feed (rating, notes, photo, toast/comment buttons) |
| `StoreLocator.jsx` | Leaflet map of nearby liquor stores |
| `BadgeGrid.jsx` | Grid of earned badges |
| `PremiumGate.jsx` | Blocks premium-only features with upgrade prompt |
| `WhiskeyJsonLd.jsx` | Schema.org Product structured data for SEO |
| `InstallPrompt.jsx` | PWA "Add to Home Screen" prompt |

---

## Git Workflow (MUST FOLLOW)

**Never commit directly to `main`.** All work goes through feature branches and pull requests.

**CRITICAL: Before writing ANY code or making ANY file changes, you MUST create a new feature branch first.** Do not start editing files while on `main` or on a stale branch. The very first action for any new task is to create a branch. No exceptions.

### For every task:
1. **Create a feature branch FIRST** — before making any changes, before reading code to modify, before anything else:
   ```
   git checkout main && git pull
   git checkout -b feature/<short-description>
   ```
2. **Do the work** — make commits on the feature branch
3. **Push and open a PR**:
   ```
   git push -u origin feature/<short-description>
   gh pr create --title "..." --body "..."
   ```
4. **User reviews and merges** the PR on GitHub
5. **After merge**, switch back to main:
   ```
   git checkout main && git pull
   ```

### Branch naming:
- Features: `feature/<name>` (e.g. `feature/onboarding-redesign`)
- Fixes: `fix/<name>` (e.g. `fix/deploy-secrets`)
- Chores: `chore/<name>` (e.g. `chore/cleanup-env-files`)

### Deploy flow:
- Merging to `main` auto-deploys to **production** (CI tests must pass first)
- Can also manually trigger production deploy via GitHub Actions workflow dispatch

---

## Backend Helper Modules (MUST REUSE)

All in `backend/app/`. Import before reimplementing — these handle cross-cutting concerns.

### File Storage
| Module | Key exports | Purpose |
|---|---|---|
| `storage.py` | `upload_file(local, key, mime)`, `upload_bytes(data, key, mime)`, `make_cdn_url(path)`, `get_nobg_set()` | S3 + CloudFront in prod, local disk in dev. Auto-detects via `S3_BUCKET` env var. Returns CDN URL or `/uploads/...` path |
| `upload_utils.py` | `validate_magic_bytes(content, allowed)`, `validate_file_size(content)`, `sanitize_extension(name, allowed, default)` | File validation: magic byte MIME detection, 10MB limit, prevents double-extension attacks |

### Gamification & Engagement
| Module | Key exports | Purpose |
|---|---|---|
| `badges.py` | `seed_badges(db)`, `evaluate_badges(user_id, db) -> list[Badge]` | 11 badge definitions (milestone/style/taste/streak). Call `evaluate_badges()` after every check-in |
| `levels.py` | `compute_user_level(username, db) -> dict` | 5-level progression (Novice/Enthusiast/Connoisseur/Expert/Master). Points from check-ins (5), unique whiskeys (3), badges (15), helpful votes (2) |
| `streaks.py` | `record_daily_activity(user_id, db) -> dict` | ISO-date streak tracking. Returns `{current_streak, longest_streak, is_new_day}` |
| `challenge_tracker.py` | `update_challenge_progress(user_id, whiskey_id, db) -> list[dict]` | Updates progress on active challenges after check-in. Returns `[{challenge_title, progress, goal, completed}]` |
| `checkin_insights.py` | `generate_checkin_insights(user_id, whiskey_id, score, db) -> list[str]` | Post-check-in contextual insights (1-3 strings). Category counts, score trends, flavor patterns |

### Communication
| Module | Key exports | Purpose |
|---|---|---|
| `email_service.py` | `send_email(to, subject, html, text, user_id, email_type) -> bool` | AWS SES with graceful degradation. Checks `EmailPreference` before sending non-transactional. Logs to `EmailLog` table |
| `email_templates.py` | `weekly_digest_email()`, `welcome_email()`, `password_reset_email()`, `re_engagement_email()`, `drip_email()` | HTML email templates. Each returns `(subject, html_body, text_body)` |
| `push_service.py` | `send_push_notification(user_id, alert_type, title, body, url, tag) -> bool` | VAPID web push. Graceful degradation if not configured. Auto-deactivates revoked subscriptions (410 Gone) |

### Analytics & Tracking
| Module | Key exports | Purpose |
|---|---|---|
| `track.py` | `track_action(db, user_id, action, whiskey_id=, category=, detail=)` | Fire-and-forget user action tracking. Fails silently — analytics never breaks the app. Does NOT commit — piggybacks on caller's transaction |
| `analytics_constants.py` | `ACTION_LOGIN`, `ACTION_RATING`, `ACTION_CHAT_MESSAGE`, `ACTION_WHISKEY_VIEW`, etc. (20+) | String constants for action names. Import these instead of using magic strings |
| `analytics_middleware.py` | auto-registered middleware | Per-request logging (path, method, user, response_time_ms). Configurable sampling rate and IP hashing |

### Background Jobs
| Module | Key exports | Purpose |
|---|---|---|
| `scheduler.py` | `main()` | APScheduler BlockingScheduler. Runs as separate Docker container (`python -m app.scheduler`) |
| `scheduled_jobs.py` | `send_weekly_digests()`, `send_re_engagement_emails()`, `send_drip_emails()`, `send_streak_push_reminders()`, `check_price_alerts()` | 5 scheduled jobs. Each handles errors per-user and uses its own `SessionLocal()` |

### Rate Limiting
| Module | Key exports | Purpose |
|---|---|---|
| `rate_limit.py` | `auth_rate_limit` (dependency) | Progressive backoff: 5 attempts/60s, then 15-min lockout after 15 attempts. Use as FastAPI dependency |

### Seeders (run at startup in `main.py`)
| Module | Purpose |
|---|---|
| `badges.py` → `seed_badges()` | 11 badge definitions |
| `seed_toplists.py` → `seed_toplists()` | Curated "Best Bourbons", "Top Rated" etc. list definitions |
| `seed_critics.py` → `seed_critics()` | Professional critic score definitions |
| `seed_challenges.py` → `seed_challenges()` | Monthly community challenge definitions |

## Environment Variables

### Required
| Variable | Example | Purpose |
|---|---|---|
| `SIPSENSE_ENV` | `development` / `staging` / `production` | Controls DB choice, logging format, Sentry env tag |
| `DATABASE_URL` | `postgresql://sipsense:pw@db:5432/sipsense` | Postgres connection (prod). Omit for SQLite (dev) |
| `JWT_SECRET_KEY` | (random 32+ chars) | HS256 signing key for auth tokens |

### AWS / Storage
| Variable | Purpose |
|---|---|
| `S3_BUCKET` | S3 bucket name (omit for local dev — storage falls back to disk) |
| `CDN_BASE_URL` | CloudFront distribution URL for uploaded files |
| `AWS_REGION` | AWS region (default: `us-east-2`) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM credentials for S3 + SES |

### AI / ML
| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Claude API key for tasting notes, chat, scanning |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Primary model for chat agent |
| `CLAUDE_MODEL_SMALL` | `claude-haiku-4-5-20251001` | Fast model for tasting notes, pairings |

### Email & Push
| Variable | Default | Purpose |
|---|---|---|
| `AWS_SES_REGION` | `us-east-2` | SES region |
| `SES_FROM_EMAIL` | `noreply@sipsense.ai` | Sender address |
| `VAPID_PRIVATE_KEY` | — | VAPID key for web push (omit to disable push) |
| `VAPID_CLAIMS_EMAIL` | `mailto:noreply@sipsense.ai` | Contact email in VAPID claims |

### Stripe
| Variable | Purpose |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe API key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | Webhook endpoint signing secret (`whsec_...`) |
| `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_YEARLY` | Stripe Price IDs for subscription tiers |
| `FRONTEND_URL` | Redirect URL after checkout (default: `https://sipsense.ai`) |

### Analytics & Rate Limiting
| Variable | Default | Purpose |
|---|---|---|
| `ANALYTICS_ENABLED` | `true` | Toggle request analytics |
| `ANALYTICS_SAMPLE_RATE` | `1.0` | Fraction of requests to log (0.0-1.0) |
| `ANALYTICS_RETENTION_DAYS` | `90` | Auto-cleanup old events on startup |
| `ANALYTICS_SALT` | — | Random string for IP anonymization |
| `SLOW_QUERY_THRESHOLD_MS` | `500` | Log slow queries above this threshold |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `RATE_LIMIT_MAX` | `300` | Max requests per IP per window |

### Other
| Variable | Purpose |
|---|---|
| `CORS_ORIGINS` | Comma-separated allowed origins (default: `http://localhost:5173`) |
| `ADMIN_USERS` | Comma-separated admin usernames |
| `SENTRY_DSN` / `VITE_SENTRY_DSN` | Sentry DSN for backend / frontend |

## Post-Check-In Orchestration

When a user rates a whiskey (`POST /api/whiskeys/{id}/rate`), the handler in `routers/whiskeys.py` calls 4 helpers in sequence. If adding new post-check-in logic, add it to this chain:

1. **`generate_checkin_insights(user_id, whiskey_id, score, db)`** — 1-3 contextual insight strings
2. **`record_daily_activity(user_id, db)`** — updates streak counters
3. **`update_challenge_progress(user_id, whiskey_id, db)`** — increments matching challenge progress
4. **`evaluate_badges(user_id, db)`** — checks 11 badge conditions, awards new ones

The response JSON includes `insights`, `streak`, `challenge_updates`, and `badges_earned` fields. Frontend `WhiskeyDetail.jsx` renders all four in a post-check-in modal.

## Testing Patterns

50+ test files in `backend/tests/`. Each router has a matching `test_<name>.py`.

### conftest.py fixtures:
- **`db_session`** — in-memory SQLite, transaction-rolled-back per test (session-scoped engine, per-test transaction)
- **`client`** — FastAPI TestClient with dependency overrides for DB + rate limiters cleared
- **`auth_headers`** — registers "testuser" and returns `{"Authorization": "Bearer ..."}`
- **`second_auth_headers`** — registers "testuser2" for social/multi-user tests
- **`sample_whiskeys`** — 6 diverse bottles (Buffalo Trace, Laphroaig 10, Jameson, Yamazaki 12, Rittenhouse Rye, Crown Royal) + seeds badges
- **`sample_user_with_ratings`** — testuser with 3 check-ins (depends on client + auth_headers + sample_whiskeys)
- **`sample_journey`**, **`sample_video`**, **`sample_top_list_curated`**, **`sample_sponsored_placement`** — domain-specific fixtures

### Writing a new test file:
```python
def test_my_feature(client, auth_headers, sample_whiskeys):
    resp = client.get("/api/my-endpoint", headers=auth_headers)
    assert resp.status_code == 200
```

Fixtures compose: `sample_user_with_ratings` depends on `client + auth_headers + sample_whiskeys`, so requesting it gives you all three.

## Additional API Routers

These routers exist but are not listed in the main table above:

| Router | Prefix | Purpose |
|---|---|---|
| `regions.py` | `/regions` | Region browsing, detail, and filtering |
| `leaderboard.py` | `/leaderboard` | Challenge leaderboards |
| `awards.py` | `/awards` | Community awards and voting |
| `marketplace.py` | `/marketplace` | E-commerce marketplace (CartItem, Order, OrderItem) |
| `subscription_box.py` | `/subscription-box` | Curated subscription box management |
| `blog.py` | `/blog` | Blog posts and articles |
| `push_notifications.py` | `/push` | Browser push subscription and preferences |

## Additional Frontend Pages

| Page | Route | Auth | Purpose |
|---|---|---|---|
| `Awards.jsx` | `/awards` | No | Community awards and voting |
| `Blog.jsx` | `/blog` | No | Blog listing |
| `BlogArticle.jsx` | `/blog/:slug` | No | Single blog post |
| `Leaderboard.jsx` | `/leaderboard` | No | Challenge leaderboards |
| `LearnCategory.jsx` | `/learn/categories/:slug` | No | Category deep-dive |
| `LearnDistillery.jsx` | `/learn/distilleries/:slug` | No | Distillery profile |
| `LearnGlossary.jsx` | `/learn/glossary` | No | Whiskey terminology |
| `LearnGrain.jsx` | `/learn/grains/:slug` | No | Grain types guide |
| `Marketplace.jsx` | `/marketplace` | No | E-commerce marketplace |
| `Regions.jsx` | `/regions` | No | Region browser |
| `RegionDetail.jsx` | `/regions/:slug` | No | Region detail |
| `SubscriptionBox.jsx` | `/subscription-box` | No | Subscription box |

## Additional Components

| Component | Purpose |
|---|---|
| `CheckInComments.jsx` | Comment thread on a check-in |
| `CriticScores.jsx` | Professional critic score display |
| `PushPermissionBanner.jsx` | Banner to request push notification permission |
| `ReportModal.jsx` | Report/flag content modal |
| `SidebarMap.jsx` | Small inline Leaflet map (lazy-loaded in ChatSidebar) |
| `SkeletonCard.jsx` | Loading placeholder card |
| `SponsoredCard.jsx` | Sponsored whiskey placement card |
| `StoreMap.jsx` | Leaflet map for store locations |
| `Toast.jsx` | `ToastProvider` + `useToast()` hook. Wraps app in `App.jsx`. Auto-dismiss 3.5s |
| `UserLevel.jsx` | User level badge (Novice-Master) |
| `UserSearch.jsx` | User search autocomplete |
| `VideoComments.jsx` | Comment thread on a video |
| `VideoUpload.jsx` | Video upload with preview |

## Frontend Utilities

| File | Key exports | Purpose |
|---|---|---|
| `constants.js` | `CATEGORY_EMOJI`, `getCategoryEmoji(cat)`, `foodEmoji(item)`, `WHISKEY_CATEGORIES`, `MAX_UPLOAD_SIZE` | Shared emoji maps and category definitions. Import instead of hardcoding |
| `data/flavorTaxonomy.js` | `FLAVOR_TAXONOMY` | 3-level flavor hierarchy (family -> subfamily -> note) with UI colors. Used in Browse flavor filter |
| `api/analytics.js` | `trackPageView(path)`, `trackEvent(name, data)`, `startPageTimer()`, `endPageTimer(path)` | Fire-and-forget analytics via `navigator.sendBeacon`. Debounced page views (2s window) |
| `i18n/useTranslation.js` | `useTranslation()` returns `{ t, locale }` | Simple key-based translation hook. English-only (`i18n/en.json`, 47 keys) |
| `utils/stars.jsx` | `StarDisplay` | Star rating rendering with half-star support |
| `utils/media.js` | `mediaUrl(path)` | Converts relative image paths to CDN URLs |

### Toast notifications:
```jsx
import { useToast } from '../components/Toast'
const addToast = useToast()
addToast('Saved!', 'success')      // types: 'success' | 'error' | 'info'
addToast('Failed', 'error', 5000)  // optional custom duration in ms
```

## CSS Design Tokens

Design tokens defined as CSS custom properties in `:root` in `App.css`. Use these instead of hardcoding colors:

```css
--bg: #1a1a1a;  --surface: #222222;  --surface-2: #2a2a2a;
--border: #3a3a3a;  --amber: #c9a84c;  --amber-light: #e2c97e;
--text: #ffffff;  --text-soft: #ece8e3;  --text-muted: #d0c9c0;
--red: #e05050;  --green: #66bb6a;  --brand-script: #d19a82;
--radius: 12px;  --radius-sm: 8px;
--shadow-sm / --shadow / --shadow-hover
```

Font stack: `'Inter', system-ui, sans-serif`. Brand accent font: `'Dancing Script'` (used with `--brand-script` color).

## Docker Architecture

4 services in `docker-compose.yml`:
1. **db** — `postgres:16-alpine`, healthcheck, persistent `pgdata` volume
2. **backend** — FastAPI + Gunicorn (2 workers, `UvicornWorker`, 120s timeout, `preload_app=True`, max 1000 req/worker). Config in `deploy/gunicorn.conf.py`
3. **frontend** — Vite build served by nginx (see `frontend/nginx.conf` for social bot detection, SSE proxy, asset caching)
4. **scheduler** — Same backend image, runs `python -m app.scheduler` (APScheduler, 256MB memory limit)

### Startup sequence (runs in `main.py` lifespan):
1. `Base.metadata.create_all()` — create/migrate tables
2. `_run_migrations()` — add missing columns to existing tables
3. `seed_badges()` — 11 badge definitions
4. `seed_toplists()` — curated list definitions
5. `seed_critics()` — critic score definitions
6. `seed_challenges()` — monthly challenge definitions
7. `cleanup_old_events()` — purge analytics beyond retention period

### Scheduled jobs (UTC, in `scheduled_jobs.py`):
| Job | Schedule | Function |
|---|---|---|
| Weekly digest | Sunday 10:00 | `send_weekly_digests()` |
| Re-engagement | Daily 14:00 | `send_re_engagement_emails()` — users inactive 14+ days |
| Onboarding drip | Daily 11:00 | `send_drip_emails()` — day 1, 3, 7, 14 after registration |
| Streak push | Daily 20:00 | `send_streak_push_reminders()` — active streak users who haven't checked in |
| Price alerts | Daily 09:00 | `check_price_alerts()` — push + in-app when price drops below target |

## ML Module Details

All in `backend/app/ml/`.

| Module | Purpose |
|---|---|
| `collaborative_filter.py` | NCF PyTorch model class: 32-dim embeddings, MLP tower (64->32->16->1), global + user + item bias |
| `inference.py` | `get_ncf_recommendations(username, db, top_n)` — lazy loads `model.pt` with double-checked locking. Metadata in `model_meta.json` (n_users, n_items, embedding_dim). Returns `list[(Whiskey, score)]` or `None` (triggers content-based fallback) |
| `recommender.py` | Content-based cosine similarity over feature vectors (category, ABV, age, price, 29+ flavor tags). Used as fallback when NCF unavailable or user has < 3 ratings |
| `taste_similarity.py` | `_profile_from_ratings(ratings)` — builds weighted centroid taste vector for palate comparison and match scores |
| `train.py` | Training script: `python -m app.ml.train`. 8 synthetic user archetypes (bourbon_lover, peat_head, highland_fan, etc.) for bootstrapping when < 500 real ratings. Outputs `model.pt` + `model_meta.json` |
| `agent.py` | LangGraph ReAct chat agent with 20+ tools, SSE streaming, built-in whiskey glossary (40+ terms) |

## Additional Data Models

These models exist in `models.py` but are not listed in the Key Data Models table above:

| Model | Table | Purpose |
|---|---|---|
| `ConversationSummary` | `conversation_summaries` | Session summaries for cross-session chat memory |
| `LiquorStore` | `liquor_stores` | Cached OSM data for nearby store lookups |
| `StoreAvailability` | `store_availability` | User-reported stock at stores |
| `ReviewHelpful` | `review_helpful` | Helpful votes on reviews (separate from toasts) |
| `ReviewFlavorTag` | `review_flavor_tags` | User-submitted flavor tags per review |
| `CheckInComment` | `checkin_comments` | Comments on check-ins |
| `WatchlistItem` | `watchlist_items` | User watching a whiskey for price alerts |
| `WatchlistAlert` | `watchlist_alerts` | In-app notification entries (follows, price drops, etc.) |
| `PriceEnrichmentLog` | `price_enrichment_log` | Audit trail for how prices were determined |
| `VideoToast` | `video_toasts` | Likes on videos |
| `VideoComment` | `video_comments` | Comments on videos |
| `AffiliateClick` | `affiliate_clicks` | Buy link click tracking |
| `UserSubscription` | `user_subscriptions` | Premium subscription state |
| `SponsoredPlacement` | `sponsored_placements` | Paid brand placements with impression/click counts |
| `PriceAlert` | `price_alerts` | Price drop alert subscriptions |
| `StripeEvent` | `stripe_events` | Webhook event log for idempotency |
| `UserStreak` | `user_streaks` | Daily engagement streak tracking |
| `Challenge` / `UserChallengeProgress` | `challenges` / `user_challenge_progress` | Monthly challenges and per-user progress |
| `PasswordResetToken` | `password_reset_tokens` | Secure reset tokens (SHA-256 hashed) |
| `EmailPreference` | `email_preferences` | Per-user email opt-in/out (8 category fields) |
| `EmailLog` | `email_log` | Audit trail for all emails sent |
| `PushSubscription` | `push_subscriptions` | Browser push endpoints per device |
| `TopList` / `TopListItem` | `top_lists` / `top_list_items` | Curated/dynamic ranked lists |
| `UserList` / `UserListItem` | `user_lists` / `user_list_items` | User-created custom lists |
| `CriticScore` | `critic_scores` | Professional critic scores from external sources |
| `UserAction` | `user_actions` | Explicit action tracking for funnel analysis |
| `ScanHistory` | `scan_histories` | Bottle scan history (label + UPC) |
| `CommentMention` | `comment_mentions` | @mentions in comments |
| `CommunityAward` / `CommunityVote` | `community_awards` / `community_votes` | Community awards and voting |
| `CartItem` / `Order` / `OrderItem` | `cart_items` / `orders` / `order_items` | E-commerce marketplace |
| `SubscriptionBox` | `subscription_boxes` | Curated subscription box definitions |
| `UserJourneyProgress` | `user_journey_progress` | Track user progress through journeys |
