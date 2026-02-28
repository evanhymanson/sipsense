# SipSense — Product Vision & Build Roadmap

## "The app that teaches you whiskey"

---

## The Core Insight

Vivino won wine by solving a specific moment: _"I'm standing in a wine aisle and I have no idea what to buy."_

SipSense wins whiskey by solving a different moment: _"I want to get into whiskey but I don't know where to start and I feel stupid asking."_

Whiskey is uniquely intimidating. Wine drinkers just swirl and sip. Whiskey drinkers feel like they need to decode a language — peat, mash bill, age statements, single malt vs blend, Speyside vs Islay. The gap between casual drinker and enthusiast is a wall, not a ramp.

**SipSense tears down that wall.**

---

## Target User (Be Specific)

**Primary: "The Curious Beginner"**

- Age 25–40, drinks beer or wine casually
- Has had a whiskey they liked once and wants to find more
- Feels embarrassed not knowing the difference between bourbon and scotch
- Doesn't want to spend $80 on something they hate
- Discovery happens on social media, not in liquor stores

**Secondary: "The Enthusiast Upgrader"**

- Already buys bourbon regularly (Maker's, Woodford, Buffalo Trace tier)
- Wants to expand their palate but doesn't know what's next
- Spends $40–100 per bottle
- Actively researches before buying

**Not our user (yet):** collectors, investors, 15-year scotch connoisseurs. They already have their communities.

---

## Product Pillars

### 1. The Learning Layer (Differentiator — build this first)

Education woven into every surface of the app. Not a wiki. Not a separate "learn" tab. Learning happens _in context_, right when the user needs it.

**Features:**

- **Flavor Wheel** — interactive SVG. Tap any flavor node (smoky → peaty → medicinal) and see whiskeys that match, with plain-English explanations
- **Whiskey 101 paths** — short guided journeys:
  - "I only drink bourbon" → here's how to explore from there
  - "I liked Laphroaig" → here's the peated scotch ladder
  - "Under $40 budget" → here's your starter pack
- **Distillery stories** — 200-word narrative cards. Not dry facts. Real stories: why Maker's Mark uses wheat instead of rye, why Islay whisky tastes like the ocean
- **Glossary tooltips** — any jargon term in the UI taps to a plain-English definition. Age statement. NAS. Expression. Mash bill. Single cask.
- **"What makes this whiskey special"** — a single plain-English paragraph on every bottle detail page generated via LLM (Claude API) from the structured data we already have

### 2. The Recommendation Engine (Core — already scaffolded)

Currently: content-based cosine similarity (working).
Next: PyTorch collaborative filtering trained on user ratings.

**New recommendation surfaces:**

- **Taste quiz** — 5-question onboarding quiz (do you like smoky foods? sweet drinks? bold coffee?) → cold-start recommendations without needing prior ratings
- **"If you like X, try Y"** — displayed on every bottle page
- **Budget-aware recs** — "same profile, half the price" surfaced prominently
- **"Next step up"** — for each whiskey, show what an enthusiast drinks when they're ready to level up

### 3. The Discovery Feed (Social, Later)

Not trying to be Instagram. Just enough social proof to help beginners feel less alone.

- Recent community ratings with tasting notes
- "Most rated this week" trending list
- "Staff picks" (curator-driven, can be manually edited)
- Eventually: follow friends, see their collections

---

## Technical Roadmap

### Phase 1 — Educational Foundation (Next Session Priority)

**Goal: Make the app genuinely useful for a beginner before acquiring any users.**

#### Backend additions

- [ ] `LearnContent` DB model — stores distillery stories, flavor explanations, whiskey category guides
- [ ] `/learn/` API router — `GET /learn/distilleries/{slug}`, `GET /learn/categories/{category}`, `GET /learn/glossary`
- [x] `TasteQuiz` endpoint — `POST /quiz/` takes answers, returns cold-start recommendations ✅
- [ ] LLM integration — Claude API call to generate "what makes this special" blurb per whiskey, cached in DB
- [ ] `FlavorNode` model — structured flavor wheel taxonomy (family → subfamily → specific note)

#### Frontend additions

- [ ] **Flavor Wheel page** — interactive SVG component. Click a flavor to filter whiskeys
- [ ] **Learn section** — `/learn` route with category guides and distillery stories
- [x] **Taste Quiz flow** — `/quiz` onboarding page, 5 steps, results page with recommendations ✅
- [ ] **Bottle page upgrade** — add "What makes this special" blurb, flavor tags are clickable, "If you like this, try..." section
- [ ] **Glossary tooltips** — `<Tooltip term="NAS">` component, renders inline definition on hover/tap

#### Data

- [ ] Write 6 category guides (bourbon, scotch, rye, irish, japanese, canadian) — store in DB or markdown files
- [ ] Write flavor wheel taxonomy JSON (3 levels deep, ~60 nodes)
- [ ] Write 20–30 distillery story cards for the most common distilleries in our DB
- [x] Taste quiz question bank (5 questions mapped to flavor profile vectors) ✅

---

### Phase 2 — Recommendation Engine Upgrade (PyTorch) ✅

**Goal: Replace cosine similarity with a real learned model.**

#### What was built

- [x] `backend/app/ml/collaborative_filter.py` — NCF model (user + item embeddings → MLP → predicted rating)
- [x] `backend/app/ml/train.py` — CLI: `python -m app.ml.train` (with synthetic data generation for bootstrapping)
- [x] `backend/app/ml/inference.py` — loads model, caches in memory, runs inference per user_id
- [x] `recommendations.py` router — tries PyTorch model first, falls back to cosine similarity for unknown users
- [x] Synthetic rating generation — 8 user archetypes (bourbon_lover, peat_head, etc.) generate realistic ratings
- [x] Model trained: RMSE=0.089, 80 synthetic users, 1130 items

#### How to retrain

```bash
cd backend
python -m app.ml.train                  # real ratings + synthetic fill
python -m app.ml.train --synthetic-only  # synthetic only
python -m app.ml.train --epochs 50 --lr 0.005  # custom hyperparams
```

#### Learning resources referenced

- PyTorch nn.Embedding docs
- "Neural Collaborative Filtering" paper (He et al., 2017)

#### Next improvements (when real users arrive)

- Retrain with real ratings once 500+ exist (model will auto-mix real + synthetic)
- Add learning rate scheduler for better convergence
- Experiment with deeper MLP or attention-based interactions

---

### Phase 3 — Mobile & Label Scan

**Goal: The Vivino moment — point camera at bottle, get instant info.**

#### Approach

1. React Native (Expo) — shares most component logic with the existing React web app
2. Camera → OCR via Google Cloud Vision API or AWS Rekognition
3. OCR text → fuzzy match against whiskey names in DB (use `rapidfuzz` Python library)
4. Return matched whiskey with full detail page

#### Key files to create

- `mobile/` — new Expo project
- `backend/app/routers/scan.py` — `POST /scan/` endpoint accepts base64 image, returns matched whiskey
- `backend/app/ml/label_matcher.py` — fuzzy matching logic

---

### Phase 4 — Monetization & Growth

- Affiliate links to ReserveBar, Drizly, Total Wine (5–8% commission)
- "SipSense Pro" subscription — advanced flavor profile analytics, unlimited quiz paths, rare bottle alerts
- Distillery partnership API — let craft distilleries add their own educational content + pay for featured placement

---

## Design Principles

1. **Plain English always** — never use jargon without immediately explaining it
2. **No judgment** — the app never makes a user feel dumb for not knowing something
3. **Price transparency** — always show budget-friendly options, never only premium
4. **Learning is the product** — every screen should leave the user knowing something they didn't before
5. **Fast and focused** — no bloat. Each page does one thing well.

---

## Current State (as of Feb 2026)

### What's built ✅

- FastAPI backend with SQLAlchemy ORM + SQLite
- 10k–25k whiskeys in DB (Distiller + OpenFoodFacts + Whiskybase + GitHub CSV)
- `upc` and `source` columns on Whiskey model (with schema migration)
- `/whiskeys/` CRUD + filter routes
- `/recommendations/` — content-based cosine similarity recommender (27-dim feature vectors)
- `/quiz/` — 5-question taste quiz → flavor vector → top 6 recommendations with plain-English reasons
- React + Vite frontend: Browse, Detail, Recommendations, **Taste Quiz** pages
- Dark amber UI theme
- Multi-source scraper pipeline: `scrape_all.sh` (Distiller → OpenFoodFacts → Whiskybase → GitHub CSV)

### Key file locations

```
sipsense/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, router registration
│   │   ├── database.py           # SQLAlchemy setup, get_db dependency
│   │   ├── models.py             # Whiskey (upc, source), UserRating models
│   │   ├── schemas.py            # WhiskeyRead, QuizAnswers, QuizRecommendation, etc.
│   │   ├── routers/
│   │   │   ├── whiskeys.py            # GET/POST /whiskeys/, rate endpoint
│   │   │   ├── recommendations.py     # POST /recommendations/
│   │   │   └── quiz.py                # POST /quiz/
│   │   └── ml/
│   │       ├── recommender.py         # Content-based cosine similarity + quiz vector logic
│   │       ├── collaborative_filter.py # PyTorch NCF model (user/item embeddings → MLP)
│   │       ├── train.py               # Training script: python -m app.ml.train
│   │       ├── inference.py           # Model loading + recommendation serving
│   │       ├── model.pt               # Trained model weights
│   │       └── model_meta.json        # Index mappings + training metrics
│   ├── scraper/
│   │   ├── base.py               # Rate-limited httpx client
│   │   ├── distiller.py          # Distiller.com sitemap + detail scraper
│   │   ├── github_csv.py         # GitHub ML Whiskey Dataset importer
│   │   ├── openfoodfacts.py      # OpenFoodFacts search API (UPC barcodes)
│   │   ├── whiskybase.py         # Whiskybase.com community ratings
│   │   ├── normalizer.py         # Raw data → DB schema mapper
│   │   └── run.py                # CLI: python -m scraper.run --source <name>
│   ├── scrape_all.sh             # Full pipeline: Distiller → OpenFoodFacts → Whiskybase → GitHub
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx               # Router, nav (Browse / Taste Quiz / For You)
    │   ├── api/client.js         # All fetch() calls (listWhiskeys, submitQuiz, etc.)
    │   ├── components/
    │   │   └── WhiskeyCard.jsx
    │   └── pages/
    │       ├── Browse.jsx
    │       ├── WhiskeyDetail.jsx
    │       ├── Recommendations.jsx
    │       └── Quiz.jsx          # 5-step taste quiz + results page
    └── vite.config.js            # /api proxy to localhost:8000
```

### How to run

```bash
# Terminal 1 — backend
cd backend
.venv/bin/uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend
npm run dev

# Scraper — run each source separately (SQLite is single-writer)
cd backend
./scrape_all.sh                                         # full pipeline
.venv/bin/python -m scraper.run --source distiller --resume   # resume if interrupted
.venv/bin/python -m scraper.run --source openfoodfacts
.venv/bin/python -m scraper.run --source whiskybase --limit 20000
```

---

## Next Steps in Priority Order

### 1. Search ✅
Full-text search by name and distillery. Prominent search bar above filters on Browse page, debounced. Backend: `q=` param on `GET /whiskeys/` with SQLite LIKE on name + distillery. Frontend: live results as you type, composable with all existing filters.

### 2. Bottle Detail Page Upgrade ✅
Right now it shows data. It should teach.

- **"What makes this special"** — call Claude API, generate a 2–3 sentence plain-English blurb from name + distillery + category + age + flavor profile. Cache in the DB `description` column. Prioritize top-rated bottles.
- **"If you like this, try..."** — reuse the recommender: take this whiskey as the seed, return top 5 similar
- **Clickable flavor tags** — each tag in `flavor_profile` is a chip; clicking it filters Browse to that flavor

### 3. Better Browse & Filter UI ✅
Right now Browse is likely basic. Make it powerful:

- **Price range slider** — min/max USD, updates results live
- **Region filter** — Speyside, Islay, Highlands, Kentucky, etc. (from DB region column)
- **Sort options** — by rating (desc), price (asc/desc), age (desc), name (asc)
- **Active filter chips** — show applied filters above results, click × to remove
- Filters compose: category + region + price range all work together

### 4. User Favorites & Collections ✅
Let users save bottles they want to try or have tried.

- **Heart/bookmark button** on WhiskeyCard and detail page
- **Collections page** — "Want to Try" and "Have Tried" lists
- Favorites feed back into "For You" recommendations (liked bottles → similarity boost)
- Backend: `UserFavorite` table, `POST /favorites/`, `GET /favorites/{username}`
- Frontend: `Favorites.jsx` page + heart icon component

### 5. Flavor Wheel Page
Interactive SVG at `/flavor-wheel`. Click any node (sweet → caramel → vanilla) and see matching whiskeys.
- Needs a flavor taxonomy JSON (~60 nodes, 3 levels: family → subfamily → specific note)
- Each leaf node maps to a flavor tag in the DB
- Visually impressive, directly serves the "helps beginners" mission

### 6. Learn Section (`/learn`)
- 6 short category guides (bourbon, scotch, rye, irish, japanese, canadian) — stored as markdown or in DB
- 20–30 distillery story cards (200 words each, narrative not dry facts)
- `<Tooltip term="NAS">` component — hover/tap any jargon term for a plain-English definition

### 7. Authentication
Right now users are just username strings in localStorage. Add JWT auth so ratings persist across devices.
- `python-jose` + `passlib` in FastAPI (standard pattern, well documented)
- `User` model in DB, `/auth/register` and `/auth/login` routes
- Frontend: login modal, store JWT in localStorage

### 8. PyTorch Recommendation Model (Phase 2) ✅
NCF model trained with synthetic data. See Phase 2 section for details.
- `python -m app.ml.train` to retrain when real ratings accumulate

### 9. Deploy
- Backend: AWS EC2 (t3.micro free tier) + gunicorn + nginx
- Database: Migrate SQLite → PostgreSQL (one-line SQLAlchemy config change)
- Frontend: build + serve from EC2 or separate CDN

---

## Phase 2.5 — Agentic AI with LangGraph

**Goal: Replace static flows with an AI agent that reasons, uses tools, and holds a real conversation.**

This is the feature that would make SipSense genuinely different from every other whiskey app — including Vivino. Instead of clicking through a static quiz, a user types:

> _"I love Bulleit Rye but I want to try something smokier and under $60"_

And the agent actually figures it out.

---

### What is LangGraph?

LangGraph is a framework (from the LangChain team) for building **stateful, multi-step AI agents** as a graph of nodes. Each node is a function — some call an LLM, some call tools (your DB, external APIs), some route to other nodes based on the result. The graph maintains state across steps, making it easy to build agents that:

- Ask clarifying questions when the request is ambiguous
- Use multiple tools in sequence (search → filter → explain)
- Remember the conversation history across turns
- Branch logic based on what the LLM decides

---

### SipSense Agent: "Ask SipSense"

A chat interface at `/chat` powered by a LangGraph agent. The agent has access to a set of tools backed by your existing backend:

#### Agent Tools

```python
@tool
def search_whiskeys(query: str, category: str = None, max_price: float = None) -> list[dict]:
    """Search the whiskey database by name, flavor, or distillery."""
    # calls your existing /whiskeys/ endpoint with filters

@tool
def get_whiskey_detail(whiskey_id: int) -> dict:
    """Get full detail on a specific whiskey including flavor profile."""

@tool
def get_similar_whiskeys(whiskey_id: int, top_n: int = 5) -> list[dict]:
    """Find whiskeys similar to the given one using the recommender."""
    # calls your existing recommender logic

@tool
def get_quiz_recommendations(flavor_preferences: list, budget: str, style: str) -> list[dict]:
    """Run the taste quiz recommender from extracted preferences."""
    # calls your existing /quiz/ endpoint

@tool
def explain_whiskey_concept(term: str) -> str:
    """Explain a whiskey concept in plain English (NAS, mash bill, peated, etc.)."""
```

#### Agent Graph

```
User message
     ↓
[Intent classifier node]
     ↓
   ┌──────────────────────────────────────┐
   │                                      │
[Search node]   [Recommend node]   [Educate node]
   │                  │                   │
[Format results] [Explain why]    [Plain-English answer]
   │                  │                   │
   └──────────────────┴───────────────────┘
                       ↓
              [Response node]
                       ↓
              Stream to frontend
```

The agent decides which path to take based on the message. "What's a good smoky scotch?" → Recommend path. "What does NAS mean?" → Educate path. "Show me something like Laphroaig but cheaper" → Search + Recommend path.

---

### Why This Beats Static Features

| Static (current) | Agentic (LangGraph) |
|---|---|
| Quiz with 5 fixed questions | Conversation that extracts preferences naturally |
| Cosine similarity scores | Agent explains *why* each bottle fits in plain English |
| Filter dropdowns | "Something smoky, not too expensive, maybe Japanese?" |
| No follow-up | "Actually I hate smoke, show me something different" |
| Dead end after results | "Tell me more about that Hibiki" → full education loop |

---

### Technical Plan

**Backend: `backend/app/routers/chat.py`**
- `POST /chat/` — accepts `{ messages: [...], session_id: str }`
- Uses LangGraph to run the agent graph
- Streams the response token-by-token via `StreamingResponse`

**Backend: `backend/app/ml/agent.py`**
- Defines the LangGraph graph, nodes, and tool bindings
- Uses Claude API (`claude-sonnet-4-6`) as the LLM backbone
- Tools are Python functions that call your existing DB/recommender code directly

**Frontend: `frontend/src/pages/Chat.jsx`**
- Simple chat UI — message input, scrolling message history
- Renders streaming responses character-by-character
- Whiskey cards appear inline when the agent returns results
- Conversation history persists in component state (later: in DB per user)

**Dependencies to add:**
```
langgraph>=0.2.0
langchain-anthropic>=0.3.0
anthropic>=0.40.0
```

---

### Implementation Order

1. `agent.py` — define tools + graph (start with 2–3 tools, add more later)
2. `chat.py` router — wire up `POST /chat/` with streaming
3. `Chat.jsx` — minimal chat UI with streaming display
4. Register `/chat` route in App.jsx + nav link
5. Iterate: add more tools, improve prompts, add memory

---

### The Long-Term Vision

The agent becomes the primary interface. Browse and Quiz stay for users who prefer structure, but the chat becomes the "expert friend" experience that no other whiskey app offers. Eventually:

- **Session memory** — agent remembers your preferences across conversations
- **Proactive suggestions** — "Based on your ratings, a new bottle just dropped you'd love"
- **Multi-agent** — a Researcher agent that looks up real-time prices, a Teacher agent for education, an Enthusiast agent for discovery — orchestrated by a master agent
- **Voice interface** — speak your preference, get spoken recommendations back

---

## Phase 5 — Massive Data Expansion (250k+ Whiskeys)

**Goal:** Build the largest structured whiskey database in existence. More data = better recommendations, better search, more legitimacy.

### Why 250k?

At 10k whiskeys the recommender starts working. At 50k it gets interesting. At 250k+ SipSense becomes a reference database — the kind of thing whiskey writers, retailers, and distilleries would pay to access. It also means every obscure bottle a user photographs will be in the system.

---

### Source Pipeline (run in order, each builds on the last)

#### 1. TTB COLA Registry — ~100k US labels (free, government data)

The US Alcohol and Tobacco Tax and Trade Bureau publishes every approved spirit label as open government data. Every whiskey legally sold in the US has a Certificate of Label Approval (COLA).

- **Data:** Brand name, distillery, class/type (bourbon, scotch, rye...), country, approval date
- **Missing:** ABV, price, tasting notes — but name + category coverage is unmatched
- **Access:** Bulk CSV download from `https://www.ttb.gov/foia/foia-reading-room.shtml`
- **Scraper file to build:** `backend/scraper/ttb.py` (built, but currently broken)
- **Key logic:** Download zip → parse CSV → filter rows where `CLASS/TYPE DESCRIPTION` contains whiskey keywords → normalize → insert (skip ABV requirement for TTB-only entries, set a default)
- **⚠️ STATUS:** TTB shut down their FOIA reading room — URL returns 404 as of Feb 2026. No bulk download available. Skip unless TTB reopens the endpoint. Use `--ttb-file` flag if you manually obtain a CSV.

#### 2. Wikidata SPARQL — ~30–50k structured entries (free, open knowledge graph)

Wikidata has structured data on named whiskey expressions, distilleries, ages, countries. Queried via their free SPARQL API.

- **Data:** Name, distillery, country of origin, ABV (when available), inception year
- **Access:** `https://query.wikidata.org/sparql` — requires proper bot User-Agent header with contact email
- **Scraper file to build:** `backend/scraper/wikidata.py`
- **Key SPARQL pattern:**
  ```sparql
  SELECT ?item ?itemLabel ?distilleryLabel ?countryLabel ?abv WHERE {
    ?item wdt:P31 wd:Q56884561 .        # instance of: whisky
    OPTIONAL { ?item wdt:P176 ?distillery }
    OPTIONAL { ?item wdt:P495 ?country }
    OPTIONAL { ?item wdt:P2665 ?abv }
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
  } LIMIT 50000
  ```
- **⚠️ STATUS:** Scraper built but effectively abandoned. Q56884561 returns 0 results. Q14353 turned out to be a Spanish river (Nervión), not bourbon. Label search only returns ~40 results total. Skip unless someone verifies the correct entity IDs.

#### 3. OpenFoodFacts — ~20k spirits with barcodes (free, Creative Commons)

Open Food Facts is a community-maintained food database with barcode data. Their spirits subset has ABV, country, brand, and sometimes ingredients.

- **Data:** Name, brand, ABV, country, barcode (UPC — useful for future label scanning!)
- **Access:** Full CSV dump at `https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz` (~10GB full dump) or filtered API: `https://world.openfoodfacts.org/cgi/search.pl?search_terms=whiskey&search_simple=1&action=process&json=1`
- **Scraper file to build:** `backend/scraper/openfoodfacts.py`
- **Filter:** `categories_tags` containing `whisky` or `whiskey` or `bourbon` etc.
- **Bonus:** Store UPC/barcode in the DB — powers label scanning later (Phase 3)

#### 4. Multiple Retail Site Scrapers — ~50k with prices (scrapeable HTML)

These are publicly accessible product catalog pages. Each requires its own parser but the data is rich — prices, descriptions, regional info.

| Site | Est. Whiskeys | What's unique |
|---|---|---|
| Total Wine | ~6,000 | Price, staff picks, ratings |
| Spec's (Texas) | ~8,000 | Price, inventory availability |
| ReserveBar | ~4,000 | Premium/allocated bottles |
| The Whisky Exchange (UK) | ~15,000 | Huge scotch/world selection |
| Master of Malt (UK) | ~20,000 | Very detailed tasting notes |

- **Scraper files to build:** `backend/scraper/totalwine.py`, `backend/scraper/masterofmalt.py`
- **Key value:** Real prices. No other free source has current retail prices at scale.
- **Rate limiting:** These sites have anti-bot measures. Use 2–4s delays, rotate User-Agents, use the `RateLimitedClient` base class already in `scraper/base.py`.

#### 5. Common Crawl Index — archived pages, no live scraping needed

Common Crawl is a non-profit that crawls the web monthly and releases the data for free via AWS S3. You can query their index to find archived copies of retailer pages and download them without hitting live servers.

- **Access:** `https://index.commoncrawl.org/CC-MAIN-2024-51-index?url=masterofmalt.com/whiskies/*&output=json`
- **Benefit:** No rate limiting, no bot detection, completely free
- **Scraper file to build:** `backend/scraper/commoncrawl.py`
- **Downside:** Pages may be 1–6 months stale (acceptable for product data)

---

### DB Schema Changes Needed

The current `Whiskey` model needs two new optional fields to support this scale:

```python
# Add to models.py
upc = Column(String, index=True)          # barcode from OpenFoodFacts — enables label scan
source = Column(String, default="manual") # "ttb", "distiller", "wikidata", "openfoodfacts", etc.
```

The `source` field lets you filter by data quality — TTB entries have no ABV or tasting notes, Distiller entries have full detail. The frontend can show a "data completeness" indicator and prioritize enriched entries in recommendations.

---

### Enrichment Pipeline (after bulk import)

Importing 250k names is step 1. Enrichment is step 2 — filling in ABV, descriptions, and flavor profiles for TTB/Wikidata entries that are missing them.

**Cross-source matching:** After importing TTB data, run a fuzzy match (`rapidfuzz` library) against existing Distiller/GitHub entries to merge records. If TTB has "Maker's Mark" and Distiller has "Maker's Mark Bourbon" with full detail, merge them.

**LLM enrichment (selective):** For the top ~10k most-searched whiskeys, call Claude API to generate a description from the name + distillery + category alone. Cache result in the `description` column. Don't do all 250k — cost would be prohibitive. Prioritize by rating_count.

---

### Running Order for Next Data Session

```bash
# 1. Finish current Distiller scrape (~8k total)
python -m scraper.run --source distiller --resume

# 2. TTB bulk import (once scraper/ttb.py is built)
python -m scraper.run --source ttb

# 3. Wikidata SPARQL (once scraper/wikidata.py is built)
python -m scraper.run --source wikidata

# 4. OpenFoodFacts (once scraper/openfoodfacts.py is built)
python -m scraper.run --source openfoodfacts

# 5. Retail sites (longer running, resume-capable)
python -m scraper.run --source masterofmalt --limit 20000
python -m scraper.run --source totalwine --limit 6000
```

**Realistic timeline to 250k:** TTB + Wikidata alone gets to ~150k in a single afternoon (both are bulk downloads/API calls, no page-by-page scraping). Retail sites add another 50–80k over a few days of scraping. OpenFoodFacts adds barcodes on top. 250k is achievable in under a week of intermittent running.
