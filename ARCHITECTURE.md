# SipSense — Full Architecture Diagram

## Context
This is a reference document — no code changes needed. The goal is to map out every layer of the SipSense application so you can understand how all the pieces connect.

---

## High-Level Overview

```
                        +-----------------------+
                        |     sipsense.ai       |
                        |   (Porkbun domain)    |
                        +-----------+-----------+
                                    |
                              HTTPS (443)
                           Let's Encrypt SSL
                                    |
                        +-----------v-----------+
                        |   System Nginx        |
                        |   (EC2: 18.223.29.193)|
                        +-----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
            Static files                    /api/* proxy
            (SPA + assets)                         |
                    |                               |
        +-----------v-----------+       +-----------v-----------+
        |   Frontend Container  |       |   Backend Container   |
        |   nginx:80 -> 8080    |       |   gunicorn:8000       |
        |   React 19 + Vite 7   |       |   FastAPI 0.115       |
        +-----------------------+       +-----------+-----------+
                                                    |
                                    +---------------+---------------+
                                    |               |               |
                            +-------v---+   +-------v---+   +------v------+
                            | PostgreSQL |   |  S3 + CDN |   | Claude API  |
                            | (Docker)   |   | (AWS)     |   | (Anthropic) |
                            +------------+   +-----------+   +-------------+
```

---

## Frontend — React 19 + Vite 7

**Entry:** `frontend/src/main.jsx` -> `App.jsx`
**API Client:** `frontend/src/api/client.js` (JWT auth, dedup, retry, timeout)
**Styling:** `frontend/src/App.css` (single 68KB file) + per-page CSS modules

### Routes (React Router 7)

| Route | Page Component | Description |
|---|---|---|
| `/` | Browse | Whiskey catalog — search, filter, sort |
| `/discover` | Discover | AI-powered discovery & trending |
| `/scan` | Scan | UPC barcode scanning (html5-qrcode) |
| `/feed` | Feed | Social feed (check-ins, toasts, comments) |
| `/videos` | Videos | Short-form video feed (TikTok-style) |
| `/me` | Profile | User profile, collection, stats, badges |
| `/user/:username` | PublicProfile | Other user's profile + palate match |
| `/whiskey/:id` | WhiskeyDetail | Detail page, AI notes, reviews, similar |
| `/journeys/:slug` | Journey | Multi-step tasting journey |
| `/quiz` | Quiz | Flavor preference onboarding |
| `/onboarding` | Onboarding | Registration / login |
| `/alerts` | Alerts | Notification center |
| `/premium` | Premium | Subscription features |
| `/admin` | Admin | Admin dashboard |

### Key Frontend Patterns
- **Auth:** JWT stored in `localStorage` (`sipsense_token`, `sipsense_user`)
- **State:** Component-level state + URL params (no Redux/Zustand)
- **Toasts:** React Context (`ToastProvider`)
- **Protected routes:** `RequireAuth` wrapper
- **PWA:** `public/manifest.json` + `public/sw.js` (service worker, offline caching)
- **Analytics:** Custom `trackPageView`, `trackEvent` functions
- **Errors:** Sentry integration (`VITE_SENTRY_DSN`)

---

## Backend — FastAPI 0.115 + Gunicorn

**Entry:** `backend/app/main.py`
**Models:** `backend/app/models.py` (30+ SQLAlchemy models)
**Schemas:** `backend/app/schemas.py` (Pydantic validators)
**Auth:** `backend/app/auth.py` (JWT HS256 + bcrypt)
**Storage:** `backend/app/storage.py` (S3 with local fallback)

### Middleware Stack (applied in order)
```
Request
  |-> Rate Limiter (300 req / 60s per IP, in-memory)
  |-> Analytics Logger (method, path, status, response time)
  |-> CORS (configurable origins)
  |-> GZip Compression (>1KB)
  |-> Security Headers (nosniff, DENY frame)
  |-> Router
```

### All API Endpoints (116+ across 30 routers)

#### Core
| Method | Path | Router | Description |
|---|---|---|---|
| POST | `/auth/register` | auth | Create user, return JWT |
| POST | `/auth/login` | auth | Authenticate, return JWT |
| GET | `/auth/me` | auth | Current user info |
| GET | `/whiskeys/` | whiskeys | List (search, filter, sort, paginate) |
| GET | `/whiskeys/count` | whiskeys | Total count with images |
| GET | `/whiskeys/{id}` | whiskeys | Detail page |
| POST | `/whiskeys/{id}/rate` | whiskeys | Submit rating (score, notes, tags) |
| GET | `/whiskeys/{id}/similar` | whiskeys | Content-based similar whiskeys |
| GET | `/whiskeys/{id}/reviews` | whiskeys | Paginated reviews + distribution |
| POST | `/whiskeys/scan` | whiskeys | UPC barcode lookup |

#### AI & Recommendations
| Method | Path | Router | Description |
|---|---|---|---|
| GET | `/recommendations/` | recommendations | Personalized recs (NCF -> content fallback) |
| POST | `/quiz/` | quiz | Submit quiz -> 6 tailored recs |
| POST | `/chat/` | chat | SSE streaming LangGraph agent |
| GET | `/whiskeys/{id}/ai-tasting-notes` | ai_features | Claude-generated nose/palate/finish |
| POST | `/whiskeys/{id}/upload-photo` | ai_features | Photo -> EasyOCR label extraction |
| GET | `/user/{username}/palate-profile` | ai_features | AI taste summary |
| GET | `/whiskeys/flavor-breakdown/{id}` | ai_features | AI flavor analysis |

#### Social
| Method | Path | Router | Description |
|---|---|---|---|
| GET | `/feed/` | feed | Social feed (followers + trending) |
| GET | `/user/{username}/profile` | social | Public profile |
| POST | `/user/{username}/follow` | social | Follow user |
| DELETE | `/user/{username}/follow` | social | Unfollow |
| GET | `/user/{username}/followers` | social | Follower list |
| GET | `/user/{username}/following` | social | Following list |
| GET | `/palate-match/{username}` | social | Palate comparison score |
| GET | `/suggested-users` | social | Users with similar palates |

#### Videos
| Method | Path | Router | Description |
|---|---|---|---|
| GET | `/videos/` | videos | Paginated video feed |
| POST | `/videos/` | videos | Upload video |
| GET | `/videos/{id}` | videos | Video detail |
| POST | `/videos/{id}/toast` | videos | Like video |
| DELETE | `/videos/{id}/toast` | videos | Unlike |
| POST/GET | `/videos/{id}/comments` | videos | Add / list comments |
| DELETE | `/videos/{id}/comments/{cid}` | videos | Delete comment |
| POST | `/videos/{id}/view` | videos | Track view |

#### Collections & Lists
| Method | Path | Router | Description |
|---|---|---|---|
| GET/POST/DELETE | `/favorites/...` | favorites | Favorite whiskeys |
| GET/POST/PATCH/DELETE | `/collection/...` | collection | Personal collection (sealed/opened/finished) |
| GET/POST/DELETE | `/watchlist/...` | watchlist | Watchlist + alerts |
| GET | `/alerts/` | watchlist | Unread alerts |
| GET | `/alerts/count` | watchlist | Unread count |

#### Learning & Exploration
| Method | Path | Router | Description |
|---|---|---|---|
| GET | `/flights/themes` | flights | Flight themes list |
| GET | `/flights/themes/{theme}` | flights | Flight whiskeys + lessons |
| GET/POST | `/flights/{theme}/progress` | flights | User flight progress |
| GET | `/journeys/` | journeys | Curated tasting journeys |
| GET | `/journeys/{slug}` | journeys | Journey detail + steps |
| GET/POST | `/user/.../journeys/{slug}/progress` | journeys | Journey progress |
| GET | `/learn/categories` | learn | Educational content |
| GET | `/learn/{category}` | learn | Lessons per category |
| GET | `/whiskeys/{id}/pairings` | pairings | Food pairings (AI) |
| GET | `/blind-tasting/` | blindtasting | Random blind tasting |
| POST | `/blind-tasting/guess` | blindtasting | Submit guess |

#### Monetization
| Method | Path | Router | Description |
|---|---|---|---|
| POST | `/affiliate/click/{id}` | affiliate | Track buy-link click |
| GET | `/affiliate/stats` | affiliate | Click/conversion stats |
| GET | `/subscription/status` | subscription | Premium check |
| POST | `/subscription/upgrade` | subscription | Create subscription |
| POST | `/subscription/cancel` | subscription | Cancel subscription |
| GET | `/subscription/features` | subscription | Free vs premium comparison |
| GET | `/sponsored/placements` | sponsored | Active sponsored content |
| POST | `/sponsored/impression/{id}` | sponsored | Track impression |
| POST | `/sponsored/click/{id}` | sponsored | Track click |

#### Other
| Method | Path | Router | Description |
|---|---|---|---|
| GET | `/trending/whiskeys` | trending | Top whiskeys this week |
| GET | `/trending/users` | trending | Most active users |
| GET | `/personality/type` | personality | User personality archetype |
| GET | `/daily/whiskey` | daily | Daily featured whiskey |
| POST | `/daily/vote` | daily | Vote on daily |
| POST | `/analytics/event` | analytics | Track custom event |
| GET | `/compare` | compare | Side-by-side comparison |
| GET | `/stores/nearby` | stores | Nearby liquor stores (OSM) |
| GET | `/discover/` | discover | Curated suggestions |
| GET | `/gift/suggestions` | gift | Gift recommendations |
| POST | `/sharecard/{rating_id}` | sharecard | Generate share card image |

---

## ML / AI Layer

```
backend/app/ml/
├── collaborative_filter.py   # NCF model definition (PyTorch)
├── model.pt                  # Trained model weights (189KB)
├── model_meta.json           # user2idx, item2idx mappings
├── inference.py              # Load model + top-N prediction
├── recommender.py            # Content-based fallback (numpy cosine sim)
├── train.py                  # Training pipeline from user_ratings
├── taste_similarity.py       # User palate matching
└── agent.py                  # LangGraph AI chat agent (88KB)
```

### Recommendation Pipeline
```
User requests recs
        |
        v
  +-----------+     success     +------------------+
  | NCF Model |  ------------> | Return top-N recs |
  | (PyTorch)  |                +------------------+
  +-----------+
        | failure / cold-start
        v
  +------------------+
  | Content-Based    |   Cosine similarity over:
  | Fallback (numpy) |   category, ABV, age, price, flavor tags
  +------------------+
        |
        v
  +------------------+
  | Return top-N recs |
  +------------------+
```

### AI Agent (LangGraph + Claude)
```
User message --> LangGraph Agent --> Claude API
                      |
                      +-- Tools:
                      |   - search_whiskeys
                      |   - compare_whiskeys
                      |   - find_nearby_stores
                      |   - build_flight
                      |   - generate_palate_profile
                      |
                      +-- Generative UI events:
                          - whiskey cards
                          - comparison tables
                          - flight builders
                          - map views
                          - palate profiles
```

---

## Database — PostgreSQL 16

### Entity Relationship Diagram

```
                    +-------------+
                    |    User     |
                    +------+------+
                           |
          +--------+-------+-------+--------+--------+
          |        |       |       |        |        |
     +----v--+ +---v---+ +v-----+ +v------+ +v-----+ +--------+
     |Rating | |Follow | |Fav   | |Collect| |Badge | |Subscr  |
     +---+---+ +-------+ +------+ +-------+ +------+ +--------+
         |         follower_id              user_id
         |         following_id
    +----+----+
    |         |
 +--v--+  +--v------+
 |Toast|  |Comment  |
 +-----+  +---------+

     +-------------+          +-------------+
     |   Whiskey   |<-------->|   Rating    |
     +------+------+    FK    +-------------+
            |
     +------+------+------+------+
     |      |      |      |      |
  +--v--+ +-v---+ +v----+ +v---+ +v---------+
  |Fav  | |Coll | |Watch| |Vid | |JourneyStep|
  +-----+ +-----+ +-----+ +---+ +-----------+
                                       |
                                 +-----v------+
                                 |  Journey    |
                                 +-------------+

  +------------------+    +------------------+
  | SponsoredPlace   |    | AffiliateClick   |
  +------------------+    +------------------+

  +------------------+    +------------------+
  | AnalyticsEvent   |    | AICache          |
  +------------------+    +------------------+

  +------------------+    +------------------+
  | LiquorStore      |    | UserMemory       |
  +------------------+    +------------------+
```

### All Tables (30+)

| Table | Key Fields | Purpose |
|---|---|---|
| `users` | id, username, email, hashed_password, is_premium, quiz_completed | User accounts |
| `whiskeys` | id, name, distillery, category, region, age, abv, price_usd, flavor_profile, image_url, upc | Whiskey catalog |
| `user_ratings` | user_id, whiskey_id, score(1-5), notes, serving_style, image_path | Reviews/ratings |
| `review_flavor_tags` | rating_id, tag_name | Per-review flavor tags |
| `user_favorites` | user_id, whiskey_id | Quick favorites list |
| `collection_items` | user_id, whiskey_id, status(sealed/opened/finished), purchase_price | Personal collection |
| `watchlist_items` | username, whiskey_id | Monitoring whiskey activity |
| `watchlist_alerts` | username, alert_type, whiskey_id, from_username, is_read | Notifications |
| `follows` | follower_id, following_id | Social graph |
| `toasts` | user_id, rating_id | Likes on ratings |
| `checkin_comments` | user_id, rating_id, text | Comments on ratings |
| `videos` | user_id, video_path, whiskey_id, view_count, is_sponsored | User videos |
| `video_toasts` | user_id, video_id | Likes on videos |
| `video_comments` | user_id, video_id, text | Comments on videos |
| `badges` | slug(PK), name, emoji, category | Achievement definitions |
| `user_badges` | user_id, badge_slug | Earned badges |
| `journeys` | slug, title, category, difficulty | Tasting journeys |
| `journey_steps` | journey_id, step_number, whiskey_id, lesson_text | Journey steps |
| `user_journey_progress` | user_id, journey_id, current_step | Journey tracking |
| `user_subscriptions` | user_id, tier, status, payment_provider | Premium subs |
| `affiliate_clicks` | user_id, whiskey_id, retailer, source, converted | Affiliate tracking |
| `sponsored_placements` | advertiser_name, whiskey_id, impression_count, click_count | Ads |
| `analytics_events` | timestamp, user_id, method, path, status_code, response_time_ms | Request logs |
| `user_actions` | user_id, action, whiskey_id, category | User behavior |
| `ai_cache` | cache_key, response_json | Claude API cache |
| `user_memory` | user_id, preferences(JSON) | AI conversation memory |
| `liquor_stores` | osm_id, name, lat, lng | Store locations |
| `store_availability` | store_id, whiskey_id, status | Stock reports |
| `price_enrichment_log` | whiskey_id, method, confidence | Price audit trail |

---

## Infrastructure & Deployment

### Docker Services
```
docker-compose.yml
├── db        : postgres:16-alpine (pgdata volume)
├── backend   : python:3.11-slim + gunicorn (2 workers, 120s timeout)
└── frontend  : node:20 build -> nginx:alpine (SPA routing + /api proxy)
```

### CI/CD (GitHub Actions)
```
Push to PR / main
        |
        v
  +------------------+
  | ci.yml           |
  | - pytest (backend)|
  | - lint + build    |
  |   (frontend)     |
  +--------+---------+
           |
           | (on merge to main)
           v
  +------------------+
  | deploy.yml       |
  | - SSH to EC2     |
  | - git pull       |
  | - docker compose |
  |   up --build     |
  | - health check   |
  +------------------+
```

### Production Server (EC2 t3.micro — 1GB RAM)
```
  System Nginx (SSL termination, port 443)
      |
      +---> localhost:8080 (frontend container)
      +---> localhost:8000 (backend container via /api)

  Docker Compose (production overrides):
      - 4GB memory limit on backend
      - restart: on-failure (max 3)
      - localhost-only port bindings
```

### External Services
| Service | Purpose | Config |
|---|---|---|
| **Claude API** (Anthropic) | Tasting notes, palate profiles, chat agent | `ANTHROPIC_API_KEY` |
| **AWS S3 + CloudFront** | Image/video storage + CDN | `S3_BUCKET`, `AWS_*`, `CDN_BASE_URL` |
| **OpenStreetMap** (Overpass) | Liquor store locations | No key needed |
| **Let's Encrypt** | SSL certificates | Certbot auto-renew |
| **Sentry** | Frontend error tracking | `VITE_SENTRY_DSN` |

---

## Data Flow Examples

### User rates a whiskey
```
React (WhiskeyDetail)
  -> POST /api/whiskeys/{id}/rate (JWT in header)
  -> FastAPI auth middleware extracts user
  -> Creates UserRating row in PostgreSQL
  -> Triggers badge check (badges.py)
  -> Creates WatchlistAlert for followers
  -> Returns updated whiskey with new avg rating
```

### User opens chat
```
React (ChatSidebar)
  -> POST /api/chat/ (SSE stream)
  -> LangGraph agent receives message
  -> Agent calls Claude API with tools
  -> Claude may call search_whiskeys, compare, etc.
  -> Agent streams generative UI events back
  -> React renders whiskey cards, maps, etc.
```

### User gets recommendations
```
React (Discover page)
  -> GET /api/recommendations/
  -> Try NCF model (inference.py)
     -> Load model.pt + model_meta.json
     -> Predict scores for unrated whiskeys
     -> Return top-N
  -> If NCF fails (cold start):
     -> Content-based fallback (recommender.py)
     -> Build user taste vector from ratings
     -> Cosine similarity against all whiskeys
     -> Return top-N
```
