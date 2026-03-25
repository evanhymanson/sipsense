from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database import get_db
from ..models import Whiskey

router = APIRouter(prefix="/flights", tags=["flights"])

# ─── Theme metadata ───────────────────────────────────────────────────────────

THEMES = {
    "beginner": {
        "label": "Beginner Flight",
        "emoji": "🌱",
        "tagline": "Four approachable drams for first-timers. All sweet, smooth, and easy to love.",
        "steps": [
            {"label": "First Dram", "lesson": "Notice the corn sweetness — this is whiskey's gentlest form. Find the vanilla."},
            {"label": "Getting Comfortable", "lesson": "Same backbone, more layers emerging. Look for caramel and soft baking spice."},
            {"label": "Building Flavor", "lesson": "The oak is speaking now. Search for dried fruit, nuttiness, or a drier finish."},
            {"label": "Level Up", "lesson": "Still smooth, but richer. This is what whiskey looks like once you've earned a palate."},
        ],
    },
    "smoky-journey": {
        "label": "Smoky Journey",
        "emoji": "🔥",
        "tagline": "Follow the peat from a whisper to a roar. Scotland's smokiest tradition.",
        "steps": [
            {"label": "First Hint", "lesson": "Smoke is background — like campfire smell on your jacket. Enjoy everything else around it."},
            {"label": "Getting Interesting", "lesson": "Now smoke is a character, not just an accent. Notice how it pairs with sweetness or brine."},
            {"label": "Full Peat", "lesson": "This is what most people think of when they hear 'peated scotch'. Medicinal, earthy, complex."},
            {"label": "Peat Beast", "lesson": "High PPM. No apologies. You've earned this dram — swirl it slow and let it breathe."},
        ],
    },
    "bourbon-ladder": {
        "label": "Bourbon Ladder",
        "emoji": "🥃",
        "tagline": "Climb from everyday to extraordinary. The full range of American whiskey.",
        "steps": [
            {"label": "The Foundation", "lesson": "Entry-level doesn't mean lesser. Learn the baseline: corn mash, new oak, vanilla."},
            {"label": "Mid-Shelf Mastery", "lesson": "More complexity per dollar here than almost anywhere. Notice the grain coming through."},
            {"label": "Premium Territory", "lesson": "Longer aging or special barrels. The finish lingers. Take your time."},
            {"label": "Top Shelf", "lesson": "This is what the hype is about. Rich, complex, and hard to find. Sip slowly."},
        ],
    },
    "scotch-regions": {
        "label": "Scotch Regions",
        "emoji": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "tagline": "One dram from each corner of Scotland. Same country, completely different whisky.",
        "steps": [
            {"label": "Speyside", "lesson": "Scotland's most prolific region. Fruit-forward, elegant, and often sherry-influenced."},
            {"label": "Highlands", "lesson": "Vast and varied. Can be heathery, coastal, rich, or peated — the wild card region."},
            {"label": "Islay", "lesson": "The island of peat. Medicinal, smoky, oceanic. This is why people argue about scotch."},
            {"label": "Lowlands", "lesson": "Scotland's gentlest whisky. Floral, light, and often triple-distilled like Irish whiskey."},
        ],
    },
    "world-tour": {
        "label": "World Tour",
        "emoji": "🌍",
        "tagline": "Five countries, five traditions, five completely different whisky philosophies.",
        "steps": [
            {"label": "America", "lesson": "Bourbon: new charred oak, corn mash, sweetness. The American signature."},
            {"label": "Scotland", "lesson": "Scotch: aged oak, often twice-distilled, shaped by peat and sea air."},
            {"label": "Ireland", "lesson": "Irish: triple-distilled, smoothest of all, often with honey and green apple."},
            {"label": "Japan", "lesson": "Japanese: precision blending, lighter style, influenced by Scottish tradition but distinctly its own."},
            {"label": "Rye", "lesson": "American rye: less corn, more spice. Drier finish. The bartender's favorite backbone."},
        ],
    },
    "sweet-to-spicy": {
        "label": "Sweet to Spicy",
        "emoji": "🌶️",
        "tagline": "Ride the spectrum from honeyed and soft to fiery and bold.",
        "steps": [
            {"label": "Pure Sweetness", "lesson": "Max honey, vanilla, caramel. No heat. This is the comfort zone."},
            {"label": "Balanced", "lesson": "Sweet up front, a little pepper on the back. Balance is the goal of most distillers."},
            {"label": "Spice Builds", "lesson": "The sweetness is a landing pad now. Heat and spice are the main event."},
            {"label": "Full Heat", "lesson": "High rye or high ABV, or both. The finish is long and warming. Respect it."},
        ],
    },
    "age-progression": {
        "label": "Age Progression",
        "emoji": "⏳",
        "tagline": "What oak actually does to whiskey over time. Four ages, four stories.",
        "steps": [
            {"label": "Young & Vibrant", "lesson": "Raw grain is present and that's a feature, not a bug. More spirit-forward than oak."},
            {"label": "Finding Balance", "lesson": "Oak integration is happening. Vanilla and tannin are in conversation with the grain."},
            {"label": "Mature", "lesson": "Oak has won — in a good way. Deep color, long finish, dried fruit notes emerging."},
            {"label": "Well Aged", "lesson": "This is what patience produces. Everything is integrated, nothing is fighting anything."},
        ],
    },
}


# ─── Query helpers per theme ──────────────────────────────────────────────────

def _filter_by_flavor(q, *keywords):
    return q.filter(or_(*[Whiskey.flavor_profile.ilike(f"%{k}%") for k in keywords]))


def _get_beginner(db, max_price, count):
    q = db.query(Whiskey).filter(
        Whiskey.category.in_(["bourbon", "irish"]),
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd <= (max_price or 65),
    )
    q = _filter_by_flavor(q, "vanilla", "caramel", "honey", "sweet")
    return q.order_by(Whiskey.price_usd).limit(count).all()


def _get_smoky_journey(db, max_price, count):
    q = db.query(Whiskey).filter(
        Whiskey.category == "scotch",
        Whiskey.price_usd.isnot(None),
    )
    q = _filter_by_flavor(q, "smoke", "peat", "smoky", "peated", "medicinal")
    if max_price:
        q = q.filter(Whiskey.price_usd <= max_price)
    return q.order_by(Whiskey.price_usd).limit(count).all()


def _get_bourbon_ladder(db, max_price, count):
    q = db.query(Whiskey).filter(
        Whiskey.category == "bourbon",
        Whiskey.price_usd.isnot(None),
    )
    if max_price:
        q = q.filter(Whiskey.price_usd <= max_price)
    return q.order_by(Whiskey.price_usd).limit(count).all()


def _get_scotch_regions(db, max_price, count):
    regions = ["Speyside", "Highlands", "Islay", "Lowlands", "Campbeltown"]
    bottles = []
    for region in regions:
        if len(bottles) >= count:
            break
        q = db.query(Whiskey).filter(
            Whiskey.category == "scotch",
            Whiskey.region.ilike(f"%{region}%"),
            Whiskey.price_usd.isnot(None),
        )
        if max_price:
            q = q.filter(Whiskey.price_usd <= max_price)
        w = q.order_by(Whiskey.rating_avg.desc()).first()
        if w:
            bottles.append(w)
    return bottles[:count]


def _get_world_tour(db, max_price, count):
    categories = ["bourbon", "scotch", "irish", "japanese", "rye"]
    bottles = []
    for cat in categories:
        if len(bottles) >= count:
            break
        q = db.query(Whiskey).filter(
            Whiskey.category == cat,
            Whiskey.price_usd.isnot(None),
        )
        if max_price:
            q = q.filter(Whiskey.price_usd <= max_price)
        w = q.order_by(Whiskey.rating_avg.desc()).first()
        if w:
            bottles.append(w)
    return bottles[:count]


def _get_sweet_to_spicy(db, max_price, count):
    sweet_q = db.query(Whiskey).filter(Whiskey.price_usd.isnot(None))
    sweet_q = _filter_by_flavor(sweet_q, "vanilla", "honey", "caramel", "sweet")
    if max_price:
        sweet_q = sweet_q.filter(Whiskey.price_usd <= max_price)
    sweet = sweet_q.order_by(Whiskey.rating_avg.desc()).limit(2).all()

    spicy_q = db.query(Whiskey).filter(Whiskey.price_usd.isnot(None))
    spicy_q = _filter_by_flavor(spicy_q, "spice", "pepper", "rye", "cinnamon", "ginger")
    if max_price:
        spicy_q = spicy_q.filter(Whiskey.price_usd <= max_price)
    # exclude already-selected ids
    used_ids = [w.id for w in sweet]
    if used_ids:
        spicy_q = spicy_q.filter(~Whiskey.id.in_(used_ids))
    spicy = spicy_q.order_by(Whiskey.rating_avg.desc()).limit(2).all()

    # interleave: sweet, balanced(sweet+spice), spicy, very spicy
    combined = sweet[:1] + sweet[1:2] + spicy[:1] + spicy[1:2]
    return combined[:count]


def _get_age_progression(db, max_price, count):
    q = db.query(Whiskey).filter(
        Whiskey.age.isnot(None),
        Whiskey.price_usd.isnot(None),
    )
    if max_price:
        q = q.filter(Whiskey.price_usd <= max_price)
    return q.order_by(Whiskey.age).limit(count).all()


_QUERY_MAP = {
    "beginner": _get_beginner,
    "smoky-journey": _get_smoky_journey,
    "bourbon-ladder": _get_bourbon_ladder,
    "scotch-regions": _get_scotch_regions,
    "world-tour": _get_world_tour,
    "sweet-to-spicy": _get_sweet_to_spicy,
    "age-progression": _get_age_progression,
}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/")
def list_themes():
    """Return all available flight themes."""
    return [
        {
            "slug": slug,
            "label": meta["label"],
            "emoji": meta["emoji"],
            "tagline": meta["tagline"],
        }
        for slug, meta in THEMES.items()
    ]


@router.get("/{theme}")
def get_flight(
    theme: str,
    max_price: float = 0.0,
    count: int = 4,
    db: Session = Depends(get_db),
):
    if theme not in THEMES:
        raise HTTPException(status_code=404, detail=f"Unknown theme '{theme}'. Valid options: {list(THEMES)}")

    meta = THEMES[theme]
    query_fn = _QUERY_MAP[theme]
    bottles = query_fn(db, max_price or 0, count)

    if not bottles:
        raise HTTPException(status_code=404, detail="Not enough whiskeys found for this flight. Try removing the price filter.")

    steps = meta["steps"]
    result = []
    for i, whiskey in enumerate(bottles):
        step = steps[i] if i < len(steps) else {"label": f"Step {i + 1}", "lesson": ""}
        result.append({
            "step": i + 1,
            "step_label": step["label"],
            "lesson": step["lesson"],
            "whiskey": {
                "id": whiskey.id,
                "name": whiskey.name,
                "distillery": whiskey.distillery,
                "category": whiskey.category,
                "region": whiskey.region,
                "age": whiskey.age,
                "abv": whiskey.abv,
                "price_usd": whiskey.price_usd,
                "flavor_profile": whiskey.flavor_profile,
                "rating_avg": whiskey.rating_avg,
                "rating_count": whiskey.rating_count,
            },
        })

    return {
        "theme": theme,
        "label": meta["label"],
        "emoji": meta["emoji"],
        "tagline": meta["tagline"],
        "bottles": result,
    }
