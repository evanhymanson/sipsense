"""
SipSense Blog / Content Hub

Auto-generated SEO article pages built from real whiskey database data.
Articles like "Best Bourbons Under $50" are dynamically generated from
actual ratings, prices, and categories — always fresh and accurate.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from .. import models
from ..database import get_db

router = APIRouter(prefix="/blog", tags=["blog"])

CURRENT_YEAR = datetime.now(timezone.utc).year

# ── Article definitions ─────────────────────────────────────────────────
# Each article is a dict describing how to query and present the data.
# The backend generates content from live DB data every request (cached
# by the frontend for 2 min and by CDN/browser for 1 hour).

ARTICLES = [
    {
        "slug": "best-bourbons-under-50",
        "title": f"Best Bourbons Under $50 ({CURRENT_YEAR})",
        "meta_description": f"The top-rated bourbons under $50 in {CURRENT_YEAR}, ranked by thousands of real user ratings on SipSense.",
        "intro": [
            "You don't need to spend a fortune to drink excellent bourbon. Some of the best bottles on the shelf sit comfortably under fifty dollars — the trick is knowing which ones are worth your money.",
            "We ranked every bourbon in our database under $50 by real user ratings from the SipSense community. No paid placements, no hype — just honest scores from people who drink the stuff.",
        ],
        "category": "bourbon",
        "price_max": 50,
        "limit": 15,
    },
    {
        "slug": "best-bourbons-under-100",
        "title": f"Best Bourbons Under $100 ({CURRENT_YEAR})",
        "meta_description": f"Top bourbons under $100 ranked by real ratings. Find your next bottle without breaking the bank.",
        "intro": [
            "The sweet spot for bourbon sits between $50 and $100 — this is where distilleries put their best foot forward without the allocated-bottle markup.",
            "These bourbons earned their spots through community ratings, not marketing budgets. Every bottle here has been rated by real SipSense users.",
        ],
        "category": "bourbon",
        "price_max": 100,
        "limit": 15,
    },
    {
        "slug": "top-rated-scotch",
        "title": f"Top Rated Scotch Whisky ({CURRENT_YEAR})",
        "meta_description": f"The highest-rated scotch whiskies in {CURRENT_YEAR}, from peaty Islays to smooth Speysides. Ranked by community ratings.",
        "intro": [
            "Scotland's distilleries produce an extraordinary range of whisky — from the briny peat bombs of Islay to the honeyed malts of Speyside. But which ones are actually the best?",
            "We let the ratings speak. These are the scotch whiskies that SipSense users rate highest, across every region and price point.",
        ],
        "category": "scotch",
        "limit": 15,
    },
    {
        "slug": "best-japanese-whisky",
        "title": f"Best Japanese Whisky ({CURRENT_YEAR})",
        "meta_description": f"The top Japanese whiskies in {CURRENT_YEAR}. From Yamazaki to Nikka, ranked by real drinker ratings.",
        "intro": [
            "Japanese whisky has gone from insider secret to global phenomenon in barely two decades. The best bottles rival — and often surpass — their Scottish counterparts in complexity and craft.",
            "These are the Japanese whiskies that SipSense users rate highest. Some are easy to find; others require a bit of hunting. All are worth the effort.",
        ],
        "category": "japanese",
        "limit": 15,
    },
    {
        "slug": "best-irish-whiskey",
        "title": f"Best Irish Whiskey ({CURRENT_YEAR})",
        "meta_description": f"Top-rated Irish whiskeys in {CURRENT_YEAR}. Smooth, approachable, and endlessly drinkable. Community-ranked.",
        "intro": [
            "Irish whiskey is in the middle of a renaissance. New distilleries are opening, old ones are experimenting, and the result is a category that's never been more exciting.",
            "From triple-distilled singles to rich pot stills, these are the Irish whiskeys that our community rates highest.",
        ],
        "category": "irish",
        "limit": 15,
    },
    {
        "slug": "best-rye-whiskey",
        "title": f"Best Rye Whiskey ({CURRENT_YEAR})",
        "meta_description": f"The highest-rated rye whiskeys in {CURRENT_YEAR}. Spicy, bold, and perfect for cocktails or sipping neat.",
        "intro": [
            "Rye whiskey is bourbon's spicier, bolder sibling — and it's having a serious moment. Whether you sip it neat or shake it into a Manhattan, a good rye delivers flavor that punches above its price.",
            "These are the rye whiskeys that SipSense users can't stop rating highly.",
        ],
        "category": "rye",
        "limit": 15,
    },
    {
        "slug": "best-whiskeys-under-30",
        "title": f"Best Whiskeys Under $30 ({CURRENT_YEAR})",
        "meta_description": f"Great whiskey doesn't have to be expensive. The best bottles under $30 in {CURRENT_YEAR}, ranked by real ratings.",
        "intro": [
            "Think great whiskey requires a big budget? Think again. There are genuinely excellent bottles sitting on the bottom shelf, and our community has found them.",
            "Every whiskey on this list costs less than $30 and earns strong ratings from real drinkers. Perfect for daily sippers, cocktail bases, or discovering new favorites without the risk.",
        ],
        "price_max": 30,
        "limit": 15,
    },
    {
        "slug": "best-whiskeys-under-75",
        "title": f"Best Whiskeys Under $75 ({CURRENT_YEAR})",
        "meta_description": f"The top whiskeys under $75 across all categories. Bourbons, scotch, rye, and more — ranked by community ratings.",
        "intro": [
            "Seventy-five dollars is the sweet spot where quality meets accessibility. You're past the budget shelf but not yet in allocated-bottle territory — and the options are outstanding.",
            "This list pulls from every category: bourbon, scotch, rye, Irish, Japanese, and more. Sorted by what real people actually enjoy drinking.",
        ],
        "price_max": 75,
        "limit": 20,
    },
    {
        "slug": "best-value-whiskeys",
        "title": f"Best Value Whiskeys ({CURRENT_YEAR})",
        "meta_description": f"The highest-rated affordable whiskeys in {CURRENT_YEAR}. Maximum flavor for minimum spend — ranked by rating-to-price ratio.",
        "intro": [
            "Value in whiskey isn't about being cheap — it's about getting more quality per dollar than you'd expect. These bottles consistently over-deliver relative to their price tags.",
            "We calculated a value score by weighing each whiskey's community rating against its price. The result: bottles that punch way above their weight class.",
        ],
        "sort": "value",
        "price_max": 60,
        "limit": 15,
    },
    {
        "slug": "most-popular-whiskeys",
        "title": f"Most Popular Whiskeys on SipSense ({CURRENT_YEAR})",
        "meta_description": f"The most-reviewed and most-rated whiskeys on SipSense in {CURRENT_YEAR}. See what the community is drinking.",
        "intro": [
            "Popularity isn't everything — but it's a good signal. When thousands of whiskey drinkers all gravitate toward the same bottles, those bottles are usually doing something right.",
            "These are the whiskeys with the most check-ins and ratings on SipSense. The community has spoken.",
        ],
        "sort": "popular",
        "limit": 20,
    },
    {
        "slug": "highest-rated-whiskeys",
        "title": f"Highest Rated Whiskeys of All Time ({CURRENT_YEAR})",
        "meta_description": f"The absolute highest-rated whiskeys on SipSense. The best of the best, across all categories and price points.",
        "intro": [
            "Forget the marketing. Forget the hype. These are the whiskeys that consistently earn the highest ratings from real drinkers on SipSense.",
            "To make this list, a whiskey needs both a top rating and a meaningful number of reviews — no flukes allowed.",
        ],
        "sort": "rating",
        "min_ratings": 3,
        "limit": 20,
    },
    {
        "slug": "best-smoky-whiskeys",
        "title": f"Best Smoky Whiskeys ({CURRENT_YEAR})",
        "meta_description": f"Love smoke and peat? These are the highest-rated smoky whiskeys in {CURRENT_YEAR}, from Islay legends to unexpected finds.",
        "intro": [
            "If you love campfire in a glass, this list is for you. Smoky whiskeys — whether peated scotch, charcoal-filtered bourbon, or smoked malt from Japan — deliver a flavor experience like nothing else.",
            "These bottles earned the highest ratings among whiskeys tagged with smoky or peaty flavor profiles.",
        ],
        "flavor": "smok",
        "limit": 15,
    },
    {
        "slug": "best-sweet-whiskeys",
        "title": f"Best Sweet Whiskeys ({CURRENT_YEAR})",
        "meta_description": f"The best sweet, approachable whiskeys in {CURRENT_YEAR}. Vanilla, caramel, honey — ranked by community ratings.",
        "intro": [
            "Not everyone wants a peat monster. If you gravitate toward vanilla, caramel, honey, and butterscotch notes, these whiskeys were made for you.",
            "Rated highest among whiskeys with sweet flavor profiles, this list is perfect for newcomers and dessert-lovers alike.",
        ],
        "flavor": "sweet",
        "limit": 15,
    },
]

# Build lookup for quick access
_ARTICLE_MAP = {a["slug"]: a for a in ARTICLES}


def _query_whiskeys(db: Session, article: dict) -> list[dict]:
    """Query whiskeys matching an article's filters, return serialized list."""
    q = db.query(models.Whiskey).filter(
        models.Whiskey.image_url.isnot(None),
        models.Whiskey.image_url != "",
    )

    # Category filter
    if "category" in article:
        q = q.filter(
            sqlfunc.lower(models.Whiskey.category) == article["category"].lower()
        )

    # Price filter
    if "price_max" in article:
        q = q.filter(
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
            models.Whiskey.price_usd <= article["price_max"],
        )

    # Flavor filter (substring match on comma-separated flavor_profile)
    if "flavor" in article:
        q = q.filter(
            sqlfunc.lower(models.Whiskey.flavor_profile).contains(
                article["flavor"].lower()
            )
        )

    # Minimum ratings filter
    min_ratings = article.get("min_ratings", 1)
    q = q.filter(models.Whiskey.rating_count >= min_ratings)

    # Sorting
    sort = article.get("sort", "rating")
    if sort == "popular":
        q = q.order_by(models.Whiskey.rating_count.desc())
    elif sort == "value":
        # rating / price — higher is better
        q = q.filter(
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
        )
        q = q.order_by(
            (models.Whiskey.rating_avg / models.Whiskey.price_usd).desc()
        )
    else:
        # Default: by rating descending, then by rating count as tiebreaker
        q = q.order_by(
            models.Whiskey.rating_avg.desc(),
            models.Whiskey.rating_count.desc(),
        )

    limit = article.get("limit", 15)
    whiskeys = q.limit(limit).all()

    return [
        {
            "id": w.id,
            "name": w.name,
            "distillery": w.distillery,
            "category": w.category,
            "region": w.region,
            "age": w.age,
            "abv": w.abv,
            "price_usd": w.price_usd,
            "rating_avg": round(w.rating_avg, 1) if w.rating_avg else None,
            "rating_count": w.rating_count,
            "image_url": w.image_url,
            "flavor_profile": w.flavor_profile,
        }
        for w in whiskeys
    ]


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("/articles")
def list_articles():
    """Return all available blog articles (index page)."""
    return [
        {
            "slug": a["slug"],
            "title": a["title"],
            "meta_description": a["meta_description"],
        }
        for a in ARTICLES
    ]


@router.get("/articles/{slug}")
def get_article(slug: str = Path(...), db: Session = Depends(get_db)):
    """Return a single blog article with dynamically queried whiskeys."""
    article = _ARTICLE_MAP.get(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    whiskeys = _query_whiskeys(db, article)

    return {
        "slug": article["slug"],
        "title": article["title"],
        "meta_description": article["meta_description"],
        "intro": article["intro"],
        "whiskeys": whiskeys,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": CURRENT_YEAR,
    }
