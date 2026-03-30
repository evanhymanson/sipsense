# SipSense Cocktail Expansion Strategy

Comprehensive strategy for expanding SipSense from a whiskey-focused discovery platform into a cocktail discovery, creation, and social experience — while keeping whiskey at the core.

---

## Why Cocktails?

### Market Opportunity

- The global cocktail & spirits market is massive and growing, driven by the craft cocktail movement and at-home mixology trend accelerated by the pandemic
- Cocktail recipe searches are high-volume: "old fashioned recipe" alone pulls ~200-300K searches/month in the US. Combined cocktail recipe queries likely exceed 2-3M/month
- No dominant app owns the cocktail discovery space the way Vivino owns wine or Untappd owns beer — the market is fragmented across recipe blogs, bartender tools, and liquor brand apps
- Gen Z and Millennials over-index on cocktails vs neat spirits, expanding the addressable market beyond SipSense's current whiskey-enthusiast core
- Cocktail content is inherently **shareable** (photos of homemade drinks, recipe cards, video tutorials) — a natural organic growth driver

### Strategic Fit for SipSense

- SipSense already has **~67 unique cocktail recipes** hardcoded in `pairings.py` across 8 whiskey categories (some duplicates appear across categories like Penicillin in both Scotch and Single Malt)
- An AI bespoke cocktail generation endpoint exists (`/ai/pairings/{id}/ai-cocktail`) using Claude, with AICache-backed caching
- The frontend renders cocktail suggestions (with S3-hosted images) on WhiskeyDetail pages
- Serving style tracking (neat/rocks/cocktail/highball) on check-ins means we're already capturing cocktail consumption signals — though this data hasn't been analyzed yet to confirm adoption rates
- The social layer (feed, toasts, comments, badges) and AI infrastructure (chat agent, recommendations) can be extended rather than rebuilt
- Cocktails are the natural bridge between SipSense's whiskey expertise and a broader spirits audience

### Honest Assessment of Current Cocktail Infrastructure

The foundation exists but is thin. Here's the reality:

| What exists | What it actually is |
|-------------|-------------------|
| "67 cocktail recipes" | Python dictionaries hardcoded in `pairings.py` — not database entities, not searchable, not linkable |
| "AI bespoke cocktails" | A single endpoint that calls Claude Haiku, returns JSON, caches in AICache. Not persisted as shareable entities |
| "Cocktail images" | S3-hosted JPGs fetched via a scraping script. No fallback if image doesn't exist |
| "Chat handles cocktails" | **False.** The LangGraph agent in `agent.py` has zero cocktail tools. Claude can discuss cocktails from general knowledge, but the agent cannot programmatically search, recommend, or build cocktails |
| "Serving style tracking" | The column exists and accepts "cocktail" as a value, but no analytics surface this data |

**Realistic readiness: ~15-20%.** The social layer, AI infrastructure, CDN pipeline, and frontend patterns are reusable. But cocktails as a product feature are basically non-existent — what exists is whiskey pairing suggestions with cocktail names attached.

### Competitive Landscape

| App/Platform | Focus | Strengths | Weaknesses |
|-------------|-------|-----------|------------|
| **Difford's Guide** | Cocktail encyclopedia | 6,000+ recipes, bartender-focused, deep content | No social, no AI, dated UX, no personalization |
| **Mixel** | Recipe app | Clean UI, ingredient-based "what can I make?" search | No community, no spirits catalog, no AI |
| **Cocktail Flow** | Visual recipes | Beautiful step-by-step with videos | No ratings, no personalization, no social |
| **Highball by Studio Neat** | iOS cocktail app | Elegant design, custom recipe creation, iCloud sync | iOS-only, no community, no AI, small catalog |
| **Bartesian** | Connected cocktail machine | One-button cocktails, hardware integration | Requires proprietary machine, limited recipes |
| **Punch Drink** | Editorial cocktail content | Excellent writing, cultural context, trusted by bartenders | No app, no user interaction, not a platform |
| **AllRecipes / Epicurious** | General recipe sites | Massive SEO authority, millions of existing users, UGC | Cocktails are a tiny subcategory, no spirits expertise, no community |
| **Total Wine app** | E-commerce + recipes | Buy ingredients in-app | Recipes are an afterthought, no social |

**Key insight:** No existing cocktail app combines AI personalization + social community + spirits expertise. But the SEO landscape is dominated by general recipe sites (AllRecipes, Epicurious, Food & Wine) who already rank for major cocktail keywords. SipSense's path to winning is through differentiation (AI, personalization, community), not by trying to out-SEO recipe aggregators on generic terms.

**Where SipSense can win:**
- "Best bourbon for an Old Fashioned" — whiskey expertise no recipe site can match
- "What cocktail should I make with Laphroaig?" — AI + spirits catalog integration
- "What can I make with what's in my bar?" — personalized, inventory-aware recommendations
- Community-driven cocktail ratings tied to specific whiskeys used

---

## The Hard Questions

Before diving into features, these tensions need honest answers:

### 1. "Why not just use the AI chat?"

The chat agent can already discuss cocktails via Claude's general knowledge. Why build a whole catalog?

**Answer:** Chat is discovery, not retention. A user asks "how do I make an Old Fashioned?" once. A catalog page with ratings, photos, whiskey pairings, and "Save to My Bar" creates a persistent, SEO-indexed, socially-shareable object that drives repeat visits and organic traffic. The chat is how users find cocktails; the catalog is how they come back.

### 2. "Does this dilute the whiskey brand?"

SipSense is "the whiskey app." Adding cocktails risks becoming "another recipe app."

**Answer:** Frame it as "whiskey-powered cocktails," not "cocktails." The differentiator is always the whiskey catalog connection: "Which specific bourbon makes the best Old Fashioned?" is a question only SipSense can answer with data (ratings, flavor profiles, match scores). Every cocktail page links back to specific bottles. Non-whiskey cocktails (Margarita, Daiquiri) should NOT be in scope for Phase 1 — stay focused.

### 3. "How do you bootstrap ratings with ~1000 users?"

Collaborative filtering needs rating data. With a small user base, cocktail ratings will be sparse.

**Answer:** Three strategies:
1. **Content-based first** — Recommend cocktails by flavor profile similarity to whiskeys the user likes (the "palate bridging" approach). No cold-start problem.
2. **Whiskey check-in bridge** — When a user checks in a whiskey with `serving_style="cocktail"`, prompt: "Which cocktail did you make?" This cross-pollinates existing whiskey engagement into cocktail ratings at zero incremental friction.
3. **AI-seeded ratings** — Pre-populate cocktail difficulty scores, flavor profiles, and "best with" whiskey pairings from AI. Users see a rich page from day one even without UGC.

### 4. "Can we rank for cocktail SEO terms?"

AllRecipes has 50M+ monthly visitors. SipSense has ~1000 users. Can we compete?

**Answer:** Not on generic terms like "cocktail recipes" or "old fashioned recipe" — those are owned by high-DA sites. But we can dominate **long-tail whiskey-cocktail intersection queries**: "best scotch for a Rob Roy," "smoky cocktail recipes with Islay whisky," "cocktails with Maker's Mark." These are low-competition, high-intent, and perfectly aligned with our expertise. Schema.org Recipe markup with aggregate ratings will help us earn rich snippets even at lower DA.

### 5. "What about non-whiskey spirits?"

Most classic cocktails use gin, rum, vodka, or tequila. Whiskey-only limits the catalog.

**Answer:** Phase 1 should be whiskey cocktails only (~150-200 recipes). Non-whiskey spirits enter in later phases as cocktail *ingredients* (e.g., the Cointreau in a Whiskey Sour) but never as browsable spirit categories competing with the whiskey catalog. If the feature succeeds and there's clear demand, a broader spirits expansion can be its own strategy document.

---

## Current State Assessment

### What Actually Exists (Verified)

| Feature | Status | Reality Check |
|---------|--------|--------------|
| Category-specific recipes | Hardcoded | ~67 unique cocktails as Python dicts in `pairings.py` (8 categories, some duplicates across Scotch/Single Malt). Not database entities. |
| AI bespoke cocktails | Single endpoint | `GET /ai/pairings/{id}/ai-cocktail` calls Claude Haiku, returns name/tagline/ingredients/instructions/garnish/glassware/why. Cached in AICache. Falls back to basic highball on failure. Requires auth. |
| Cocktail images | S3 hosted | ~67 images fetched via `scripts/fetch_cocktail_images.py` (Bing scraping → crop → S3 upload). No fallback placeholder if image missing. |
| Cocktail display UI | Basic cards | WhiskeyDetail.jsx renders cocktail cards (image + name + ingredients string + description) under "Cocktail Ideas" heading. |
| Serving style tracking | Schema only | `user_ratings.serving_style` accepts "cocktail" but no analytics, insights, or recommendations surface this data. |
| Chat agent cocktail tools | **None** | `agent.py` has 20+ whiskey tools (search, recommend, compare, flights, gift finder) but ZERO cocktail tools. Claude answers cocktail questions from general knowledge only. |
| Cocktail CSS | Basic | `.cocktail-list` grid, `.cocktail-item` cards with hover effects in `App.css`. Functional but minimal. |

### Reusable Infrastructure (What We Don't Have to Build)

| System | How It Helps Cocktails |
|--------|----------------------|
| Activity feed (`feed.py`) | Can be extended to include cocktail check-ins alongside whiskey check-ins |
| Toast/comment system (`social.py`) | Toasts and comments can be extended to cocktail ratings (pattern: polymorphic via `checkin_comment`, `video_comment`) |
| Badge system (`badges.py`) | 20+ badges with category-based triggers. Cocktail badges plug into same `evaluate_badges()` flow |
| Journey system (`journeys.py`) | Multi-step guided paths with lessons. Cocktail journeys use identical data model (Journey → JourneyStep) |
| Share card generation (`sharecard.py`) | Pillow-based PNG generation for social sharing. Can add cocktail card templates |
| Learn hub (`learn.py`) | Hardcoded educational content by category. Can add cocktail technique and ingredient content |
| User lists (`userlists.py`) | `user_list` / `user_list_item` tables for custom lists. Can reuse for cocktail collections (no need for separate `cocktail_collections` table) |
| S3 image pipeline (`storage.py`) | CDN URL generation, cocktail image caching already implemented |
| Whiskey catalog | 1000+ bottles with flavor profiles, prices, ratings — directly linkable from "Which whiskey to use" on cocktail pages |
| Video feed (`videos.py`) | TikTok-style vertical feed with toasts/comments. Cocktail tutorial videos are a natural content type |
| UPC barcode scanning | `ScanBottle.jsx` + Claude Vision. Can be extended for ingredient barcode scanning |

### What's Missing

| Gap | Impact | Notes |
|-----|--------|-------|
| No cocktail database table | Critical | Cocktails are inline Python dicts, not queryable entities |
| No cocktail detail pages | Critical | Can't link to, share, or SEO-index individual cocktails |
| No cocktail ratings/reviews | Critical | Users can't rate or review cocktails |
| No cocktail search/browse | High | No way to discover cocktails independent of a whiskey page |
| No ingredient normalization | High | Ingredients are comma-separated strings, not structured data. "What can I make?" queries are impossible |
| No "my bar" inventory | High | Can't filter cocktails by what you have at home |
| No cocktail check-ins | High | Can't log "I made this cocktail" as a social action |
| No agent cocktail tools | High | Chat agent can't programmatically search/recommend cocktails |
| No step-by-step instructions | Medium | Current recipes have instructions as a single string, not structured steps |
| No technique education | Low | No content about shaking vs stirring, ice types, etc. |

---

## Product Vision

### The Pitch

**"The whiskey app that teaches you what to do with the bottle."**

SipSense already helps you find, rate, and understand whiskey. Cocktails are the natural next step — turning bottle knowledge into drink-making knowledge. Not a generic recipe app. A whiskey-powered cocktail experience backed by AI, community ratings, and the deepest spirits catalog in the category.

### Core Principles

1. **Whiskey-first, always** — Every cocktail page connects back to specific bottles in the catalog. "Which bourbon makes the best Old Fashioned?" is answered with real data, not generic advice. Non-whiskey cocktails are out of scope.
2. **AI as the differentiator** — No recipe site can generate a custom drink based on your bar inventory, palate profile, and mood. This is the moat.
3. **Social makes it sticky** — Cocktail check-ins with photos of homemade drinks, tagged with the specific whiskey used. The feed becomes richer and more varied.
4. **Education builds authority** — Technique content, ingredient deep dives, and guided cocktail journeys position SipSense as the expert bartender in your pocket.
5. **Mobile-first kitchen UX** — Cocktail making happens with messy hands and a phone propped on the counter. Instructions must be large text, one step at a time, voice-friendly.

---

## Data Model Expansion

### New Tables

Design follows existing SipSense patterns: Integer PKs, `created_at`/`updated_at` timestamps, `server_default=func.now()`, UniqueConstraints via `__table_args__`.

#### `cocktails`

Keep it lean. Only columns needed for Phase 1-2. Additional metadata (calories, season, occasion) can be added later via auto-migration if needed.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| name | String(200) | e.g., "Old Fashioned". Unique, indexed. |
| slug | String(200) | URL-safe, unique, indexed. e.g., "old-fashioned" |
| description | Text | Flavor narrative, 2-3 sentences |
| history | Text | Origin story, cultural context (nullable) |
| category | String(50) | "classic", "modern_classic", "sour", "stirred", "highball", "hot", "tiki", "original". Indexed. |
| base_spirit | String(50) | "bourbon", "rye", "scotch", "irish", "japanese", "blended_whiskey". Indexed. |
| difficulty | String(20) | "easy", "intermediate", "advanced" |
| prep_time_minutes | Integer | Default 5 |
| glassware | String(50) | "rocks", "coupe", "highball", "martini", "collins", "mug", "nick_and_nora" |
| technique | String(50) | "stirred", "shaken", "built", "blended", "muddled" |
| garnish | String(200) | Description of garnish |
| instructions | Text | JSON array of step strings: `["Place sugar cube in glass", "Add bitters...", ...]` |
| tips | Text | Pro tips, variations (nullable) |
| flavor_profile | Text | JSON: `{"sweet": 3, "sour": 2, "bitter": 4, "spirit_forward": 5, "refreshing": 2}` (1-5 scale) |
| image_url | String(500) | S3 CDN path |
| source | String(20) | "curated", "ai_generated". Default "curated". |
| is_featured | Boolean | Default false. Editorial pick. |
| rating_avg | Float | Denormalized average rating. Default 0. |
| rating_count | Integer | Denormalized count. Default 0. |
| created_at | DateTime | `server_default=func.now()` |
| updated_at | DateTime | `server_default=func.now(), onupdate=func.now()` |

**What's deliberately excluded:** `author_id`, `is_approved`, `whiskey_id` (FK), `abv_estimate`, `calories_estimate`, `season`, `occasion`, `serves`, `video_url`. These can be added in later phases if needed. Start lean.

#### `cocktail_ingredients`

Normalized ingredient list per cocktail. Enables "what can I make?" search.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| cocktail_id | Integer FK → cocktails | `ondelete="CASCADE"` |
| ingredient_id | Integer FK → ingredients | `ondelete="CASCADE"` |
| amount | String(50) | "2 oz", "1 dash", "1 barspoon", "to taste" |
| is_optional | Boolean | Default false. Garnish or optional modifier. |
| sort_order | Integer | Display order in recipe |
| notes | String(200) | "preferably overproof", "freshly squeezed" (nullable) |

UniqueConstraint on `(cocktail_id, ingredient_id)`.

#### `ingredients`

Master ingredient catalog. Keep simple — this is a lookup table, not a product catalog.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| name | String(100) | e.g., "Angostura Bitters". Unique, indexed. |
| slug | String(100) | URL-safe, unique |
| category | String(50) | "spirit", "liqueur", "bitter", "syrup", "juice", "garnish", "mixer", "other" |
| subcategory | String(50) | "bourbon", "amaro", "aromatic_bitter", "citrus", etc. (nullable) |
| is_common | Boolean | Default false. Likely in a home bar — used for quick-add UI. |

**What's deliberately excluded:** `description`, `image_url`, `shelf_life_days`, `whiskey_id` FK. Not needed for Phase 1. The ingredient table is for structured recipe data and "what can I make?" matching, not for browsing.

#### `user_bar`

Tracks what ingredients a user has at home.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | Integer FK → users | `ondelete="CASCADE"` |
| ingredient_id | Integer FK → ingredients | `ondelete="CASCADE"` |
| added_at | DateTime | `server_default=func.now()` |

UniqueConstraint on `(user_id, ingredient_id)`.

#### `cocktail_ratings`

User reviews of cocktails. Parallels `user_ratings` for whiskeys.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | Integer FK → users | `ondelete="CASCADE"` |
| cocktail_id | Integer FK → cocktails | `ondelete="CASCADE"` |
| score | Float | 1-5 stars |
| notes | Text | Tasting notes, modifications (nullable) |
| image_path | String(500) | Photo of the made cocktail (nullable) |
| whiskey_used_id | Integer FK → whiskeys | Which specific whiskey they used (nullable) |
| created_at | DateTime | `server_default=func.now()` |

UniqueConstraint on `(user_id, cocktail_id)` — one rating per user per cocktail (matches whiskey pattern).

#### `cocktail_saves`

User bookmarks/favorites for cocktails. Mirrors `user_favorites` pattern.

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | Integer FK → users | `ondelete="CASCADE"` |
| cocktail_id | Integer FK → cocktails | `ondelete="CASCADE"` |
| created_at | DateTime | `server_default=func.now()` |

UniqueConstraint on `(user_id, cocktail_id)`.

### Tables NOT Needed (Reuse Existing)

| Proposed | Use Instead | Why |
|----------|------------|-----|
| `cocktail_collections` | `user_list` / `user_list_item` | Existing user list system already supports custom named lists. Add a `list_type` column ("whiskey" or "cocktail") or a nullable `cocktail_id` FK to `user_list_item`. |
| `cocktail_toasts` | `toast` table | Extend with nullable `cocktail_rating_id` FK alongside existing `rating_id` FK. |
| `cocktail_comments` | `checkin_comment` | Extend with nullable `cocktail_rating_id` FK. |

This avoids table proliferation and keeps social features unified.

---

## Feature Roadmap

### Phase 1: Foundation (Cocktail Catalog, Detail Pages, My Bar)

**Goal:** Make cocktails browsable, searchable, linkable, and inventory-aware. Create SEO value and demonstrate the core value proposition.

**Why My Bar is in Phase 1 (not Phase 3):** "What can I make with what I have?" is the single most compelling feature for a cocktail app. It's what distinguishes SipSense from a recipe blog. Launching without it means launching as a worse version of Difford's Guide. The `user_bar` table and matching query are not complex — they should ship with the catalog.

#### Backend

- Create `cocktails`, `cocktail_ingredients`, `ingredients`, `user_bar` tables in `models.py`
- Seed script to:
  - Migrate ~67 existing recipes from `pairings.py` dicts into `cocktails` table
  - Parse ingredient strings into normalized `cocktail_ingredients` rows
  - Populate `ingredients` master table (~100-150 common cocktail ingredients)
  - Expand catalog to ~150-200 curated whiskey cocktail recipes (AI-assisted generation + editorial review)
- New router: `cocktails.py` with endpoints:
  - `GET /api/cocktails` — browse/search with filters (base_spirit, category, difficulty, technique, q text search). Pagination via skip/limit.
  - `GET /api/cocktails/{slug}` — full detail with ingredients, instructions, flavor profile
  - `GET /api/cocktails/featured` — editorial picks (is_featured=True)
  - `GET /api/cocktails/for-whiskey/{whiskey_id}` — cocktails matching a whiskey's category (replaces pairings cocktail section)
  - `GET /api/cocktails/makeable` — cocktails the authenticated user can make with their bar (requires auth)
  - `GET /api/cocktails/almost` — cocktails missing 1-2 ingredients (requires auth)
- New router: `bar.py` with endpoints:
  - `GET /api/bar` — list user's bar inventory
  - `POST /api/bar` — add ingredient by ID
  - `DELETE /api/bar/{ingredient_id}` — remove ingredient
  - `GET /api/bar/suggestions` — "buy this one ingredient to unlock N more cocktails"
  - `POST /api/bar/auto-populate` — scan user's whiskey collection and auto-add matching spirit ingredients
- Wire into `main.py` router registration
- Add cocktail-related indexes in `database.py`

#### Frontend

- New page: `Cocktails.jsx` at `/cocktails` — browse grid with filters, search, featured carousel
  - No auth required for browsing
  - "What Can You Make?" section (requires auth, prompts My Bar setup)
  - Filter chips: base spirit, category, difficulty
  - Sort: popular (rating_count), top rated (rating_avg), newest
- New page: `CocktailDetail.jsx` at `/cocktail/:slug` — full recipe page
  - Hero image with difficulty/time/technique badges
  - Ingredient list with "I have this" checkboxes (connected to My Bar)
  - Step-by-step instructions in **large text, one step visible at a time** (kitchen mode for messy hands)
  - "Which Whiskey to Use" section: whiskey cards from catalog filtered by base_spirit, sorted by rating
  - Flavor profile bar chart (sweet/sour/bitter/spirit-forward/refreshing)
  - Related cocktails (same base_spirit, similar flavor profile)
  - Schema.org `Recipe` JSON-LD for SEO rich snippets
- New page: `MyBar.jsx` at `/bar` — visual ingredient shelf
  - Grid of ingredient chips organized by category (spirits, bitters, syrups, juices, garnishes)
  - Quick-add from "common ingredients" preset list
  - "Auto-add from my collection" button (links whiskey collection to bar)
  - "What can I make?" count prominently displayed
  - "Almost there" section: cocktails missing 1-2 ingredients
- Update `WhiskeyDetail.jsx` to link cocktail suggestions to proper detail pages
- Add "Cocktails" nav item to main navigation
- New component: `CocktailJsonLd.jsx` — Schema.org Recipe structured data (mirrors `WhiskeyJsonLd.jsx` pattern)

#### AI Integration

- Add 3 new tools to LangGraph agent in `agent.py`:
  - `search_cocktails` — search catalog by name, base_spirit, category, difficulty
  - `get_cocktail_recipe` — retrieve full recipe details for a specific cocktail
  - `cocktail_for_whiskey` — best cocktails for a specific bottle based on category + flavor alignment

### Phase 2: Social & Engagement (Check-ins, Ratings, Sharing)

**Goal:** Let users log cocktails they've made, rate them, share photos, and engage with each other.

#### Backend

- `cocktail_ratings` + `cocktail_saves` tables and endpoints:
  - `POST /api/cocktails/{id}/rate` — rate with photo, notes, which whiskey used
  - `GET /api/cocktails/{id}/reviews` — paginated reviews with user info
  - `POST /api/cocktails/{id}/save` / `DELETE /api/cocktails/{id}/save`
  - `GET /api/cocktails/saved` — list saved cocktails
- Extend `feed.py` to include cocktail check-ins in activity feed
  - New feed item type alongside existing whiskey check-ins
  - Same pagination, filtering, friends-only mode
- Extend toast/comment system for cocktail ratings:
  - Add `cocktail_rating_id` nullable FK to `toast` and `checkin_comment` tables
- **Whiskey check-in bridge**: When a user submits a whiskey rating with `serving_style="cocktail"`, return a prompt suggesting they also rate the cocktail they made. Frontend shows a "Rate the cocktail?" card linking to the relevant cocktail detail page.
- Badge triggers for cocktail milestones:
  - "Home Bartender" — first cocktail check-in
  - "Shaken Not Stirred" — rate 5 shaken cocktails
  - "Mixologist" — rate 25 cocktails
  - "Cocktail Explorer" — rate cocktails in 5+ categories
- Extend `sharecard.py` with cocktail share card template
- Update denormalized `rating_avg` and `rating_count` on `cocktails` table after each new rating

#### Frontend

- Check-in form on cocktail detail page
  - 1-5 star rating
  - Notes field
  - "Whiskey used" dropdown (filtered to base_spirit category from user's collection)
  - Photo upload (optional but encouraged with badge incentive)
- Cocktail check-in cards in activity feed (new component: `CocktailCheckInCard.jsx`)
- Save/bookmark button on cocktail cards and detail pages
- "Cocktails" tab on Profile page (`/me`) showing user's cocktail ratings, saved cocktails, and stats
- Photo gallery on cocktail detail page from user-uploaded images

#### AI Integration

- Post-check-in cocktail recommendation: "You enjoyed the Whiskey Sour — try the Gold Rush next"
- Add `rate_cocktail` tool to chat agent
- Chat: "Based on cocktails you've enjoyed, try..." personalization

### Phase 3: Smart Recommendations & Video

**Goal:** Personalized cocktail recommendations powered by palate data, and cocktail tutorial video content.

#### Cocktail Recommendation Engine

Extend the existing content-based recommender (not NCF — insufficient cocktail rating data for collaborative filtering at this stage):

1. **Palate bridging** — Map whiskey palate profile to cocktail preferences:
   - User prefers smoky whiskeys (high peat/smoke tags) → spirit-forward cocktails (Penicillin, Rob Roy, Godfather)
   - User prefers sweet/smooth (high vanilla/caramel/honey tags) → balanced, sweet cocktails (Old Fashioned, Mint Julep, Gold Rush)
   - User prefers complex/sherried (high dried fruit/spice tags) → multi-ingredient layered cocktails (Paper Plane, Blood & Sand, Vieux Carre)
   - User prefers light/floral (high floral/citrus/grain tags) → refreshing cocktails (Japanese Highball, Irish Maid, Sakura Spritz)

2. **Flavor profile cosine similarity** — Same approach as whiskey recommender but over the 5-dimension cocktail flavor vector (sweet/sour/bitter/spirit-forward/refreshing)

3. **Inventory-aware ranking** — Boost cocktails the user can actually make with their bar inventory. Penalize cocktails requiring many missing ingredients.

4. **Check-in signals** — Users who rate a cocktail highly see more of that category/technique

#### Backend

- `GET /api/cocktails/recommended` — personalized cocktail recommendations
- `GET /api/cocktails/trending` — most-checked-in cocktails in recent window
- Extend daily discovery concept: "Cocktail of the Day" alongside Daily Discovery whiskey
- Add `recommend_cocktail` and `generate_custom_cocktail` tools to chat agent

#### Video Integration

SipSense already has a TikTok-style video feed (`/videos`). Cocktail tutorials are perfect video content.

- Add `cocktail_id` nullable FK to `videos` table — tag videos with cocktail recipes
- Cocktail detail pages show tagged tutorial videos
- Video feed can filter by "cocktail tutorials"
- This is a content strategy win: cocktail-making videos are the #1 engagement type on beverage social media

### Phase 4: Education & Journeys

**Goal:** Teach bartending skills through guided content, elevating SipSense as the authority.

#### Cocktail Journeys (extend existing journey system)

The `Journey` → `JourneyStep` model already supports multi-step paths with lessons and tasting prompts. Seed new cocktail-focused journeys:

- **"Whiskey Cocktail 101"** — Old Fashioned → Whiskey Sour → Manhattan → Sazerac → Paper Plane (progressive complexity)
- **"Build Your Home Bar"** — 5 steps, each introducing new ingredients + cocktails they unlock. Ties directly into My Bar feature.
- **"Around the World in Whiskey Cocktails"** — Japanese Highball → Irish Coffee → Rob Roy → Bourbon Smash → Canadian Cocktail
- **"From Simple to Complex"** — 3-ingredient cocktails → 5+ ingredient cocktails with technique lessons
- **"Classic to Modern"** — Pre-Prohibition classics → modern craft innovations

#### Learn Hub Expansion

Add to `learn.py` (follows existing pattern of hardcoded educational content):

- **Technique pages**: Shaking, stirring, muddling, building, ice science, garnish craft
- **Ingredient deep dives**: Bitters (what they are, major brands), Vermouths (sweet vs dry, shelf life), Syrups (making your own)
- **"Cocktail Basics" guide**: Equivalent of existing category guides but for cocktail fundamentals

#### AI Integration

- Chat explains techniques contextually ("How do I dry shake?")
- AI-powered "What went wrong?" troubleshooter
- Daily cocktail trivia questions (extend existing daily quiz)

### Phase 5: Community & Commerce

**Goal:** User-generated recipes and monetization paths.

**Important:** Only pursue user-submitted recipes if Phase 2 metrics show strong cocktail check-in adoption. With a small user base, UGC will be sparse and potentially low quality.

#### User-Created Recipes (Conditional)

- Recipe submission via `POST /api/cocktails/submit`
- Admin moderation queue (reuse existing admin patterns)
- Recipe forking: "Make your own version" of any cocktail
- Use existing `user_list` / `user_list_item` for cocktail collections (add `cocktail_id` FK to `user_list_item`)
- Trending user recipes on browse page

#### Monetization

**Affiliate & Buy Links:**
- Ingredient buy links on cocktail detail pages (Amazon, Total Wine affiliate)
- "Buy all ingredients" bundle link
- Whiskey buy links within cocktail context ("Best bourbon for this recipe" → affiliate link)
- Barware recommendations (shakers, jiggers, glassware)

**Sponsored Content:**
- Sponsored cocktail recipes from spirit brands ("Featured by Maker's Mark")
- Branded cocktail challenges ("Bulleit Bourbon Cocktail Competition")

**Premium Features:**
- Unlimited AI cocktail generation (free tier: 3/day)
- Advanced "My Bar" features (substitute suggestions, shopping list optimization)
- Batch calculator (scale recipes for parties)
- Printable recipe cards

---

## UI/UX Concepts

### Cocktail Browse Page (`/cocktails`)

```
+----------------------------------------------------------+
|  [Search cocktails...]                    [Filters v]     |
+----------------------------------------------------------+
|                                                           |
|  FEATURED COCKTAILS            (horizontal scroll)        |
|  +--------+  +--------+  +--------+  +--------+          |
|  | Paper  |  | Peni-  |  | Gold   |  | Boule- |          |
|  | Plane  |  | cillin |  | Rush   |  | vardier|          |
|  | ****   |  | *****  |  | ****   |  | ****   |          |
|  +--------+  +--------+  +--------+  +--------+          |
|                                                           |
|  WHAT CAN YOU MAKE?          [Set up My Bar ->]           |
|  You have 12 ingredients. You can make 23 cocktails!      |
|                                                           |
|  BROWSE BY BASE SPIRIT                                    |
|  [Bourbon] [Rye] [Scotch] [Irish] [Japanese]             |
|                                                           |
|  BROWSE BY STYLE                                          |
|  [Classic] [Modern] [Sour] [Stirred] [Highball] [Hot]   |
|                                                           |
|  ALL COCKTAILS              Sort: [Popular v]             |
|  +--------+  +--------+  +--------+                      |
|  |  img   |  |  img   |  |  img   |                      |
|  | Old    |  | Manhat-|  | Whiskey|                      |
|  | Fash.  |  | tan    |  | Sour   |                      |
|  | Bourbon|  | Rye    |  | Any    |                      |
|  | Easy   |  | Easy   |  | Easy   |                      |
|  | *****  |  | ****   |  | ****   |                      |
|  | [can   |  | [need  |  | [can   |  ← My Bar status    |
|  |  make] |  |  1]    |  |  make] |                      |
|  +--------+  +--------+  +--------+                      |
+----------------------------------------------------------+
```

### Cocktail Detail Page (`/cocktail/:slug`)

```
+----------------------------------------------------------+
|  [< Back]                         [Save] [Share]          |
+----------------------------------------------------------+
|                                                           |
|  +------------------+  OLD FASHIONED                      |
|  |                  |  **** (4.2) · 47 ratings            |
|  |   [hero image]   |  Classic · Bourbon · Stirred        |
|  |                  |  Easy · 3 min · Rocks glass         |
|  +------------------+                                     |
|                                                           |
|  "The cocktail that started it all. A study in           |
|   simplicity — spirit, sugar, water, bitters."            |
|                                                           |
|  INGREDIENTS                     Serves: [1] [2] [4]     |
|  +----------------------------------------------+        |
|  | [x] 2 oz bourbon           [Buy ->]          |        |
|  |     Best with: Maker's Mark, Buffalo Trace    |        |
|  | [x] 1 sugar cube           [Buy ->]          |        |
|  | [x] 2 dashes Angostura     [Buy ->]          |        |
|  | [x] Orange peel                               |        |
|  | [ ] Luxardo cherry (optional)                 |        |
|  +----------------------------------------------+        |
|  [I have all of these!]  [Add missing to bar]            |
|                                                           |
|  INSTRUCTIONS              [Start Kitchen Mode ->]        |
|  1. Place sugar cube in rocks glass                       |
|  2. Add bitters, muddle until dissolved                   |
|  3. Add large ice cube                                    |
|  4. Pour bourbon over ice                                 |
|  5. Stir gently 15-20 seconds                            |
|  6. Express orange peel over drink, drop in               |
|                                                           |
|  [Kitchen Mode: full-screen, one step at a time,         |
|   large text, prev/next buttons for messy hands]          |
|                                                           |
|  PRO TIPS                                                 |
|  - Use a large ice cube for slower dilution              |
|  - Try demerara sugar for a richer profile               |
|  - A higher-proof bourbon (100+) stands up to dilution   |
|                                                           |
|  WHICH WHISKEY TO USE                                     |
|  +--------+  +--------+  +--------+                      |
|  |Buffalo |  |Maker's |  |Woodford|  (WhiskeyCard        |
|  |Trace   |  |Mark    |  |Reserve |   from catalog,      |
|  |$25 94% |  |$30 91% |  |$35 89% |   sorted by rating)  |
|  +--------+  +--------+  +--------+                      |
|                                                           |
|  FLAVOR PROFILE                                           |
|       Sweet ████████░░ 4/5                                |
|        Sour ░░░░░░░░░░ 0/5                                |
|      Bitter ██████░░░░ 3/5                                |
|  Sp. Forward████████░░ 4/5                                |
|  Refreshing ██░░░░░░░░ 1/5                                |
|                                                           |
|  HISTORY                                                  |
|  First documented in 1806 as "a stimulating liquor..."   |
|                                                           |
|  TUTORIAL VIDEOS                 (if tagged videos exist) |
|  [video thumbnail] [video thumbnail]                      |
|                                                           |
|  +-------------------------------------------+           |
|  | RATE THIS COCKTAIL                         |           |
|  | [*] [*] [*] [*] [*]                       |           |
|  | Notes: [                              ]    |           |
|  | Whiskey used: [Select from collection v]   |           |
|  | [Upload photo]                             |           |
|  | [Submit Check-In]                          |           |
|  +-------------------------------------------+           |
|                                                           |
|  REVIEWS (47)                     Sort: [Recent v]        |
|  +-------------------------------------------+           |
|  | @whiskeylover · **** · 2 days ago         |           |
|  | Used: Eagle Rare 10                        |           |
|  | "Incredible with a high-proof bourbon..."  |           |
|  | [photo]                                    |           |
|  | [Toast] 12  [Comment] 3                   |           |
|  +-------------------------------------------+           |
|                                                           |
|  SIMILAR COCKTAILS                                        |
|  +--------+  +--------+  +--------+                      |
|  |Boulev- |  |Manhat- |  |Sazerac |                      |
|  |ardier   |  |tan     |  |        |                      |
|  +--------+  +--------+  +--------+                      |
+----------------------------------------------------------+
```

### My Bar Page (`/bar`)

```
+----------------------------------------------------------+
|  MY BAR                          [+ Add Ingredient]       |
+----------------------------------------------------------+
|                                                           |
|  You can make 23 cocktails with your bar!                 |
|  Buy Aperol to unlock 7 more ->                           |
|                                                           |
|  [Auto-add from my whiskey collection]                    |
|                                                           |
|  SPIRITS (4)                                              |
|  [Maker's Mark] [Jameson] [Monkey Shoulder] [Bulleit Rye]|
|                                                           |
|  BITTERS (3)                                              |
|  [Angostura] [Peychaud's] [Orange Bitters]               |
|                                                           |
|  SYRUPS & SWEETENERS (4)                                  |
|  [Simple Syrup] [Honey] [Demerara] [Grenadine]          |
|                                                           |
|  JUICES & MIXERS (5)                                      |
|  [Lemon] [Lime] [Ginger Beer] [Soda Water] [Tonic]      |
|                                                           |
|  GARNISHES (3)                                            |
|  [Orange] [Lemon] [Maraschino Cherry]                    |
|                                                           |
|  QUICK ADD (common ingredients)                           |
|  [+ Sugar] [+ Egg White] [+ Club Soda] [+ Mint]         |
|                                                           |
|  WHAT YOU CAN MAKE                    [View All ->]       |
|  +--------+  +--------+  +--------+  +--------+          |
|  | Old    |  | Whiskey|  | Mint   |  | Gold   |          |
|  | Fash.  |  | Sour   |  | Julep  |  | Rush   |          |
|  +--------+  +--------+  +--------+  +--------+          |
|                                                           |
|  ALMOST THERE (need 1 more ingredient)                    |
|  +--------+  +--------+  +--------+                      |
|  |Penicil-|  |Paper   |  |Blood & |                      |
|  |lin     |  |Plane   |  |Sand    |                      |
|  |+Ginger |  |+Aperol |  |+Cherry |                      |
|  | Syrup  |  |        |  |Heering |                      |
|  +--------+  +--------+  +--------+                      |
+----------------------------------------------------------+
```

### Kitchen Mode (full-screen overlay on CocktailDetail)

```
+----------------------------------------------------------+
|  OLD FASHIONED              Step 3 of 6       [X Close]   |
+----------------------------------------------------------+
|                                                           |
|                                                           |
|                                                           |
|           Add a large ice cube                            |
|                                                           |
|           to the rocks glass                              |
|                                                           |
|                                                           |
|                                                           |
+----------------------------------------------------------+
|                                                           |
|     [<< Previous]                    [Next >>]            |
|                                                           |
+----------------------------------------------------------+

Large text. Big tap targets. No scrolling.
Designed for phone propped on counter with wet hands.
```

---

## AI Integration Deep Dive

### New Chat Agent Tools (Phased)

**Phase 1 (ship with catalog):**

| Tool | Description | Example Query |
|------|-------------|---------------|
| `search_cocktails` | Search catalog by name, base_spirit, category, difficulty | "Find me a smoky cocktail" |
| `get_cocktail_recipe` | Retrieve full recipe and details by slug | "How do I make a Penicillin?" |
| `cocktail_for_whiskey` | Best cocktails for a specific bottle | "What cocktail brings out the best in Lagavulin 16?" |

**Phase 2-3 (ship with social + recommendations):**

| Tool | Description | Example Query |
|------|-------------|---------------|
| `recommend_cocktail` | Personalized rec based on palate + bar inventory | "What should I make tonight?" |
| `generate_custom_cocktail` | AI creates a new recipe from constraints | "Make me something with Laphroaig and honey" |
| `check_bar_inventory` | See what user has, what they can make | "What can I make with what I have?" |
| `suggest_bar_additions` | Recommend next purchase to unlock most new cocktails | "What should I buy next?" |
| `cocktail_substitutions` | Find ingredient swaps | "I don't have Aperol, what can I use?" |
| `scale_recipe` | Adjust servings for parties | "Scale the Whiskey Sour for 8 people" |

### AI-Generated Custom Cocktails (Enhanced)

Expand the existing `/ai/pairings/{id}/ai-cocktail` into a standalone endpoint:

**`POST /api/cocktails/generate`** (authenticated)

Input:
```json
{
  "base_spirit": "scotch",
  "specific_whiskey_id": 42,
  "mood": "warming",
  "complexity": "simple",
  "style_reference": "something like a Penicillin but less sweet",
  "use_my_bar": true
}
```

Output:
```json
{
  "name": "The Highland Dusk",
  "tagline": "Where heather honey meets campfire smoke",
  "ingredients": [
    {"amount": "2 oz", "item": "Laphroaig 10", "role": "base", "why": "Provides the smoky backbone"},
    {"amount": "0.75 oz", "item": "heather honey syrup", "role": "sweetener", "why": "Echoes the floral notes"},
    {"amount": "0.5 oz", "item": "lemon juice", "role": "acid", "why": "Brightens and balances the smoke"},
    {"amount": "2 dashes", "item": "Peychaud's bitters", "role": "seasoning", "why": "Adds floral complexity"}
  ],
  "instructions": [
    "Combine all ingredients in a shaker with ice",
    "Shake vigorously for 12 seconds",
    "Double-strain into a chilled coupe",
    "Express a lemon peel over the surface"
  ],
  "garnish": "Lemon peel spiral",
  "glassware": "coupe",
  "technique": "shaken",
  "flavor_profile": {"sweet": 3, "sour": 3, "bitter": 2, "spirit_forward": 4, "refreshing": 3},
  "why_it_works": "The honey syrup tames Laphroaig's intensity while lemon creates a bright counterpoint to the smoke.",
  "variations": [
    "Swap honey for maple syrup for a more autumnal character",
    "Try with Highland Park 12 for less smoke, more balance"
  ],
  "difficulty": "intermediate",
  "prep_time_minutes": 5
}
```

Key decisions:
- **Don't persist AI-generated cocktails to the catalog** — they're ephemeral creations. Different Claude model versions produce different recipes, and quality varies. Keep the catalog curated.
- **Do cache them** in AICache with a user-specific key so they can be recalled
- **Rate limit**: 3/day free, unlimited for premium

### Palate Bridging Logic (Detailed)

This is SipSense's unique advantage — no recipe site has a user's whiskey palate data to inform cocktail recommendations.

**Mapping whiskey flavor tags to cocktail flavor profiles:**

| Whiskey Palate Signal | Cocktail Recommendation Bias | Example Cocktails |
|----------------------|-----------------------------|--------------------|
| High smoke/peat | Boost `spirit_forward` and `bitter` cocktails | Penicillin, Rob Roy, Godfather, Smoky Cokey |
| High vanilla/caramel/honey | Boost `sweet` and balanced cocktails | Old Fashioned, Gold Rush, Mint Julep, Hot Toddy |
| High spice/pepper/cinnamon | Boost `spirit_forward` with spice elements | Sazerac, Vieux Carre, Toronto, Rye Witch |
| High fruit/floral/citrus | Boost `refreshing` and `sour` cocktails | Whiskey Sour, Japanese Highball, Irish Maid, Sakura Spritz |
| High oak/leather/tobacco | Boost `bitter` and stirred cocktails | Manhattan, Boulevardier, Bobby Burns, Algonquin |
| Prefers high ABV (cask strength) | Boost `spirit_forward`, suggest stirred over shaken | Manhattan, Sazerac, De La Louisiane |
| Prefers low ABV / smooth | Boost `refreshing`, highball-style drinks | Japanese Highball, Whisky Ginger, Irish Buck |

Implementation: cosine similarity between user's flavor tag frequency vector (from whiskey ratings) and a pre-computed cocktail-to-flavor-tag bridge matrix.

---

## SEO & Content Strategy

### Realistic SEO Assessment

SipSense cannot outrank AllRecipes or Epicurious for "old fashioned recipe" or "cocktail recipes." Those are owned by sites with 50M+ monthly visitors and domain authority above 80.

**Where SipSense CAN win:**

| Keyword Category | Example Queries | Competition | SipSense Advantage |
|-----------------|----------------|-------------|-------------------|
| Whiskey + cocktail intersection | "best bourbon for old fashioned", "cocktails with scotch" | Low-Medium | Deep whiskey catalog with ratings and flavor data |
| Specific bottle cocktails | "cocktails with Maker's Mark", "Laphroaig cocktail recipes" | Low | Bottle-specific pages with community ratings per whiskey used |
| "What can I make" queries | "whiskey cocktails 3 ingredients", "easy bourbon drinks" | Medium | My Bar feature + difficulty filtering |
| Comparison queries | "Manhattan vs Old Fashioned", "bourbon sour vs whiskey sour" | Low-Medium | Compare feature, flavor profiles |
| Educational long-tail | "why is my old fashioned bitter", "how to stir a cocktail" | Low | Learn hub + AI chat |

### Structured Data (Schema.org Recipe)

Every cocktail detail page should include JSON-LD Recipe markup:

```json
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Old Fashioned",
  "description": "The classic bourbon cocktail...",
  "image": "https://cdn.sipsense.ai/cocktails/old-fashioned.jpg",
  "recipeIngredient": ["2 oz bourbon", "1 sugar cube", "2 dashes Angostura bitters", "Orange peel"],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "Place sugar cube in rocks glass"},
    {"@type": "HowToStep", "text": "Add bitters, muddle until dissolved"}
  ],
  "prepTime": "PT3M",
  "recipeCategory": "Cocktail",
  "recipeCuisine": "American",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.2",
    "ratingCount": "47"
  }
}
```

This enables Google rich snippets (recipe cards with star ratings, images, prep time) even at lower domain authority.

### Content Calendar

| Week | Content Piece | SEO Target | Format |
|------|--------------|------------|--------|
| 1 | "The 20 Best Whiskey Cocktails, Ranked by Our Community" | best whiskey cocktails | Blog article + cocktail links |
| 2 | "The Old Fashioned: History, Recipe, and Which Bourbon to Use" | best bourbon for old fashioned | Deep-dive blog + bottle recommendations |
| 3 | "Bourbon vs Rye in Cocktails: How to Choose" | bourbon vs rye cocktails | Blog article + comparison tool |
| 4 | "How to Build a Whiskey Home Bar (5 Bottles, 30 Cocktails)" | whiskey home bar essentials | Blog + My Bar feature promotion |
| 5 | "5 Easy 3-Ingredient Whiskey Cocktails for Beginners" | easy whiskey cocktails | Blog + difficulty filter |
| 6 | "Smoky Cocktails for Scotch Lovers" | scotch cocktails | Blog + flavor filter |
| 7 | "Cocktail Techniques: When to Stir vs Shake" | how to stir a cocktail | Learn hub technique page |
| 8 | "Seasonal Cocktail Guide: [Current Season]" | [season] whiskey cocktails | Blog + seasonal filter |

---

## Metrics & Success Criteria

### Phase 1 Success (3 months post-launch)

| Metric | Target | Rationale |
|--------|--------|-----------|
| Cocktail detail page views | 5K/month | Internal traffic from whiskey pages + early SEO |
| Cocktail pages indexed by Google | 150+ | Catalog + ingredient pages fully crawled |
| Users who set up My Bar | 100 | Core feature adoption among active users |
| "What can I make?" queries (endpoint hits) | 500/month | People are using the killer feature |

### Phase 2 Success (6 months post-launch)

| Metric | Target | Rationale |
|--------|--------|-----------|
| Cocktail check-ins | 200/month | Active engagement (realistic for ~1000 users) |
| Whiskey check-in → cocktail bridge conversion | 10% | Serving_style="cocktail" users also rate the cocktail |
| Cocktail photos uploaded | 50/month | Community content |
| Feed posts with cocktail content | 10% of feed | Blending into social without overwhelming |

### Phase 3 Success (9 months post-launch)

| Metric | Target | Rationale |
|--------|--------|-----------|
| Organic search traffic to cocktail pages | 1K/month | Long-tail SEO traction |
| AI custom cocktail generations | 300/month | AI differentiator usage |
| Cocktail tutorial videos uploaded | 20 | Video content cross-pollination |
| Ingredient buy-link clicks | 100/month | Early monetization signal |

---

## Honest Challenges

These aren't just "risks with mitigations" — they're real problems that could kill the feature.

### 1. Nobody Rates Cocktails

**The problem:** Making a cocktail at home and then opening an app to rate it is a lot of friction. Unlike rating a whiskey (sip and rate), cocktails require making the drink first, then remembering to log it.

**Why it might fail:** Cocktail rating adoption on competing apps is notoriously low. Mixel has millions of downloads but thin user review data.

**What to try:**
- Whiskey check-in bridge (lowest friction: user is already rating the whiskey)
- "Made this?" push notification after user views a recipe
- Photo-first flow: upload the photo and the app prompts for rating
- Badge incentives tied specifically to cocktail check-ins

### 2. My Bar Setup Is Tedious

**The problem:** Users must manually enter 15-20 ingredients before "what can I make?" delivers value. Most will abandon.

**Why it might fail:** Every "what's in my fridge?" cooking app has this problem. HelloFresh and Blue Apron won by eliminating the inventory step entirely.

**What to try:**
- Auto-populate spirits from whiskey collection (covers 1-2 bottles)
- "Starter kit" one-click setup: 10 most common bar ingredients
- Progressive disclosure: show results even with 3-4 ingredients (not empty state)
- Barcode scanning for bottles and mixers (extend existing UPC infrastructure)
- Show "You can make 3 cocktails!" even with a minimal bar — small wins keep people going

### 3. SEO Against Established Giants

**The problem:** AllRecipes, Epicurious, and Bon Appetit own cocktail recipe SEO. SipSense has negligible domain authority.

**Why it might fail:** Even with perfect Schema.org markup and great content, Google may never rank SipSense cocktail pages above page 2 for any high-volume term.

**What to try:**
- Focus exclusively on whiskey-specific long-tail queries where SipSense has genuine topical authority
- Blog content strategy linking to cocktail pages (builds internal link authority)
- User-generated content (reviews with unique text) adds content depth Google values
- Accept that SEO is a slow burn and measure it on a 12-month horizon, not 3

### 4. Identity Crisis

**The problem:** Adding cocktails to a whiskey app confuses the brand. Existing users came for whiskey discovery, not bartending tutorials.

**Why it might fail:** Feature sprawl makes the app feel unfocused. Users open the app and don't know what it's for anymore.

**What to try:**
- Cocktails are a tab/section, not the homepage. Whiskey browse (`/`) stays the landing page.
- All cocktail content links back to specific whiskeys. The message is "what to DO with your whiskey," not "learn to bartend."
- Marketing frame: "SipSense: from bottle to glass" — cocktails are the natural extension of the whiskey journey.
- Monitor whether whiskey engagement metrics (check-ins, time on whiskey pages) decline after cocktail launch. If they do, pull back.

### 5. AI-Generated Cocktail Quality

**The problem:** Claude generates plausible-sounding cocktails, but untested recipes can taste terrible. "Heather honey syrup" sounds good on paper but might be cloyingly sweet with a smoky Islay scotch.

**Why it might fail:** Users try an AI cocktail, it tastes bad, they lose trust in SipSense's cocktail recommendations entirely.

**What to try:**
- Never auto-add AI cocktails to the curated catalog. They're ephemeral creations in chat and on the generate page.
- Include a disclaimer: "AI-created recipe — not yet tested by the community"
- Track ratings on AI-generated cocktails separately. If they consistently score below 3/5, reduce visibility.
- Consider having a human "test kitchen" for AI cocktails before featuring them prominently

### 6. Legal & Responsible Drinking

**The problem:** Promoting alcohol recipes has legal implications in some jurisdictions. An app that encourages making drinks needs to handle this carefully.

**What to do:**
- Age gate on cocktail pages (simple "Are you 21+?" interstitial, not account verification)
- "Drink responsibly" footer on all cocktail content
- Never suggest "challenge" formats that encourage speed or quantity of drinking
- AI guardrails: cap suggested alcohol content, never combine stimulants with alcohol, refuse to generate drinking game recipes

---

## Implementation Effort Estimates

| Phase | New Tables | New Endpoints | New Pages | Key Dependencies |
|-------|-----------|--------------|-----------|-----------------|
| Phase 1: Foundation + My Bar | 4 (cocktails, cocktail_ingredients, ingredients, user_bar) | ~12 | 3 (Browse, Detail, MyBar) | Seed data, ingredient parsing |
| Phase 2: Social | 2 (cocktail_ratings, cocktail_saves) + extend toast/comment | ~10 | 0 (extend existing) | Phase 1 tables |
| Phase 3: Recs + Video | 0 (extend videos table) | ~6 | 0 (extend existing) | Phase 2 rating data |
| Phase 4: Education | 0 (use existing journeys/learn) | ~4 | 0 (extend existing) | Content creation |
| Phase 5: Community + Commerce | 0 (extend user_list) | ~6 | 0 (extend existing) | Phase 2 adoption proof |

---

## Party Host Experience & Guided Cocktail Discovery

The cocktail expansion shouldn't just be a recipe catalog — it should be a **decision engine** that takes someone from "I'm hosting Saturday and have no idea what to serve" to "I'm making three specific cocktails and here's my shopping list." This is also the single biggest stickiness opportunity: party hosts are repeat users by nature. If SipSense becomes their go-to planning tool, they come back every time they entertain.

### The Cocktail Concierge (Guided Decision Flow)

A step-by-step wizard that narrows the universe of cocktails down to a personalized recommendation, designed for someone who doesn't know where to start. Think of it as the Taste Quiz but for cocktails.

**Flow:**

1. **What's the occasion?** — Casual hangout, dinner party, holiday gathering, date night, game day, birthday, "just me tonight"
2. **How many people?** — 1-2, 3-6, 7-15, 15+ (this determines whether batch recipes are recommended)
3. **What's everyone's vibe?** — Something refreshing & light, something bold & spirit-forward, something sweet & approachable, surprise me / mix of tastes
4. **What's your bartending comfort level?** — Never made a cocktail, made a few basics, I'm pretty comfortable, I want a challenge
5. **What's in your bar?** — Quick-select from common bottles (pull from My Bar if logged in, otherwise show top 15 spirits + common mixers). Option: "I'll buy whatever I need"
6. **How much prep time?** — Under 5 min per drink, up to 15 min, I'll prep in advance, time doesn't matter
7. **Result:** 1-3 specific cocktail recommendations with "Why this works for you" explanation, full recipes, and a combined shopping list for anything missing

**Why this works:** Every step eliminates options. By step 4, the user feels invested. By step 7, they feel confident. The friction of "what should I make?" is the #1 reason people default to beer and wine for parties. Eliminating that friction is the value proposition.

**AI integration:** The concierge can also run as a conversational flow in the chat agent — same logic, but natural language. "Hey, I'm hosting a dinner for 8 on Saturday, most of my friends like sweeter drinks, and I have Maker's Mark and Buffalo Trace." → Agent runs through the decision tree implicitly and returns recommendations with reasoning.

### Party Planning Mode

Once someone picks their cocktails (via the Concierge or by browsing), Party Planning Mode bundles everything they need to execute.

#### Batch Recipe Scaling
- Select a cocktail → enter guest count → get auto-scaled recipe ("makes 12 servings")
- Smart scaling that accounts for dilution differences between single and batch (e.g., batch Old Fashioneds need less water since they don't get stirred individually with ice)
- "Pitcher friendly" flag on cocktails that batch well vs. ones better made individually

#### Unified Shopping List
- Combines ingredients across all selected cocktails, deduplicates, and totals quantities
- Marks what the user already has (from My Bar) vs. what they need to buy
- "Send to phone" or shareable link for grocery store runs
- Integration opportunity: link ingredients to buy pages (affiliate revenue from Total Wine, Drizly, etc.)

#### Drink Menu Builder
- Select 2-4 cocktails → auto-generate a shareable menu card
- Templates: chalkboard style, minimalist, holiday themed, etc.
- Includes cocktail names, short descriptions, and optional whiskey callouts ("Made with Buffalo Trace")
- Exportable as image (reuse existing Pillow share card infrastructure) or printable PDF
- Shareable link that guests can view on their phones at the party

#### Prep Timeline
- Based on selected cocktails and party time, generate a prep schedule:
  - "Day before: Make simple syrup, chill glasses"
  - "2 hours before: Pre-batch the Whiskey Sours, cut garnishes"
  - "30 min before: Set up bar station with ice, glasses, garnishes"
  - "As guests arrive: Stir and serve Old Fashioneds to order"
- This is the kind of structured guidance that turns an anxious host into a confident one

### Guest Preference Collector

A lightweight, no-login-required form that hosts can share with their guest list before the event.

**How it works:**
1. Host creates an event in SipSense (name, date, rough guest count)
2. SipSense generates a shareable link (e.g., `sipsense.ai/party/abc123`)
3. Guests visit the link and answer 3-4 quick questions: flavor preferences (sweet/strong/refreshing), any allergies/restrictions, spirit preferences, adventurousness level
4. Host sees aggregated results: "6 of 8 guests prefer sweeter drinks, 2 prefer spirit-forward, 1 doesn't drink"
5. Concierge uses this data to recommend cocktails that cover the group's preferences — e.g., "Make a Whiskey Sour (covers the sweet crowd) and an Old Fashioned (covers the spirit-forward folks), plus have ginger beer for a non-alcoholic option"

**Why this is sticky:** The host now has a reason to come back to SipSense every time they entertain. The guest preference data persists — next party, SipSense already knows what your friend group likes. And every guest who visits the link sees SipSense for the first time (organic growth loop).

### Host Dashboard & Event History

For repeat hosts, SipSense becomes their party planning archive.

- **Event history:** Past events with date, guest count, cocktails served, and any notes
- **"Host again" button:** One click to re-create a past event's cocktail lineup, pre-populated with the same recipes and shopping list
- **Remix suggestions:** "Last time you made Whiskey Sours and Old Fashioneds. Want to keep one and try something new? Here's a Gold Rush — similar crowd-pleaser, different flavor."
- **Hit tracker:** If guests rated drinks via the party link, show which cocktails were most popular. "Your Penicillin was rated 4.7/5 — consider making it your signature."
- **Template library:** Save a cocktail lineup as a reusable template ("My Go-To Dinner Party Menu," "Game Day Classics," "Holiday Crowd-Pleasers")

### Seasonal & Occasion Intelligence

The app should proactively surface relevant cocktail content based on calendar context.

- **Seasonal push notifications / homepage cards:** "Fall is here — try a Hot Toddy or Apple Cider Bourbon Smash"
- **Holiday-specific recommendations:** "Hosting Thanksgiving? Here are 3 cocktails that pair with turkey dinner"
- **Weather-aware suggestions:** Cold snap → warm cocktails (Hot Toddy, Irish Coffee). Heat wave → refreshing cocktails (Whiskey Smash, Highballs)
- **Trending in community:** "This weekend, 47 SipSense users are making Mint Juleps for the Kentucky Derby"
- **"What's in season" ingredient callouts:** Fresh peaches in summer → Peach Bourbon Smash rises in recommendations

### Stickiness Loops for Party Hosts

The goal is to make SipSense the app hosts open *first* when they decide to entertain.

| Loop | How It Works | Why It's Sticky |
|------|-------------|-----------------|
| **Event reminders** | "You hosted a holiday party last December — planning one this year?" (calendar-based nudge) | Triggers the planning flow at the natural decision point |
| **Host streak** | Track hosting frequency. "You've hosted 4 events this year!" Unlock host-specific badges ("The Entertainer," "Cocktail Party Pro") | Gamification that rewards the exact behavior we want |
| **Post-party recap** | After an event, prompt: "How'd it go? Rate your cocktails, note what you'd change." Generates a recap card to share | Creates a reflection moment + shareable content for organic growth |
| **Signature cocktail tracker** | "Your most-made cocktail is the Old Fashioned (made it at 3 events)." Suggest variations to keep it fresh | Makes the user feel like SipSense knows them |
| **Guest list learning** | Over multiple events, SipSense builds a profile of the host's typical crowd preferences. Recs get better each time | The more you use it, the harder it is to switch — data moat |
| **Monthly host inspiration** | Email/push: "New cocktail that's perfect for your usual crowd" — personalized to past event data | Keeps the app top-of-mind between events |
| **Social proof in feed** | When a user hosts an event, it shows in the activity feed: "Sarah hosted a cocktail party with 3 whiskey cocktails" with a photo | Inspires other users to host and use the planning tools |

### The Full Journey: From Zero to Party-Ready

To illustrate how all these pieces connect, here's a user story:

> **Sarah has never made a cocktail.** She's hosting 8 friends for her birthday dinner on Saturday.
>
> 1. She opens SipSense and taps "Plan a Party" (or tells the AI chat "I'm hosting dinner for 8")
> 2. The **Cocktail Concierge** walks her through 6 quick questions. She picks "dinner party," "8 people," "mix of tastes," "never made a cocktail," and "I have Maker's Mark"
> 3. SipSense recommends: **Whiskey Sour** (crowd-pleaser, easy), **Old Fashioned** (for the spirit-forward friends), and a **Ginger Highball** (as a low-ABV/mocktail option). Each with a "Why this works" explanation
> 4. She shares the **Guest Preference Collector** link in her group chat. 6 friends respond — confirms the sweet/spirit-forward split
> 5. She taps "Plan This Party" → sees the **combined shopping list** (lemons, simple syrup, Angostura bitters, ginger beer — she already has the Maker's Mark)
> 6. Thursday evening, she gets a **prep timeline**: "Make simple syrup tonight (5 min). Saturday morning: juice lemons, chill glasses."
> 7. Saturday afternoon, she opens the **Drink Menu Builder**, picks a template, and prints a card for the bar area
> 8. During the party, she follows the step-by-step recipes on her phone. Friends ask "what app is that?" → organic growth
> 9. Sunday, she gets a **post-party recap** prompt. She rates the cocktails and notes "Everyone loved the Whiskey Sour, skip the Highball next time"
> 10. **Next month**, SipSense nudges: "Hosting again? Based on your last party, try a Gold Rush — it's like the Whiskey Sour your friends loved, but with honey." Sarah's hooked.

This is the flywheel: each party makes the next one easier, and each party introduces SipSense to new potential users.

---

## Experience-First Event Planning: Lead with the Occasion, Not the Alcohol

### The Core Insight: People Buy Experiences, Not Products

The biggest mistake a cocktail app can make is opening with "What do you want to drink?" That's like a travel app opening with "What airline do you want to fly?" Nobody cares about the airline — they care about the trip. Nobody opens an app because they woke up craving a Penicillin. They open it because **they're hosting Saturday night and need to figure out what to do.**

The entire SipSense cocktail experience should be reframed around **the event** as the primary object, with cocktails as the output. The user's starting point is never "I want to make an Old Fashioned" — it's "I'm having people over and I want it to be great." Everything flows from the occasion.

This is fundamentally different from every cocktail app on the market. Difford's Guide, Mixel, Cocktail Flow — they all start with a recipe search bar. SipSense should start with: **"Tell me about your event."**

### The Event Profile Wizard

A guided intake flow that captures everything about the occasion before suggesting a single drink. This is the app's front door for the hosting use case.

#### Step 1: What's the Occasion?

Not just "party type" but the emotional intent:
- **Impress someone** — date night, boss coming to dinner, in-laws visiting, hosting your partner's friends for the first time
- **Celebrate** — birthday, promotion, engagement, holiday, housewarming, graduation
- **Hang out** — casual get-together, game day, movie night, friends catching up, after-work drinks
- **Host a proper event** — cocktail party, dinner party, holiday gathering, themed party, bridal shower
- **Just me / couple's night** — winding down, trying something new, romantic evening at home

Why this matters: The emotional context shapes everything. "Impress the in-laws" → elegant, foolproof, universally appealing drinks. "Game day with the guys" → easy batch cocktails, bold flavors, low-maintenance. The occasion determines the cocktail profile before a single flavor preference is captured.

#### Step 2: Where Is It Happening?

Physical environment shapes what cocktails are practical:
- **Indoor apartment/house** — full kitchen access, limited space, noise considerations
- **Backyard / patio** — outdoor, more relaxed, weather factor, potential for a bar cart setup
- **Rooftop / balcony** — scenic but space-constrained, wind factor (no delicate garnishes)
- **Park / beach / outdoor venue** — no running water, needs portable setup, punch/batch-only
- **Rental / Airbnb** — unfamiliar kitchen, may lack tools, keep it simple
- **Office / workplace** — formal, measured portions, accessibility matters

Why this matters: A park picnic eliminates anything that requires shaking, straining, or fresh ingredients held at temperature. An apartment party with thin walls suggests quieter prep (no aggressive muddling). A backyard BBQ can support a full bar station. The venue constrains the solution set dramatically.

#### Step 3: How Many People?

- **1-2** — craft individual cocktails, go complex, this is a tasting experience
- **3-6** — sweet spot for made-to-order cocktails, host can bartend and socialize
- **7-15** — transition to batch cocktails + 1 made-to-order signature drink, host can't be behind the bar all night
- **15-30** — full batch mode, self-serve punch or pitcher station, simple garnish bar
- **30+** — catering territory: 2-3 pre-batched options max, disposable glassware OK, volume matters

Why this matters: Group size is the single biggest filter on cocktail complexity. A Manhattan stirred to order is perfect for 4 guests. For 25 guests, it's a nightmare — the host spends the entire party behind a bar. SipSense must be honest: "For your party size, skip the made-to-order cocktails. Here's a bourbon punch that tastes incredible and serves itself."

#### Step 4: Who's Coming?

This is where SipSense gets personal about the crowd:

**Age range / demographic:**
- **21-25** — likely newer to cocktails, lean approachable and fun, Instagram-worthy presentation matters, lower alcohol tolerance on average
- **25-35** — craft cocktail curious, willing to try bold flavors, open to being educated, may have dietary preferences (low sugar, low calorie)
- **35-50** — likely has preferences already, appreciates quality over novelty, comfort drinks with a twist
- **50+** — classics done well, may prefer spirit-forward, less likely to want "trendy" drinks
- **Mixed ages** — need range, something for everyone, universally appealing base + one adventurous option

**Nature of the group:**
- **Close friends** — can experiment, they'll be honest if it's bad, fun atmosphere
- **Acquaintances / networking** — need crowd-pleasers, can't risk polarizing flavors, conversation starters help
- **Family** — wide taste range, non-alcoholic options essential, nostalgic flavors work
- **Colleagues** — keep it professional, moderate alcohol content, nothing too obscure
- **Partner's friends / new people** — safe but impressive, want to seem like you know what you're doing

**Known preferences (if any):**
- "Most of my friends drink beer/wine" → ease them in with highballs and spritzes, nothing too spirit-forward
- "Cocktail-savvy crowd" → can go complex, they'll appreciate technique and unusual ingredients
- "Mixed drinkers and non-drinkers" → always include a mocktail/low-ABV option built from the same ingredient set

#### Step 5: What's the Vibe?

The sensory environment the host is creating:

- **Loud and energetic** — music, dancing, high energy → bold, simple, batch-friendly drinks that don't require explanation. Bright colors, fun garnishes. Nobody's savoring — they're celebrating.
- **Conversational and relaxed** — background music, sitting, talking → more nuanced cocktails that spark conversation. "What is this? It's incredible." A drink that's a talking point.
- **Intimate and quiet** — candles, low music, small group → craft cocktails made with care, sipping slowly. This is where you pull out the stirred, spirit-forward drinks.
- **Active / outdoors** — lawn games, BBQ, pool → refreshing, low-ABV, tall drinks with ice. Nothing that goes warm fast. Hydration matters.
- **Formal / elegant** — seated dinner, toasts, structure → classic cocktails with clean presentation. Coupe glasses, expressed citrus oils, zero mess.

#### Step 6: Space & Setup

Practical logistics that determine what's feasible:

- **Do you have a dedicated bar area?** — or are you mixing on the kitchen counter? Determines how much station setup guidance SipSense provides
- **How much counter/table space?** — 2 feet of counter = 1 batch cocktail max. A full table = self-serve station with 3 options
- **Do you have cocktail tools?** — shaker, jigger, strainer, muddler. If no → recommend built/stirred drinks only, and suggest a $20 starter kit (affiliate opportunity)
- **Ice situation?** — home freezer only (limited), bought bags (plan quantity), access to large format ice. Ice is the #1 thing hosts underestimate. SipSense should calculate ice needs based on cocktail selection and guest count.
- **Glassware?** — proper glasses, mason jars, disposable cups. All are fine — SipSense adjusts presentation recommendations accordingly. "No rocks glasses? Use short tumblers. No coupes? A wine glass works."

#### Step 7: Budget & Effort

- **How much do you want to spend per person?** — $5/person (beer-adjacent budget), $10/person (solid cocktail experience), $15+/person (premium spirits, multiple options)
- **How much prep time are you willing to invest?** — "Just want to pour things" vs "I'll prep the day before" vs "I want the full bartender experience"
- **Shopping flexibility** — "I'll buy whatever" vs "Want to use what I already have" (connects to My Bar)

### From Event Profile to Cocktail Recommendations

Once the wizard captures the full event profile, SipSense runs a matching algorithm that's fundamentally different from "search by base spirit." The logic:

#### The Matching Matrix

| Event Signal | Cocktail Attribute It Filters |
|-------------|------------------------------|
| 30+ guests | Must be batchable. Eliminate made-to-order complex drinks |
| Outdoor / no running water | Must be pre-batchable or built-in-glass. No shaking/straining on site |
| Age 21-25, newer drinkers | Boost `sweet` and `refreshing`. Suppress `spirit_forward` and `bitter` |
| Loud, energetic vibe | Boost visually striking drinks. Penalize subtle, sipping cocktails |
| Formal dinner party | Boost classics. Penalize novelty/tiki/fun drinks |
| Low budget ($5/person) | Filter to cocktails with inexpensive ingredients. Eliminate recipes requiring premium spirits |
| "No cocktail tools" | Filter to built/stirred cocktails only. No shaker required |
| Hot weather / outdoor | Boost `refreshing`, tall drinks, highballs. Penalize hot cocktails, spirit-forward sippers |
| Cold weather / intimate | Boost warm cocktails, spirit-forward, stirred. Penalize light/refreshing |
| Mixed drinkers + non-drinkers | Always include a mocktail/low-ABV variant in recommendations |
| Host is a beginner | Filter to `difficulty=easy`. Include extra technique guidance |
| Close friends, experimental | Can include AI-generated or unusual cocktails. Higher risk tolerance |

#### Example Outputs

**Input:** Backyard BBQ, 20 people, ages 25-35, casual friends, loud and energetic, outdoor, limited bar space, $8/person budget, minimal prep time

**Output:**
> **Your BBQ Cocktail Plan**
>
> For 20 guests outdoors with an energetic vibe, you want bold, batch-friendly drinks that serve themselves. Here's your lineup:
>
> 1. **Bourbon Lemonade Punch** (the crowd-pleaser) — Pre-batch in a dispenser. Sweet, refreshing, foolproof. Serves itself. *Why: Covers 70% of your crowd who want something easy and delicious.*
>
> 2. **Whiskey Ginger Highball Station** (the DIY option) — Set out bourbon, ginger beer, ice, and lime wedges. Guests build their own. *Why: Zero prep, interactive, and the ginger beer crowd loves it.*
>
> 3. **Smoked Old Fashioned** (the conversation starter) — Make 4-5 to order for the cocktail-curious guests. *Why: Gives you a "signature" move without being stuck behind the bar.*
>
> 4. **Ginger Beer + Lime Mocktail** (the non-drinker) — Same setup as the highball, just skip the bourbon. *Why: Nobody feels excluded.*
>
> **Shopping list:** 2 bottles bourbon ($50), 12-pack ginger beer ($10), 2 bags ice ($8), lemons, limes, simple syrup ($7). **Total: ~$75 ($3.75/person)**
>
> **Prep timeline:** Morning of — make the punch (10 min). 30 min before — set up stations, cut garnishes, fill ice buckets.

**Input:** Dinner party, 6 people, ages 35-50, partner's colleagues (want to impress), quiet and intimate, indoor apartment, have basic bar tools, $15/person budget, willing to prep day-before

**Output:**
> **Your Dinner Party Cocktail Plan**
>
> For an intimate dinner with colleagues you want to impress, go classic and polished. Three courses of drinks, matched to the meal:
>
> 1. **Arrival: Boulevardier** — Pre-batched and chilled in a decanter. Pour into coupes as guests arrive. *Why: Sophisticated, unexpected (not the obvious Old Fashioned), beautiful garnet color. Says "I know what I'm doing."*
>
> 2. **With Dinner: Japanese Highball** — Made individually at the table with Suntory Toki + premium soda water. *Why: Light enough to complement food, the theatrical pour and precise ice impresses, and the low ABV keeps everyone sharp through dinner.*
>
> 3. **After Dinner: Single Malt Neat** — Offer 1-2 bottles from your collection with tasting notes from SipSense. *Why: Transition from cocktails to whiskey signals depth of knowledge. Let the conversation breathe.*
>
> 4. **Non-drinker: Yuzu Tonic** — Yuzu juice + tonic water + rosemary sprig. *Why: Feels intentional, not like an afterthought.*
>
> **Shopping list:** 1 bottle Campari, 1 bottle sweet vermouth, 1 bottle rye ($45), Suntory Toki ($30), premium soda water ($8), yuzu juice ($6). **Total: ~$89 ($14.80/person)**
>
> **Prep timeline:** Day before — batch the Boulevardier, chill. Day of — chill glasses 1 hour before, prep garnishes, set up a small bar station with the highball ingredients.

### The Full Event Package: Beyond the Cocktail

This is where SipSense becomes more than a recipe app. Once the cocktail plan is set, surround it with everything else the host needs:

#### Food Pairings (Curated per Cocktail)

Don't just recommend cocktails — recommend what to eat with them:
- **Bourbon Lemonade Punch** → pulled pork sliders, cornbread, grilled peach skewers
- **Boulevardier** → charcuterie board with aged cheeses, marcona almonds, dark chocolate
- **Japanese Highball** → sashimi, edamame, light salads, grilled fish
- **Old Fashioned** → smoked brisket, sharp cheddar, candied pecans

SipSense already has food pairing infrastructure in `pairings.py`. Extend it from whiskey-food pairings to cocktail-food pairings. The AI can generate contextual pairings: "For your backyard BBQ, pair the Bourbon Lemonade Punch with grilled corn and jalapeño cornbread."

#### Atmosphere Recommendations

Based on the vibe selection, suggest:
- **Music direction** — not specific playlists (licensing issues) but genre/mood guidance: "For your dinner party vibe: jazz standards, bossa nova, or lo-fi ambient. Keep it below conversation volume."
- **Lighting notes** — "Dim the overhead lights, use candles or string lights. Warm tones make cocktails look better in photos."
- **Table/bar setup guidance** — "For 20 guests, set up a self-serve station on a 4-foot table. Arrange bottles left-to-right in the order guests will use them. Put ice at the end."
- **Temperature/season considerations** — "It's going to be 85°F — pre-chill all glasses in the freezer, double your ice estimate, and put the batch cocktails in a cooler, not on the counter."

#### Glassware & Tools Guide

Based on what the user reported having:
- **What you need vs. nice-to-have** — "You need: rocks glasses (or any short glass), a jigger (or a shot glass), and a bar spoon (or a long-handled regular spoon). Nice to have: a large ice cube tray."
- **Affordable starter kit** — Link to a $20-30 Amazon bar tool set (affiliate revenue)
- **Improvisation tips** — "No muddler? Use a wooden spoon handle. No strainer? Use a slotted spoon. No coupe? A wine glass works beautifully."

#### Ice Planning Calculator

Ice is the most underestimated element of hosting. SipSense should calculate:
- **Pounds of ice needed** — based on guest count, cocktail types, duration, and whether drinks are shaken/stirred/served tall
- **Large format vs. standard** — "For stirred cocktails, buy 2 trays of large cubes. For highballs, use standard ice. For batch punch, freeze a large block in a bundt pan."
- **When to buy** — "Buy ice the morning of. 2 bags of standard + 1 tray of large cubes for your party of 12."

#### Non-Alcoholic Strategy

Always included — never an afterthought:
- **Mirror the cocktail menu** — For every cocktail, suggest a zero-proof version using the same flavor profile. "Your Whiskey Sour becomes a Honey-Lemon Shrub Fizz."
- **Use the same ingredients** — Build the mocktail from ingredients already in the shopping list (ginger beer, citrus, syrups). No extra shopping trip.
- **Present it as intentional** — "Add the mocktail to your printed menu with a name, not just 'non-alcoholic option.'" This makes non-drinkers feel like first-class guests.

### Event Archetypes (Pre-Built Templates)

For users who don't want to go through the full wizard, offer one-tap templates:

| Archetype | Cocktails | Food Pairings | Vibe | Serves |
|-----------|-----------|---------------|------|--------|
| **The Backyard BBQ** | Bourbon Punch, Whiskey Ginger station, Smoked Old Fashioned | Brisket, ribs, corn, coleslaw | Loud, outdoor, casual | 15-30 |
| **Date Night In** | Paper Plane, Boulevardier, after-dinner neat pour | Oysters, steak, dark chocolate | Intimate, candles, jazz | 2 |
| **Game Day** | Irish Whiskey Punch, Bourbon & Cola station | Wings, nachos, sliders | Loud, TV on, casual | 6-12 |
| **Holiday Dinner** | Cranberry Whiskey Sour, Hot Toddy, Eggnog (bourbon-spiked) | Turkey, ham, pie | Warm, family, festive | 8-15 |
| **Housewarming** | Mint Julep bar (build your own), Welcome Punch | Cheese board, finger foods, dips | Conversational, tour-friendly | 10-20 |
| **Bridal/Baby Shower** | Whiskey Peach Bellini, Lavender Lemonade (low-ABV), Mocktail flight | Tea sandwiches, fruit, petit fours | Elegant, daytime, bright | 10-25 |
| **The Cocktail Hour** | Manhattan, Sazerac, Paper Plane, Whiskey Sour (all made-to-order) | Charcuterie, crostini, olives | Sophisticated, small, slow | 4-8 |
| **After-Work Drinks** | Highball station, one signature stirred drink | Bar snacks, nuts, pretzels | Casual, decompressing, easy | 3-6 |
| **Summer Pool Party** | Frozen Whiskey Slush, Bourbon Arnold Palmer, Watermelon Smash | Grilled shrimp, fruit skewers, chips & guac | Bright, hot, high energy | 10-20 |
| **Winter Firepit** | Hot Toddy, Irish Coffee, Bourbon Hot Chocolate | S'mores, chili, warm bread | Cozy, cold, campfire | 4-10 |

Each archetype is a one-tap complete plan: cocktails + shopping list + food pairings + setup guide + prep timeline. Users can customize from here.

### Event UI Concept

```
+----------------------------------------------------------+
|  PLAN AN EVENT                                             |
+----------------------------------------------------------+
|                                                            |
|  What are you hosting?                                     |
|                                                            |
|  +------------------+  +------------------+                |
|  |    Dinner        |  |   Casual         |                |
|  |    Party         |  |   Hangout        |                |
|  |   [dinner icon]  |  |   [couch icon]   |                |
|  +------------------+  +------------------+                |
|  +------------------+  +------------------+                |
|  |   Celebration    |  |   Impress        |                |
|  |   / Holiday      |  |   Someone        |                |
|  |   [party icon]   |  |   [star icon]    |                |
|  +------------------+  +------------------+                |
|  +------------------+  +------------------+                |
|  |    Date          |  |   Just           |                |
|  |    Night         |  |   Me             |                |
|  |   [heart icon]   |  |   [solo icon]    |                |
|  +------------------+  +------------------+                |
|                                                            |
|  --- OR pick a template ---                                |
|                                                            |
|  [Backyard BBQ] [Game Day] [Holiday Dinner]                |
|  [Cocktail Hour] [Pool Party] [Winter Firepit]             |
|                                                            |
+----------------------------------------------------------+

          After completing the wizard:

+----------------------------------------------------------+
|  YOUR EVENT PLAN                    [Edit] [Share]         |
|  "Sarah's Birthday Dinner"                                 |
|  Saturday, April 5 · 8 guests · Indoor · Intimate          |
+----------------------------------------------------------+
|                                                            |
|  COCKTAIL MENU                                             |
|  +----------------------------------------------+         |
|  | 1. Boulevardier              Arrival drink    |         |
|  |    Pre-batched, pour from decanter            |         |
|  |    [View Recipe] [Swap This]                  |         |
|  +----------------------------------------------+         |
|  | 2. Japanese Highball         With dinner       |         |
|  |    Made at table, theatrical pour              |         |
|  |    [View Recipe] [Swap This]                  |         |
|  +----------------------------------------------+         |
|  | 3. Neat Scotch Tasting       After dinner      |         |
|  |    2-3 bottles with tasting notes              |         |
|  |    [Choose Bottles]                            |         |
|  +----------------------------------------------+         |
|  | 4. Yuzu Tonic (mocktail)     Non-drinker       |         |
|  |    [View Recipe]                               |         |
|  +----------------------------------------------+         |
|                                                            |
|  FOOD PAIRINGS                                             |
|  Arrival: Charcuterie board, marcona almonds               |
|  Dinner: Pairs well with grilled salmon or steak          |
|  After: Dark chocolate, candied nuts                       |
|  [Full Pairing Guide ->]                                   |
|                                                            |
|  SHOPPING LIST                    [Share] [Send to Phone]  |
|  Spirits: Campari, sweet vermouth, rye, Suntory Toki      |
|  Mixers: Premium soda water, yuzu juice, tonic             |
|  Garnishes: Orange peel, rosemary, lemon                   |
|  Already have: [Maker's Mark, Angostura] (from My Bar)     |
|  Estimated total: $89 ($11.13/person)                      |
|  [Buy on Drizly ->] [Buy on Total Wine ->]                |
|                                                            |
|  PREP TIMELINE                                             |
|  Thu evening: Batch the Boulevardier (10 min)              |
|  Sat 4pm: Prep garnishes, set up bar area                  |
|  Sat 5pm: Chill glasses, fill ice bucket                   |
|  Sat 6pm: Guests arrive — pour Boulevardiers               |
|  [Add to Calendar]                                         |
|                                                            |
|  ATMOSPHERE NOTES                                          |
|  Music: Jazz standards or bossa nova, low volume           |
|  Lighting: Dim overhead, candles on table + bar            |
|  Setup: Small bar station near kitchen, tray service       |
|                                                            |
|  ICE PLAN                                                  |
|  Large cubes: 1 tray (for Boulevardiers if on rocks)       |
|  Standard ice: 1 bag (for highballs)                       |
|  Buy morning of event                                      |
|                                                            |
|  [Save as Template]  [Host Again Later]  [Share Plan]      |
+----------------------------------------------------------+
```

### Why Experience-First is the Stickiness Moat

Every cocktail app asks "what drink do you want?" That's a single-use query — you get the recipe, you leave, you never come back. By asking "what event are you hosting?", SipSense captures a fundamentally different relationship:

1. **Events are recurring.** People host multiple times a year. Each event brings them back to SipSense. A recipe lookup is one-and-done.

2. **Events are social.** Every event plan is shareable, every guest who sees the printed menu or party link discovers SipSense. A recipe is private.

3. **Events generate data.** After each event, SipSense knows: what cocktails worked, what didn't, what the crowd liked, how many people came. This data compounds — the 5th event plan is dramatically better than the 1st because SipSense knows the host's crowd.

4. **Events have budgets.** People willingly spend $50-200 on hosting supplies. That's affiliate revenue for spirits, tools, glassware, ingredients — all clicked through from the shopping list. A recipe searcher buys one bottle.

5. **Events have emotional stakes.** "I want my dinner party to be amazing" is a high-intent, high-anxiety use case. SipSense solving that anxiety builds deep loyalty. "I want an Old Fashioned recipe" has zero emotional weight.

6. **Events differentiate completely.** No cocktail app does this. Difford's is a recipe encyclopedia. Mixel is ingredient matching. None of them ask "who's coming to your party?" SipSense would be the only app that treats the social event as the primary object, with cocktails as one output among many (food, atmosphere, logistics).

The positioning shifts from **"SipSense: the whiskey app"** to **"SipSense: the app that makes you the best host in your friend group."** That's a much stickier identity — and it naturally leads users into the whiskey catalog, the cocktail recipes, the AI chat, and every other feature.

### Integration with Existing Cocktail Concierge

The Event Planner and the Cocktail Concierge (described in the Party Host section above) work together but serve different entry points:

- **Cocktail Concierge** = "I know I want cocktails, help me pick which ones" → starts with cocktail preferences
- **Event Planner** = "I'm hosting an event, help me plan everything" → starts with the occasion, cocktails are one output

The Event Planner is a superset. It runs the Concierge logic internally after gathering event context, but wraps the cocktail recommendations in the full event package (food, atmosphere, logistics, shopping, timeline). Users who just want cocktail recommendations without the full event planning experience can still use the Concierge directly.

### Data Model Additions for Event Planning

Building on the Party Host section's data model, the Event Planner needs:

#### `events` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| user_id | Integer FK → users | `ondelete="CASCADE"` |
| name | String(200) | "Sarah's Birthday Dinner" |
| occasion_type | String(50) | "dinner_party", "celebration", "casual", "date_night", etc. |
| event_date | DateTime | Nullable — user might not have a date yet |
| guest_count | Integer | |
| location_type | String(50) | "indoor_apartment", "backyard", "park", etc. |
| vibe | String(50) | "loud_energetic", "conversational", "intimate", "active_outdoor", "formal" |
| age_range | String(30) | "21-25", "25-35", "mixed", etc. |
| crowd_type | String(50) | "close_friends", "colleagues", "family", "new_people", etc. |
| budget_per_person | Float | Nullable |
| prep_willingness | String(20) | "minimal", "moderate", "extensive" |
| notes | Text | Free-text user notes (nullable) |
| archetype_slug | String(50) | If created from a template: "backyard-bbq", "date-night", etc. (nullable) |
| plan_data | Text | JSON blob: generated cocktail plan, food pairings, atmosphere notes, shopping list, prep timeline |
| status | String(20) | "planning", "ready", "completed". Default "planning" |
| created_at | DateTime | `server_default=func.now()` |
| updated_at | DateTime | `server_default=func.now(), onupdate=func.now()` |

#### `event_cocktails` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| event_id | Integer FK → events | `ondelete="CASCADE"` |
| cocktail_id | Integer FK → cocktails | `ondelete="CASCADE"` |
| role | String(50) | "arrival", "with_dinner", "after_dinner", "signature", "mocktail" |
| servings | Integer | Scaled for guest count |
| sort_order | Integer | Display order |

This sits alongside the existing `cocktails` and `cocktail_ingredients` tables proposed in the data model section above — it references them, doesn't duplicate them.

---

## Summary

SipSense has a genuine opportunity in cocktails because:

1. **No one has AI + whiskey expertise + community in one cocktail app.** Recipe sites have recipes. Social apps have feeds. AI tools have chat. SipSense can integrate all three, and the whiskey catalog connection is a moat no recipe blog can replicate.

2. **The foundation exists but needs honest investment.** ~67 recipes, AI generation, cocktail images, serving style data, and the full social/gamification layer are reusable. But cocktails need to become first-class database entities before anything meaningful can be built on top.

3. **"What can I make?" is the killer feature.** It's the single biggest unmet need in cocktail apps — personalized, inventory-aware recommendations. Ship it in Phase 1, not Phase 3. It's the difference between launching as a worse Difford's Guide and launching as something genuinely new.

4. **Whiskey check-in bridge solves cold start.** The existing serving style data gives us a built-in pathway to bootstrap cocktail ratings without requiring users to adopt a new behavior.

5. **Stay focused.** Whiskey cocktails only in Phase 1. No gin, rum, tequila, vodka recipes. The temptation to become a general cocktail app will be strong — resist it until the whiskey cocktail experience is excellent.

The recommended approach: ship Phase 1 (catalog + detail pages + My Bar) as a single cohesive launch. Measure adoption. If cocktail page views exceed 3K/month and My Bar setup reaches 50+ users within 2 months, proceed to Phase 2. If not, investigate why before investing further.
