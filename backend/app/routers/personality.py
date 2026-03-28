"""
Whiskey Personality — generates a fun archetype based on user's rating & favorite patterns.

GET /personality/me  — returns personality type, title, description, and traits
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from collections import Counter

from ..database import get_db
from ..models import User, UserRating, UserFavorite, Whiskey
from ..auth import get_current_user

router = APIRouter(prefix="/personality", tags=["personality"])

# ── Personality archetypes ────────────────────────────────────────────────
# Each archetype is keyed by (dominant_trait, secondary_trait).
# We derive traits from the user's category preferences, flavor leanings,
# price range, and adventurousness (how many different categories they've tried).

ARCHETYPES = {
    ("smoky", "bold"): {
        "type": "campfire_poet",
        "title": "The Campfire Poet",
        "emoji": "🔥",
        "tagline": "You like your whiskey the way you like your stories — smoky, intense, and unforgettable.",
        "description": (
            "You're drawn to peat, char, and that unmistakable campfire warmth. "
            "You probably enjoy a glass by an actual fire, or at least imagining one. "
            "Islay scotches whisper your name, and you're not afraid of a whiskey that fights back."
        ),
        "spirit_bottle": "Laphroaig 10",
        "playlist_vibe": "Blues guitar by a bonfire",
    },
    ("smoky", "explorer"): {
        "type": "storm_chaser",
        "title": "The Storm Chaser",
        "emoji": "⛈️",
        "tagline": "You seek out the bold, the wild, and the beautifully chaotic.",
        "description": (
            "Not content with just one style, you love smoky whiskies but you chase them "
            "across countries and categories. Japanese peated malts? Island scotches? Smoked bourbon? "
            "If it has depth and danger, you're in."
        ),
        "spirit_bottle": "Hakushu Distiller's Reserve",
        "playlist_vibe": "Thunderstorm ambience with jazz",
    },
    ("sweet", "comfort"): {
        "type": "smooth_operator",
        "title": "The Smooth Operator",
        "emoji": "🍯",
        "tagline": "Life's too short for harsh edges. You know what you like, and it's delicious.",
        "description": (
            "Vanilla, caramel, honey — these aren't just flavors to you, they're a lifestyle. "
            "You gravitate toward approachable, well-crafted whiskeys that feel like a warm hug. "
            "Bourbon is probably your home base, and you make excellent cocktails."
        ),
        "spirit_bottle": "Maker's Mark",
        "playlist_vibe": "Sunday morning soul",
    },
    ("sweet", "explorer"): {
        "type": "golden_wanderer",
        "title": "The Golden Wanderer",
        "emoji": "✨",
        "tagline": "Sweet is your compass, but curiosity is your map.",
        "description": (
            "You started with the crowd-pleasers — bourbon, Irish, maybe a Japanese highball — "
            "but now you're chasing that sweetness through sherry casks, port finishes, and "
            "tropical rum-barrel experiments. Every bottle is a new chapter."
        ),
        "spirit_bottle": "Redbreast 12",
        "playlist_vibe": "Indie folk road trip",
    },
    ("complex", "bold"): {
        "type": "midnight_scholar",
        "title": "The Midnight Scholar",
        "emoji": "📚",
        "tagline": "You don't just drink whiskey — you study it.",
        "description": (
            "You appreciate layers, transitions, and the kind of complexity that reveals itself "
            "over 30 minutes with a good glass. Sherry-matured scotches, cask-strength pours, "
            "and anything with a story behind it. Your friends come to you for recommendations."
        ),
        "spirit_bottle": "GlenDronach 15 Revival",
        "playlist_vibe": "Late-night piano bar",
    },
    ("complex", "explorer"): {
        "type": "globe_trotter",
        "title": "The Globe Trotter",
        "emoji": "🌍",
        "tagline": "Your palate has a passport, and it's well-stamped.",
        "description": (
            "From Kentucky to Kyoto, Islay to Ireland, you've tasted your way around the world. "
            "You love comparing how different regions and traditions interpret the same grain. "
            "Your collection probably needs its own room."
        ),
        "spirit_bottle": "Nikka From the Barrel",
        "playlist_vibe": "World music mixtape",
    },
    ("fruity", "comfort"): {
        "type": "orchard_keeper",
        "title": "The Orchard Keeper",
        "emoji": "🍎",
        "tagline": "You find the sunshine in every sip.",
        "description": (
            "Apple, pear, citrus, dried fruit — you're drawn to whiskeys that feel alive and bright. "
            "Speyside malts and light Irish whiskeys are your happy place. You probably prefer your "
            "whiskey with a splash of water to open up those fruity notes."
        ),
        "spirit_bottle": "Glenmorangie Original",
        "playlist_vibe": "Acoustic coffee shop set",
    },
    ("fruity", "explorer"): {
        "type": "sunset_chaser",
        "title": "The Sunset Chaser",
        "emoji": "🌅",
        "tagline": "You're chasing that golden moment in every glass.",
        "description": (
            "Fruity, floral, and a little bit wild — you love whiskeys that surprise you. "
            "Wine cask finishes, tropical notes from Japanese distilleries, and anything that "
            "makes you say 'wait, is this really whiskey?' You're the fun one at tastings."
        ),
        "spirit_bottle": "Yamazaki 12",
        "playlist_vibe": "Tropical lo-fi beats",
    },
    ("spicy", "bold"): {
        "type": "trailblazer",
        "title": "The Trailblazer",
        "emoji": "🌶️",
        "tagline": "You like your whiskey with a kick and your adventures with an edge.",
        "description": (
            "High-rye bourbons, cask-strength ryes, and anything that tingles on the tongue — "
            "that's your territory. You're not here for gentle sipping; you want character, "
            "spice, and a finish that sticks around. You make a killer Manhattan."
        ),
        "spirit_bottle": "Rittenhouse Rye",
        "playlist_vibe": "High-energy Americana",
    },
    ("spicy", "explorer"): {
        "type": "spice_merchant",
        "title": "The Spice Merchant",
        "emoji": "🧭",
        "tagline": "You've mapped the spice routes of the whiskey world.",
        "description": (
            "Rye spice, baking spices from bourbon, peppery Islay drams, Indian single malts — "
            "you find spice in every corner of the whiskey world and you love comparing them. "
            "Your palate can tell the difference between cinnamon and clove at 50 paces."
        ),
        "spirit_bottle": "Amrut Fusion",
        "playlist_vibe": "Bazaar vibes — sitar meets electronica",
    },
}

# Fallback for users with minimal data
DEFAULT_ARCHETYPE = {
    "type": "curious_newcomer",
    "title": "The Curious Newcomer",
    "emoji": "🥃",
    "tagline": "Every expert was once a beginner. Your journey starts here.",
    "description": (
        "You're at the very beginning of your whiskey adventure, and that's the most exciting "
        "place to be. Everything is new, every sip is a discovery. Take the taste quiz, "
        "rate a few bottles, and watch your personality emerge."
    ),
    "spirit_bottle": "Buffalo Trace",
    "playlist_vibe": "Discovery playlist on shuffle",
}


def _classify_dominant_trait(flavor_counts: Counter) -> str:
    """Determine the user's dominant flavor trait."""
    smoky_score = sum(flavor_counts.get(f, 0) for f in ["smoky", "peaty", "charred", "campfire"])
    sweet_score = sum(flavor_counts.get(f, 0) for f in ["sweet", "vanilla", "caramel", "honey", "butterscotch", "toffee"])
    fruity_score = sum(flavor_counts.get(f, 0) for f in ["fruity", "citrus", "apple", "pear", "tropical", "dried fruit", "floral"])
    spicy_score = sum(flavor_counts.get(f, 0) for f in ["spicy", "pepper", "cinnamon", "rye spice", "ginger", "clove"])
    complex_score = sum(flavor_counts.get(f, 0) for f in ["oak", "leather", "tobacco", "nutty", "chocolate", "dark fruit", "sherry"])

    scores = {
        "smoky": smoky_score,
        "sweet": sweet_score,
        "fruity": fruity_score,
        "spicy": spicy_score,
        "complex": complex_score,
    }
    return max(scores, key=scores.get) if any(v > 0 for v in scores.values()) else "sweet"


def _classify_secondary_trait(category_counts: Counter, total_rated: int) -> str:
    """Determine if user is an explorer (diverse tastes) or comfort-seeker (sticks to one style)."""
    num_categories = len(category_counts)
    if num_categories >= 4 or (total_rated >= 5 and num_categories >= 3):
        return "explorer"
    # Check if they gravitate toward bold (high ABV, high price)
    return "bold" if total_rated >= 3 else "comfort"


@router.get("/me")
def get_my_personality(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username

    # Load only whiskey IDs (not full ORM objects) to reduce memory/hydration overhead
    rated_wids = [
        row[0] for row in
        db.query(UserRating.whiskey_id).filter(UserRating.user_id == user_id).all()
    ]
    fav_wids = [
        row[0] for row in
        db.query(UserFavorite.whiskey_id).filter(UserFavorite.user_id == user_id).all()
    ]

    total_rated = len(rated_wids)
    total_favorites = len(fav_wids)
    if total_rated + total_favorites < 2:
        return {**DEFAULT_ARCHETYPE, "stats": {"total_rated": total_rated, "total_favorites": total_favorites}}

    # Get whiskey data for all interactions
    whiskey_ids = list(set(rated_wids + fav_wids))
    whiskeys = db.query(Whiskey).filter(Whiskey.id.in_(whiskey_ids)).all()
    whiskey_map = {w.id: w for w in whiskeys}

    # Count flavors and categories
    flavor_counts: Counter = Counter()
    category_counts: Counter = Counter()
    prices = []
    abvs = []

    for wid in rated_wids:
        w = whiskey_map.get(wid)
        if not w:
            continue
        category_counts[w.category] += 1
        if w.price_usd:
            prices.append(w.price_usd)
        if w.abv:
            abvs.append(w.abv)
        if w.flavor_profile:
            for tag in [t.strip().lower() for t in w.flavor_profile.split(",") if t.strip()]:
                flavor_counts[tag] += 1

    for wid in fav_wids:
        w = whiskey_map.get(wid)
        if not w:
            continue
        category_counts[w.category] += 1
        if w.flavor_profile:
            for tag in [t.strip().lower() for t in w.flavor_profile.split(",") if t.strip()]:
                flavor_counts[tag] += 0.5  # favorites count less than ratings

    dominant = _classify_dominant_trait(flavor_counts)
    secondary = _classify_secondary_trait(category_counts, total_rated)

    archetype = ARCHETYPES.get((dominant, secondary))
    if not archetype:
        # Try just the dominant trait with either secondary
        for sec in ["explorer", "bold", "comfort"]:
            archetype = ARCHETYPES.get((dominant, sec))
            if archetype:
                break
        if not archetype:
            archetype = DEFAULT_ARCHETYPE

    top_flavors = [f for f, _ in flavor_counts.most_common(5)]
    top_categories = [c for c, _ in category_counts.most_common(3)]

    return {
        **archetype,
        "dominant_trait": dominant,
        "secondary_trait": secondary,
        "stats": {
            "total_rated": total_rated,
            "total_favorites": total_favorites,
            "categories_explored": len(category_counts),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "avg_abv": round(sum(abvs) / len(abvs), 1) if abvs else None,
        },
        "top_flavors": top_flavors,
        "top_categories": top_categories,
    }
