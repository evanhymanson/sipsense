"""
SipSense Discover Router

Returns pre-assembled graph data for the Obsidian-inspired knowledge graph.
Combines categories, flavors, distilleries, regions, and journeys into
a single { nodes, links } response.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db
from ..models import Journey, UserJourneyProgress
from ..auth import get_optional_user
from .learn import CATEGORIES, DISTILLERIES

router = APIRouter(prefix="/discover", tags=["discover"])

# ── Flavor families (mirrors frontend flavorTaxonomy.js) ─────────────────────
FLAVOR_FAMILIES = [
    {"id": "smoky",  "label": "Smoky",  "color": "#4b5563"},
    {"id": "sweet",  "label": "Sweet",  "color": "#b45309"},
    {"id": "fruity", "label": "Fruity", "color": "#be185d"},
    {"id": "spicy",  "label": "Spicy",  "color": "#c2410c"},
    {"id": "woody",  "label": "Woody",  "color": "#7c2d12"},
    {"id": "floral", "label": "Floral", "color": "#6d28d9"},
    {"id": "grainy", "label": "Grainy", "color": "#a16207"},
]

# Which flavor families each category is known for
CATEGORY_FLAVORS = {
    "bourbon":  ["sweet", "woody", "spicy"],
    "scotch":   ["smoky", "fruity", "floral"],
    "rye":      ["spicy", "woody", "grainy"],
    "irish":    ["fruity", "sweet", "floral"],
    "japanese": ["floral", "fruity", "sweet"],
    "canadian": ["sweet", "grainy", "spicy"],
}

# Regions and their categories
REGIONS = [
    {"id": "kentucky",     "label": "Kentucky",     "categories": ["bourbon"]},
    {"id": "tennessee",    "label": "Tennessee",    "categories": ["bourbon"]},
    {"id": "speyside",     "label": "Speyside",     "categories": ["scotch"]},
    {"id": "islay",        "label": "Islay",        "categories": ["scotch"]},
    {"id": "highlands",    "label": "Highlands",    "categories": ["scotch"]},
    {"id": "lowlands",     "label": "Lowlands",     "categories": ["scotch"]},
    {"id": "campbeltown",  "label": "Campbeltown",  "categories": ["scotch"]},
    {"id": "ireland",      "label": "Ireland",      "categories": ["irish"]},
    {"id": "japan",        "label": "Japan",        "categories": ["japanese"]},
    {"id": "canada",       "label": "Canada",       "categories": ["canadian"]},
]

# Distillery → category mapping (derived from learn.py data)
DISTILLERY_CATEGORIES = {
    "makers-mark":   "bourbon",
    "buffalo-trace": "bourbon",
    "wild-turkey":   "bourbon",
    "four-roses":    "bourbon",
    "glenfiddich":   "scotch",
    "laphroaig":     "scotch",
    "ardbeg":        "scotch",
    "macallan":      "scotch",
    "yamazaki":      "japanese",
    "jameson":       "irish",
    "redbreast":     "irish",
}

# Distillery → region mapping
DISTILLERY_REGIONS = {
    "makers-mark":   "kentucky",
    "buffalo-trace": "kentucky",
    "wild-turkey":   "kentucky",
    "four-roses":    "kentucky",
    "glenfiddich":   "speyside",
    "laphroaig":     "islay",
    "ardbeg":        "islay",
    "macallan":      "speyside",
    "yamazaki":      "japan",
    "jameson":       "ireland",
    "redbreast":     "ireland",
}


@router.get("/graph")
def get_graph_data(db: Session = Depends(get_db)):
    nodes = []
    links = []

    # ── Category nodes ───────────────────────────────────────────────
    for cat in CATEGORIES:
        nodes.append({
            "id": f"cat-{cat['slug']}",
            "label": cat["title"],
            "type": "category",
            "emoji": cat["emoji"],
            "slug": cat["slug"],
            "val": 8,
        })

    # ── Flavor family nodes ──────────────────────────────────────────
    for fam in FLAVOR_FAMILIES:
        nodes.append({
            "id": f"flavor-{fam['id']}",
            "label": fam["label"],
            "type": "flavor",
            "color": fam["color"],
            "val": 5,
        })

    # ── Region nodes ─────────────────────────────────────────────────
    for reg in REGIONS:
        nodes.append({
            "id": f"region-{reg['id']}",
            "label": reg["label"],
            "type": "region",
            "val": 4,
        })

    # ── Distillery nodes ─────────────────────────────────────────────
    for dist in DISTILLERIES:
        nodes.append({
            "id": f"dist-{dist['slug']}",
            "label": dist["title"],
            "type": "distillery",
            "emoji": dist["emoji"],
            "slug": dist["slug"],
            "val": 3,
        })

    # ── Activity nodes ───────────────────────────────────────────────
    for act in [
        {"id": "activity-quiz",          "label": "Taste Quiz",     "emoji": "🎯"},
        {"id": "activity-blind-tasting", "label": "Blind Tasting",  "emoji": "🫣"},
        {"id": "activity-flights",       "label": "Flight Builder", "emoji": "✈️"},
        {"id": "activity-glossary",      "label": "Glossary",       "emoji": "📖"},
    ]:
        nodes.append({**act, "type": "activity", "val": 4})

    # ── Journey nodes ────────────────────────────────────────────────
    try:
        journeys = db.query(Journey).all()
        for j in journeys:
            nodes.append({
                "id": f"journey-{j.slug}",
                "label": j.title,
                "type": "journey",
                "slug": j.slug,
                "emoji": j.image_emoji or "🗺️",
                "val": 4,
            })
    except Exception as e:
        logger.warning("Failed to load journeys for discover graph: %s", e)

    # ── Links: category ↔ flavor ─────────────────────────────────────
    for cat_slug, flavors in CATEGORY_FLAVORS.items():
        for flav in flavors:
            links.append({
                "source": f"cat-{cat_slug}",
                "target": f"flavor-{flav}",
            })

    # ── Links: category ↔ region ─────────────────────────────────────
    for reg in REGIONS:
        for cat in reg["categories"]:
            links.append({
                "source": f"cat-{cat}",
                "target": f"region-{reg['id']}",
            })

    # ── Links: distillery ↔ category ─────────────────────────────────
    for slug, cat in DISTILLERY_CATEGORIES.items():
        links.append({
            "source": f"dist-{slug}",
            "target": f"cat-{cat}",
        })

    # ── Links: distillery ↔ region ───────────────────────────────────
    for slug, reg in DISTILLERY_REGIONS.items():
        links.append({
            "source": f"dist-{slug}",
            "target": f"region-{reg}",
        })

    return {"nodes": nodes, "links": links}
