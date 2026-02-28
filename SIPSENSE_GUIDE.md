# SipSense - Complete App Guide

**"The app that teaches you whiskey"**

SipSense is a full-stack, AI-powered whiskey discovery and education platform. It combines a 9,000+ whiskey database, machine learning recommendations, an AI chat agent, community social features, gamification, and a liquor store locator into one app designed to make whiskey approachable for everyone.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Running the App](#running-the-app)
5. [Feature Guide](#feature-guide)
   - [Account & Onboarding](#account--onboarding)
   - [Browse & Search](#browse--search)
   - [Whiskey Detail Page](#whiskey-detail-page)
   - [Taste Quiz](#taste-quiz)
   - [Personalized Recommendations](#personalized-recommendations)
   - [Activity Feed & Social](#activity-feed--social)
   - [Favorites](#favorites)
   - [My Shelf (Collection)](#my-shelf-collection)
   - [My Palate Profile](#my-palate-profile)
   - [Whiskey Personality](#whiskey-personality)
   - [Badges & Achievements](#badges--achievements)
   - [Compare Bottles](#compare-bottles)
   - [Flight Builder](#flight-builder)
   - [Gift Finder](#gift-finder)
   - [Value Picks](#value-picks)
   - [Flavor Wheel](#flavor-wheel)
   - [Trending](#trending)
   - [Daily Discovery](#daily-discovery)
   - [Blind Tasting Challenge](#blind-tasting-challenge)
   - [Store Locator](#store-locator)
   - [Learn (Whiskey 101)](#learn-whiskey-101)
   - [AI Chat Assistant](#ai-chat-assistant)
   - [User Profiles](#user-profiles)
6. [API Reference](#api-reference)
7. [Database](#database)
8. [ML & Recommendation Engine](#ml--recommendation-engine)
9. [Testing](#testing)
10. [Environment Variables](#environment-variables)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Git

### Quick Setup

```bash
# Clone the repo
git clone <your-repo-url>
cd sipsense

# Backend setup
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (WAL mode, production-ready for single-server) |
| Auth | JWT tokens via python-jose + bcrypt via passlib |
| AI/LLM | Anthropic Claude API (descriptions, chat agent) |
| AI Agent | LangGraph + LangChain (conversational chat) |
| ML | NumPy cosine similarity (content-based filtering) |
| ML (planned) | PyTorch collaborative filtering |
| HTTP Client | httpx (Overpass API, external calls) |
| Geolocation | OpenStreetMap Overpass API (free, no API key) |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Build Tool | Vite |
| Maps | Leaflet + react-leaflet (CartoDB dark tiles) |
| Styling | Plain CSS with CSS custom properties (dark amber theme) |
| State | React hooks + localStorage for persistence |
| Streaming | Server-Sent Events (SSE) for chat |

---

## Project Structure

```
sipsense/
├── CLAUDE.md                    # AI assistant instructions
├── VISION.md                    # Product vision & roadmap
├── SIPSENSE_GUIDE.md            # This file
│
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, rate limiter, router registration
│   │   ├── database.py          # SQLAlchemy engine, session, get_db dependency
│   │   ├── models.py            # All ORM models (User, Whiskey, Rating, Badge, Store, etc.)
│   │   ├── schemas.py           # Pydantic v2 schemas for request/response validation
│   │   ├── auth.py              # JWT creation/verification, password hashing, auth dependencies
│   │   ├── badges.py            # Badge definitions and evaluation engine
│   │   │
│   │   ├── routers/             # 21 API router files (70+ endpoints)
│   │   │   ├── auth.py          # Register, login, /me
│   │   │   ├── whiskeys.py      # CRUD, search, filter, rate, value picks
│   │   │   ├── recommendations.py  # ML-powered personalized recommendations
│   │   │   ├── quiz.py          # Taste preference quiz
│   │   │   ├── favorites.py     # Add/remove/list favorites
│   │   │   ├── collection.py    # My Shelf bottle tracking
│   │   │   ├── stores.py        # Liquor store locator (OpenStreetMap)
│   │   │   ├── chat.py          # AI chat agent (LangGraph + SSE streaming)
│   │   │   ├── feed.py          # Community activity feed
│   │   │   ├── social.py        # Toasts (likes) and user profiles
│   │   │   ├── trending.py      # Trending & new arrivals
│   │   │   ├── pairings.py      # Food & cocktail pairings
│   │   │   ├── flights.py       # Curated tasting flights (7 themes)
│   │   │   ├── gift.py          # Gift recommendation wizard
│   │   │   ├── compare.py       # Side-by-side bottle comparison
│   │   │   ├── palate.py        # User taste profile analytics
│   │   │   ├── personality.py   # Whiskey personality archetype
│   │   │   ├── learn.py         # Educational content (guides, stories, glossary)
│   │   │   ├── daily.py         # Daily discovery (one curated pick per day)
│   │   │   └── blindtasting.py  # Blind tasting challenge game
│   │   │
│   │   └── ml/
│   │       ├── recommender.py   # Content-based cosine similarity + quiz vector logic
│   │       └── agent.py         # LangGraph chat agent with tool bindings
│   │
│   ├── scraper/                 # Multi-source whiskey data scrapers
│   │   ├── base.py              # Rate-limited httpx client
│   │   ├── distiller.py         # Distiller.com scraper
│   │   ├── openfoodfacts.py     # OpenFoodFacts API
│   │   ├── whiskybase.py        # Whiskybase scraper
│   │   ├── github_csv.py        # GitHub ML datasets
│   │   ├── normalizer.py        # Raw data normalization pipeline
│   │   └── run.py               # CLI entry point
│   │
│   ├── tests/                   # 178 tests (pytest)
│   │   ├── conftest.py          # Shared fixtures, in-memory SQLite, auth helpers
│   │   ├── pytest.ini           # Test configuration
│   │   ├── test_auth.py         # 11 auth tests
│   │   ├── test_whiskeys.py     # 20 whiskey CRUD/search/rate tests
│   │   ├── test_favorites.py    # 8 favorites tests
│   │   ├── test_collection.py   # 11 collection tests
│   │   ├── test_quiz.py         # 6 quiz tests
│   │   ├── test_recommendations.py  # 5 recommendation tests
│   │   ├── test_stores.py       # 7 store locator tests (mocked Overpass)
│   │   ├── test_flights.py      # 8 flight theme tests
│   │   ├── test_gift.py         # 5 gift finder tests
│   │   ├── test_palate.py       # 5 palate profile tests
│   │   ├── test_compare.py      # 3 comparison tests
│   │   ├── test_trending.py     # 5 trending tests
│   │   ├── test_pairings.py     # 4 pairings tests
│   │   ├── test_learn.py        # 8 educational content tests
│   │   ├── test_recommender_ml.py  # 6 ML unit tests
│   │   └── test_normalizer.py   # 56 scraper normalizer tests
│   │
│   ├── sipsense.db              # SQLite database (~9,000 whiskeys)
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── App.jsx              # Router, navigation groups, auth wrapper
    │   ├── api/client.js        # All API fetch methods (50+ functions)
    │   │
    │   ├── pages/               # 21 page components
    │   │   ├── Onboarding.jsx   # Login / Register
    │   │   ├── Browse.jsx       # Main whiskey catalog with filters
    │   │   ├── WhiskeyDetail.jsx # Deep-dive bottle page
    │   │   ├── Quiz.jsx         # 5-question taste quiz
    │   │   ├── Recommendations.jsx  # Personalized "For You"
    │   │   ├── Favorites.jsx    # Saved whiskeys
    │   │   ├── Collection.jsx   # My Shelf bottle tracker
    │   │   ├── MyPalate.jsx     # Taste profile analytics
    │   │   ├── Personality.jsx  # Whiskey personality type
    │   │   ├── Feed.jsx         # Community activity timeline
    │   │   ├── Trending.jsx     # Hot right now + new arrivals
    │   │   ├── DailyDiscovery.jsx  # One curated pick per day
    │   │   ├── FlavorWheel.jsx  # Hierarchical flavor browser
    │   │   ├── BlindTasting.jsx # Gamified tasting challenge
    │   │   ├── Compare.jsx      # Side-by-side comparison
    │   │   ├── FlightBuilder.jsx # Curated tasting flights
    │   │   ├── GiftFinder.jsx   # Guided gift wizard
    │   │   ├── ValuePicks.jsx   # Best bang-for-buck
    │   │   ├── Learn.jsx        # Whiskey 101 + Distilleries + Glossary
    │   │   ├── Stores.jsx       # Nearby liquor store finder
    │   │   └── UserProfile.jsx  # Public user profiles
    │   │
    │   ├── components/
    │   │   ├── WhiskeyCard.jsx      # Reusable whiskey card for grids
    │   │   ├── CheckInCard.jsx      # Activity feed check-in card
    │   │   ├── ChatSidebar.jsx      # AI chat assistant with generative UI
    │   │   ├── BadgeGrid.jsx        # Badge display grid
    │   │   ├── SkeletonCard.jsx     # Loading placeholder
    │   │   ├── StoreLocator.jsx     # Store finder (used on detail page)
    │   │   ├── StoreMap.jsx         # Leaflet map component
    │   │   └── ReportModal.jsx      # Availability report modal
    │   │
    │   └── data/
    │       └── flavorTaxonomy.js    # 3-level flavor hierarchy (7 families, 60+ nodes)
    │
    └── vite.config.js               # Dev proxy: /api/* -> localhost:8000/*

```

---

## Running the App

### Start the Backend

```bash
cd backend
source .venv/bin/activate    # or: .venv/bin/activate (zsh/bash)

# Start the server (auto-reloads on code changes)
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Start the Frontend

```bash
cd frontend
npm run dev
```

The app is now live at `http://localhost:5173`. The Vite dev server proxies `/api/*` requests to the backend automatically.

### Run Tests

```bash
cd backend
.venv/bin/python3 -m pytest tests/ -v
```

All 178 tests should pass in under 20 seconds.

---

## Feature Guide

### Account & Onboarding

When you first open the app, you're taken to the **Onboarding** page (`/onboarding`).

- **Create Account**: Pick a username (letters, numbers, underscores), enter email, set a password (6+ characters). You'll get a JWT token stored in your browser.
- **Sign In**: Username + password. Token persists in localStorage.
- After registering, you're redirected to the **Taste Quiz** to kickstart your profile.
- All other pages require authentication (the app redirects you to onboarding if not logged in).

### Browse & Search

**Route:** `/` (home page)

The main whiskey catalog. This is where you explore the full database of ~9,000 whiskeys.

- **Search bar** — type any name or distillery, results filter live
- **Category filter** — bourbon, scotch, irish, japanese, rye, canadian, etc.
- **Region filter** — Speyside, Islay, Highlands, Kentucky, etc.
- **Flavor filter** — smoky, vanilla, fruity, spicy, etc.
- **Price range** — set min and max price
- **ABV filter** — minimum alcohol by volume
- **Sort by** — rating (default), price low-to-high, price high-to-low, age, name
- **Pagination** — loads 50 at a time with "Load More"
- **Active filter chips** — see what filters are applied, click to remove

Each whiskey appears as a card showing name, distillery, category, ABV, age, region, price, and star rating.

### Whiskey Detail Page

**Route:** `/whiskey/:id`

Click any whiskey card to see its full profile. This is the richest page in the app:

- **Core info**: Name, distillery, category, region, age, ABV, price
- **"What makes this special"**: AI-generated 2-3 sentence description (cached in DB, generated via Claude API)
- **Flavor tags**: Clickable chips — click one to browse all whiskeys with that flavor
- **Community rating**: Average score + total number of ratings
- **Check-in form**: Rate this whiskey with:
  - Star rating (1-5, half-star increments)
  - Serving style (neat, rocks, cocktail, highball)
  - Location note (where are you drinking this?)
  - Tasting notes (optional freeform text)
  - After submitting, you may unlock **badges** (shown with a celebration animation)
- **Community reviews**: See what others have rated and said
- **Food pairings**: Category-specific pairings + flavor-bonus pairings (e.g., smoky whiskey gets "Grilled Steak")
- **Cocktail suggestions**: Recipes tailored to the whiskey category (Old Fashioned for bourbon, Penicillin for scotch, etc.)
- **Similar whiskeys**: ML-powered "If you like this, try..." section (5 recommendations via cosine similarity)
- **Store locator**: Find nearby liquor stores that might carry this bottle (uses your GPS location)
- **Favorite button**: Heart toggle to save to your favorites
- **Add to shelf**: Add this bottle to your personal collection

### Taste Quiz

**Route:** `/quiz`

A 5-question interactive quiz that learns your preferences and recommends your first whiskeys. Perfect for beginners who don't know where to start.

**Questions:**
1. **Flavor preferences** — multi-select from: sweet, fruity, spicy, vanilla, caramel, citrus, honey, oak, floral, nutty
2. **Smokiness** — none / light / heavy
3. **Body preference** — light / medium / full
4. **Budget per bottle** — four tiers from budget to luxury
5. **Style preference** — bourbon / scotch / irish / japanese / rye / surprise me

**Results:** 6 matched whiskeys ranked by similarity score, each with a plain-English explanation of why it matched (e.g., "It's a bourbon that hits your style preference, with vanilla, caramel notes you'll love, clean with no harsh smoke, fits your budget budget.").

If you're logged in, taking the quiz marks your profile as `quiz_completed`.

### Personalized Recommendations

**Route:** `/recommendations`

Once you've rated some whiskeys, the ML engine builds a profile of what you like and recommends bottles you haven't tried yet.

**How it works:**
- Your highly-rated whiskeys (3.5+ stars) are converted into 27-dimensional feature vectors
- The system computes the "centroid" (average) of your taste preferences
- Every unrated whiskey is scored by cosine similarity to your centroid
- Top matches are returned ranked by similarity score

**Cold start:** If you haven't rated anything yet, you'll see top-rated whiskeys as a starting point.

### Activity Feed & Social

**Route:** `/feed`

A chronological timeline of everyone's check-ins across the community.

- **Category filter tabs**: All, Bourbon, Scotch, Irish, Japanese, Rye, Single Malt
- **Each check-in shows**: Username (clickable to their profile), time ago, whiskey name + link, star rating, serving style emoji, location, tasting notes
- **Toast button**: Tap the toast emoji to "like" someone's check-in (like a cheers)
- **Infinite scroll**: Load more with pagination

### Favorites

**Route:** `/favorites`

Your saved whiskeys. Tap the heart on any whiskey card or detail page to add it here.

- See all your favorited bottles in one place
- Shows count of how many you've saved
- Quick access to the detail page for each

### My Shelf (Collection)

**Route:** `/collection`

Track every bottle you own, have opened, or have finished. Think of it as your personal whiskey inventory.

- **Add bottles** from any whiskey detail page with optional purchase price, location, and personal notes
- **Status tracking**: Sealed / Opened / Finished — change status with a dropdown
- **Filter tabs**: View all, or filter by status
- **Stats row**: Total bottles, sealed count, opened count, finished count, total money spent
- **Per-bottle info**: Whiskey details, purchase price, purchase location, personal notes
- **Remove**: Delete bottles from your collection

### My Palate Profile

**Route:** `/my-palate`

An analytics dashboard of your personal taste preferences, built from all your ratings and favorites.

- **AI narrative**: A plain-English description of your palate (e.g., "With 12 bottles rated, you've built a solid baseline. You lean toward bourbon, and your palate tends toward vanilla, caramel, sweet. Your ratings average 4.1/5, which makes you an enthusiastic scorer.")
- **Stats cards**: Bottles rated, favorites saved, average rating, average price
- **Top categories**: Bar chart of which whiskey styles you drink most
- **Flavor cloud**: Your most common flavor tags visualized
- **Recent ratings**: Your last 15 check-ins with whiskey details and scores
- **Favorites**: Grid of your saved bottles

### Whiskey Personality

**Route:** `/personality`

Based on your rating patterns, the app assigns you a whiskey personality archetype.

**Personality types include:**
- Campfire Poet (loves peated/smoky)
- Golden Wanderer (eclectic explorer)
- Velvet Traditionalist (classic bourbon lover)
- And more, each with their own emoji, description, spirit bottle recommendation, and playlist vibe

**What you see:**
- Your personality emoji, title, and tagline
- Description of what your preferences say about you
- Recommended "signature bottle"
- If experienced: Flavor DNA, go-to styles, detailed stats

### Badges & Achievements

Badges are awarded automatically after each check-in. The badge engine evaluates your history against these criteria:

| Badge | Requirement |
|-------|-------------|
| First Sip | Rate your first whiskey |
| The Regular | 25 check-ins |
| Connoisseur | 50 check-ins |
| Bourbon Trail | Rate 5 different bourbons |
| Peat Freak | Rate 5 Islay scotches |
| Master Blender | Try all 8 whiskey categories |
| World Traveler | Rate whiskeys from 4+ countries |
| High Roller | Check in a bottle worth $200+ |
| Cask Strength | Rate a whiskey at 55%+ ABV |
| Top Shelf | Give a perfect 5-star rating |

When you earn a new badge, it appears in a celebration animation right after your check-in. View all your badges on the Palate and Personality pages.

### Compare Bottles

**Route:** `/compare`

Pick any two whiskeys and see them side by side.

- **Search autocomplete**: Start typing to find bottles (debounced search)
- **Head-to-head comparison**:
  - Price (lower highlighted in green)
  - Rating (higher highlighted in green)
  - Age, ABV, Category, Region
  - Visual bars for ABV and rating
  - Flavor profiles compared

### Flight Builder

**Route:** `/flight-builder`

Build curated tasting flights from 7 pre-designed themes. Each flight is a guided progression of 4 bottles with tasting lessons.

**Available themes:**
| Theme | What it teaches |
|-------|----------------|
| Beginner Flight | Four approachable drams for first-timers |
| Smoky Journey | Follow the peat from a whisper to a roar |
| Bourbon Ladder | Climb from everyday to extraordinary American whiskey |
| Scotch Regions | One dram from each corner of Scotland |
| World Tour | Five countries, five completely different philosophies |
| Sweet to Spicy | Ride the spectrum from honeyed to fiery |
| Age Progression | What oak actually does over time |

Each step includes the whiskey details plus a **"What to look for"** tasting lesson. Optional max price filter to keep things affordable.

### Gift Finder

**Route:** `/gift-finder`

A 4-step guided wizard to find the perfect whiskey gift.

1. **Drinker level**: Newbie / Casual / Enthusiast / Connoisseur
2. **Style preference**: Bourbon / Scotch / Irish / Japanese / Rye / Open to anything
3. **Budget**: $25-55 / $55-110 / $110-220 / $220+
4. **Occasion** (optional): Birthday / Holiday / Host gift / Just because

Results: 4 curated picks with a personalized message explaining why these bottles fit.

### Value Picks

**Route:** `/value-picks`

Find the best whiskeys for your money. Scoring formula: `rating / log(price)` — high rating at low price = high value.

- **Budget presets**: Under $30, $50, $75, $150
- **Category filter**: Narrow to bourbon, scotch, etc.
- **Custom max price**: Set your own ceiling
- **Ranked list**: Each bottle shows its rank, name, price, and rating

### Flavor Wheel

**Route:** `/flavor-wheel`

An interactive hierarchical flavor browser with 3 levels of depth.

**7 flavor families:**
- **Smoky**: Peaty (medicinal, mossy, bonfire) / Ashy (charcoal, gunpowder)
- **Sweet**: Caramel (toffee, butterscotch) / Vanilla (cream, custard) / Honey (heather, beeswax)
- **Fruity**: Dark Fruit (cherry, plum, raisin) / Citrus (orange, lemon) / Orchard (apple, pear) / Tropical (banana, mango)
- **Spicy**: Pepper (black, white, chili) / Baking Spice (cinnamon, nutmeg) / Herbal (mint, anise)
- **Woody**: Oak (cedar, resin) / Earthy (leather, tobacco) / Roasted (coffee, chocolate)
- **Floral**: Light Floral (rose, lavender) / Delicate (elderflower, chamomile)
- **Grainy**: Cereal (malt, corn, biscuit) / Nutty (almond, walnut)

Click any flavor at any level to browse matching whiskeys.

### Trending

**Route:** `/trending`

See what the community is drinking right now.

- **Category tabs**: All, Bourbon, Scotch, Irish, Japanese, Rye
- **Hot Right Now**: Whiskeys with the most recent activity (ratings + favorites, with favorites weighted 2x)
- **Recently Added**: Newest whiskeys in the database

### Daily Discovery

**Route:** `/daily`

One curated whiskey recommendation per day. Same pick for all users on the same day (deterministic based on date).

- Featured whiskey card with full details
- **Tasting tip** — what to look for when trying it
- **Did you know** — interesting fact about the whiskey
- **Conversation starter** — something fun to bring up at a tasting

### Blind Tasting Challenge

**Route:** `/blind-tasting`

A gamified challenge where you try to identify a mystery whiskey from clues.

**Difficulty levels:**
| Difficulty | Points | Clues Given |
|------------|--------|-------------|
| Easy (10pts) | ABV, Age, Price, Flavors, Description | Most information |
| Medium (25pts) | ABV, Price range, Flavors | Some information |
| Hard (50pts) | Flavor hints only | Minimal information |

**Gameplay:**
1. Pick your difficulty
2. Read the clues about the mystery whiskey
3. Guess the category (bourbon, scotch, irish, etc.)
4. See your result: correct, partial, or wrong
5. Full reveal with the whiskey's details and a fun fact
6. Running score tracker across rounds

### Store Locator

**Route:** `/stores` (standalone) + embedded on whiskey detail pages

Find liquor stores near you using OpenStreetMap data. No API key required.

- **Uses browser geolocation** (with permission)
- **Radius selector**: 1.2mi / 3mi / 6mi / 15mi
- **Interactive map**: Leaflet map with store markers and your position
- **Store list**: Name, distance, address, phone (clickable to call), website, opening hours
- **Community availability reports**: On whiskey detail pages, report whether a specific store has that bottle in stock
- **Results cached for 7 days** to minimize API calls

### Learn (Whiskey 101)

**Route:** `/learn`

A comprehensive educational hub with three sections:

**Tab 1 - Whiskey 101 (Category Guides)**

Deep-dive guides for each whiskey category. Each includes:
- Quick facts (4 bullet points)
- Flavor tags
- Multi-paragraph guide written in plain English
- Entry-level bottle recommendations
- "Next to explore" suggestion

Categories covered: Bourbon, Scotch, Rye, Irish, Japanese, Canadian

**Tab 2 - Distillery Stories**

Narrative stories about famous distilleries — not dry facts, real stories about the people and history. Currently covers 11 distilleries:
- Maker's Mark, Buffalo Trace, Wild Turkey, Four Roses (Bourbon)
- Glenfiddich, Laphroaig, Ardbeg, The Macallan (Scotch)
- Yamazaki (Japanese)
- Jameson, Redbreast (Irish)

**Tab 3 - Glossary**

30 whiskey terms explained in plain English, sorted alphabetically. Examples:
- Single Malt, Blended Whisky, Cask Strength, NAS, Peated, Mash Bill, Angel's Share, Dram, ABV, Mizunara Oak, PPM, Sherry Cask, Solera, and more.

### AI Chat Assistant

The **ChatSidebar** is available on every page (floating action button). It's powered by a LangGraph agent using Claude as the LLM backbone.

**What it can do:**
- Natural language whiskey recommendations ("something smoky under $60")
- Answer questions about whiskey ("what does NAS mean?")
- Compare bottles conversationally
- Suggest food pairings
- Remember context within a conversation

**Generative UI**: The agent can render rich components inline:
- Whiskey card grids (up to 6 per response)
- Store maps with locations
- Side-by-side comparison tables
- Flight visualizations
- Palate profile charts
- Price alternative suggestions

**Starter prompts** for new users:
- "I'm brand new to whiskey. Where do I start?"
- "What's the difference between bourbon and scotch?"
- "Find me something smoky but not too intense"
- And more

Messages persist in localStorage between sessions.

### User Profiles

**Route:** `/user/:username`

View any user's public profile:
- Username and member since date
- Stats: total check-ins, unique whiskeys, average score, badges earned
- Badge grid
- Top categories with progress bars
- Recent check-ins

---

## API Reference

The backend exposes 70+ endpoints across 21 routers. Full interactive documentation available at `http://localhost:8000/docs` when the server is running.

### Key Endpoint Groups

| Prefix | Auth | Purpose |
|--------|------|---------|
| `/auth/` | Varies | Register, login, get current user |
| `/whiskeys/` | Varies | CRUD, search, filter, sort, rate, value picks |
| `/recommendations/` | Required | ML-powered personalized recommendations |
| `/quiz/` | Optional | Taste preference quiz |
| `/favorites/` | Required | Add/remove/list favorite whiskeys |
| `/collection/` | Required | My Shelf bottle tracking |
| `/stores/` | Varies | Liquor store locator + community availability |
| `/chat/` | Optional | AI chat agent (SSE streaming) |
| `/feed/` | Optional | Community activity timeline |
| `/ratings/` | Required | Toast (like) check-ins |
| `/users/` | No | Public user profiles |
| `/trending/` | No | Trending + new arrivals |
| `/pairings/` | No | Food & cocktail pairings |
| `/flights/` | No | Curated tasting flights (7 themes) |
| `/gift/` | No | Gift recommendation wizard |
| `/compare/` | No | Side-by-side bottle comparison |
| `/palate/` | Required | Personal taste analytics |
| `/personality/` | Required | Whiskey personality archetype |
| `/learn/` | No | Educational content (guides, stories, glossary) |
| `/daily/` | No | Daily discovery pick |
| `/blind-tasting/` | No | Blind tasting challenge game |

### Rate Limiting

The API includes an in-memory rate limiter: **120 requests per minute per IP**. Returns `429 Too Many Requests` with a `Retry-After` header when exceeded.

---

## Database

### Models

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | Username, email, hashed password, JWT auth |
| `Whiskey` | `whiskeys` | Name, distillery, category, region, age, ABV, price, flavor profile, description, UPC barcode, source |
| `UserRating` | `user_ratings` | Score (1-5), notes, serving style, location, timestamp |
| `UserFavorite` | `user_favorites` | User-whiskey favorite relationship |
| `CollectionItem` | `collection_items` | Bottle tracking with status (sealed/opened/finished), purchase info |
| `LiquorStore` | `liquor_stores` | OSM data: name, lat/lng, address, phone, hours (cached 7 days) |
| `StoreAvailability` | `store_availability` | Community reports: whiskey X is in stock at store Y |
| `Toast` | `toasts` | "Likes" on check-ins (unique per user per rating) |
| `Badge` | `badges` | Badge definitions (10 badges across milestone/style/taste categories) |
| `UserBadge` | `user_badges` | Which users have earned which badges |
| `UserMemory` | `user_memory` | Persistent chat agent memory of user preferences |

### Current Data

- **~9,000 whiskeys** across bourbon, scotch, irish, japanese, rye, canadian, single malt, and blended categories
- Flavor profiles generated for ~4,000+ whiskeys
- AI descriptions generated for ~500+ whiskeys
- Sources: Distiller.com, OpenFoodFacts, Whiskybase, GitHub datasets, manual curation

---

## ML & Recommendation Engine

### Content-Based Filtering (Current)

Located in `backend/app/ml/recommender.py`.

**Feature vector (27 dimensions):**
- 8 one-hot encoded category features (bourbon, scotch, irish, japanese, rye, canadian, single malt, blended)
- 3 normalized numeric features (ABV/70, age/30, price/300)
- 16 flavor tag binary features (smoky, peaty, sweet, fruity, floral, spicy, vanilla, caramel, honey, oak, nutty, citrus, chocolate, leather, herbal, grain)

**Recommendation flow:**
1. Get all whiskeys the user rated 3.5+ stars
2. Convert each to a 27-dim vector, compute centroid (average)
3. Score all unrated whiskeys by cosine similarity to centroid
4. Return top N results

**Quiz flow:**
1. Convert quiz answers to a target vector (style preference, smokiness, body/ABV, budget/price, flavor tags)
2. Score all whiskeys by cosine similarity to target
3. Generate plain-English reason for each match
4. Return top 6

### Collaborative Filtering (Planned)

PyTorch embedding model (user_id + whiskey_id -> predicted rating). Training requires ~500+ ratings from real users. Architecture: `nn.Embedding` for users and whiskeys, dot product + bias for score prediction.

---

## Testing

### Test Architecture

- **Framework**: pytest with FastAPI TestClient
- **Database**: In-memory SQLite (isolated per test via transaction rollback)
- **Auth**: Fixtures that register test users and return JWT headers
- **External APIs**: Mocked (Overpass API uses `unittest.mock.patch`)
- **Rate limiter**: Cleared between tests to prevent 429 errors
- **Badges**: Seeded in fixtures so badge evaluation works during rating tests

### Running Tests

```bash
cd backend

# Run all tests
.venv/bin/python3 -m pytest tests/ -v

# Run specific test file
.venv/bin/python3 -m pytest tests/test_auth.py -v

# Run with short traceback
.venv/bin/python3 -m pytest tests/ --tb=short

# Run a single test
.venv/bin/python3 -m pytest tests/test_whiskeys.py::TestRateWhiskey::test_rate_success -v
```

### Test Coverage

| Test File | Tests | What's Covered |
|-----------|-------|----------------|
| `test_auth.py` | 11 | Register (success, dupe username, dupe email, validation), login (success, wrong pw, nonexistent), /me (valid, no token, bad token) |
| `test_whiskeys.py` | 20 | List (search, filter by 6 fields, sort 3 ways, pagination), get by ID, create, rate (CheckInResponse format, average update, validation, auth, 404), get ratings, value picks |
| `test_favorites.py` | 8 | Add, idempotent add, 404, unauth, remove, remove non-fav, list, get IDs |
| `test_collection.py` | 11 | Add, 404, unauth, list, filter by status, includes whiskey data, update status, ownership check, delete, stats, empty stats |
| `test_quiz.py` | 6 | Default params, bourbon pref, smoky pref, includes reasons, top_n, marks quiz_completed |
| `test_recommendations.py` | 5 | Cold start, with ratings, excludes rated, top_n, unauth |
| `test_stores.py` | 7 | Nearby (mocked Overpass), cache hit, invalid coords, report availability, 404 store, get availability, haversine math |
| `test_flights.py` | 8 | List themes (count + metadata), beginner, bourbon ladder, world tour, invalid theme, max price, count param |
| `test_gift.py` | 5 | Default, newbie sweet filter, connoisseur, style filter, budget tiers |
| `test_palate.py` | 5 | With ratings, empty profile, unauth, narrative changes, favorites included |
| `test_compare.py` | 3 | Two whiskeys, one 404, missing params |
| `test_trending.py` | 5 | Fallback to top-rated, with activity, category filter, limit, new arrivals ordering |
| `test_pairings.py` | 4 | Bourbon pairings, scotch pairings, smoky flavor bonus, 404 |
| `test_learn.py` | 8 | List categories, get category, 404, list distilleries, get distillery, 404, glossary sorted, definitions exist |
| `test_recommender_ml.py` | 6 | Vector dimensions, normalization, bourbon-bourbon similarity > bourbon-scotch, similarity range, quiz vector weights peat, quiz vector normalized |
| `test_normalizer.py` | 56 | ABV parsing (11), age parsing (10), price parsing (9), rating parsing (5), category normalization (11), region normalization (6), full normalize pipeline (9) |

---

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Required for AI features (chat agent, description generation)
ANTHROPIC_API_KEY=sk-ant-...

# JWT secret (defaults to dev secret if not set)
JWT_SECRET_KEY=your-production-secret-here

# CORS origins (defaults to localhost:5173)
CORS_ORIGINS=http://localhost:5173

# Database URL (defaults to local SQLite)
DATABASE_URL=sqlite:///sipsense.db

# Claude model for blurb generation (defaults to haiku)
CLAUDE_MODEL_SMALL=claude-haiku-4-5-20251001
```

**Without `ANTHROPIC_API_KEY`:** The app works fully except AI-generated descriptions return `{"blurb": null, "status": "no_key"}` and the chat agent won't function. All other features (search, recommendations, quiz, social, etc.) work without any API key.

---

## Navigation Map

The sidebar navigation is organized into four groups:

```
DISCOVER                 PERSONAL                TOOLS                  EXPLORE
---------               ---------               ------                 --------
Browse                  For You                 Compare                Learn
Feed                    Favorites               Flights                Stores
Trending                My Shelf                Gift Finder
Daily                   My Palate               Value Picks
Flavors                 Personality
Taste Quiz
Blind Tasting
```

The **AI Chat** button floats on every page for instant access to the conversational assistant.
