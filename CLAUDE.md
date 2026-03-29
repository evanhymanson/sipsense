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
