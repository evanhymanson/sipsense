"""
Enrich whiskey prices in the SipSense database.

Multi-phase approach:
  Phase 1: Internal cross-reference (fuzzy name matching against existing prices)
  Phase 2: Web retail lookup (Wine-Searcher average prices)
  Phase 3: Statistical estimation (category + age + distillery model)
  Phase 4: Audit and verification

Usage:
  cd backend
  python -m scripts.enrich_prices                          # all phases
  python -m scripts.enrich_prices --phase 1                # cross-ref only
  python -m scripts.enrich_prices --phase 2 --limit 5000   # web lookup, 5K max
  python -m scripts.enrich_prices --phase 3                # statistical estimation
  python -m scripts.enrich_prices --audit                  # verification only
  python -m scripts.enrich_prices --dry-run                # preview changes
  python -m scripts.enrich_prices --resume                 # resume from checkpoint
"""

import argparse
import json
import logging
import re
import sys
import time
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Allow imports from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Whiskey, PriceEnrichmentLog

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("WARNING: rapidfuzz not installed. Fuzzy matching disabled.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Progress tracking ────────────────────────────────────────────────────

PROGRESS_FILE = Path(__file__).parent / "enrich_prices_progress.json"

PROGRESS_DEFAULTS = {
    "phase1_done": False,
    "phase2_index": 0,
    "phase2_done": False,
    "phase3_done": False,
    "total_enriched": 0,
    "by_method": {
        "exact_match": 0,
        "fuzzy_match": 0,
        "cross_ref": 0,
        "web_lookup": 0,
        "statistical": 0,
    },
}


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return dict(PROGRESS_DEFAULTS)


def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ── Name normalization for price matching ────────────────────────────────

# Suffixes to strip (longest first)
_SUFFIXES = [
    "kentucky straight bourbon whiskey",
    "kentucky straight bourbon",
    "single malt scotch whisky",
    "single malt scotch whiskey",
    "blended scotch whisky",
    "blended scotch whiskey",
    "single malt whisky",
    "single malt whiskey",
    "blended malt whisky",
    "blended malt whiskey",
    "scotch whisky", "scotch whiskey",
    "irish whiskey", "irish whisky",
    "bourbon whiskey", "bourbon whisky",
    "tennessee whiskey", "tennessee whisky",
    "canadian whisky", "canadian whiskey",
    "japanese whisky", "japanese whiskey",
    "american whiskey", "american whisky",
    "rye whiskey", "rye whisky",
    "corn whiskey", "wheat whiskey",
    "grain whisky", "whisky", "whiskey",
]


def normalize_for_price(name: str) -> str:
    """Aggressively normalize a whiskey name for price matching."""
    s = name.lower().strip()
    if s.startswith("the "):
        s = s[4:]
    # Normalize age: "12 year old" → "12yo"
    s = re.sub(
        r"(\d+)\s*(?:year[s]?\s*old|year[s]?|yr[s]?\s*old|yr[s]?|yo|y\.o\.?)",
        r"\1yo", s, flags=re.I,
    )
    # Strip whiskey-type suffixes
    for suffix in _SUFFIXES:
        s = s.replace(suffix, "")
    # Strip cask numbers
    s = re.sub(r"cask\s*(?:#|no\.?)\s*\d+", "", s)
    # Strip batch numbers
    s = re.sub(r"batch\s*(?:no\.?)?\s*\d+", "", s)
    # Strip vintage years
    s = re.sub(r"\b(19|20)\d{2}\b", "", s)
    # Strip bottle sizes
    s = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", s, flags=re.I)
    # Strip SMWS codes
    s = re.sub(r"\bsmws\s*\d+\.\d+\b", "", s, flags=re.I)
    # Normalize punctuation
    s = s.replace("'", "").replace("\u2019", "").replace("`", "")
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip("-").strip()
    return s


def age_bucket(age) -> str:
    """Map an age to a bucket for grouping."""
    if age is None:
        return "NAS"
    a = int(age)
    if a <= 7:
        return "3-7"
    if a <= 12:
        return "8-12"
    if a <= 17:
        return "13-17"
    if a <= 25:
        return "18-25"
    return "26+"


# ── Phase 1: Internal Cross-Reference ───────────────────────────────────

def phase1_cross_reference(db: Session, dry_run: bool = False) -> dict:
    """
    Match unpriced whiskeys against priced ones in the DB.

    1A: Exact and fuzzy name matching
    1B: Distillery + category + age bucket median
    """
    log.info("=== Phase 1: Internal Cross-Reference ===")

    # Load priced whiskeys
    priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
    ).all()
    log.info("Loaded %d priced whiskeys for reference", len(priced))

    # Load unpriced whiskeys
    unpriced = db.query(Whiskey).filter(
        or_(Whiskey.price_usd.is_(None), Whiskey.price_usd == 0),
    ).all()
    log.info("Found %d unpriced whiskeys", len(unpriced))

    # ── Build indexes ────────────────────────────────────────────────────
    # Index 1: normalized name → list of (id, price, distillery)
    name_index: dict[str, list[tuple[int, float, str]]] = defaultdict(list)
    # Index 2: distillery bucket → list of (name_norm, id, price)
    distillery_index: dict[str, list[tuple[str, int, float]]] = defaultdict(list)
    # Index 3: (distillery, category, age_bucket) → list of prices
    group_index: dict[tuple, list[float]] = defaultdict(list)

    for w in priced:
        norm = normalize_for_price(w.name)
        dist = (w.distillery or "").lower().strip()
        name_index[norm].append((w.id, w.price_usd, dist))
        if dist:
            distillery_index[dist].append((norm, w.id, w.price_usd))
        bucket = age_bucket(w.age)
        group_index[(dist, w.category, bucket)].append(w.price_usd)

    stats = {"exact_match": 0, "fuzzy_match": 0, "cross_ref": 0}
    updates = []  # (whiskey_id, price, method, confidence, source_detail)

    for i, w in enumerate(unpriced):
        if i % 5000 == 0 and i > 0:
            log.info("  Phase 1 progress: %d / %d", i, len(unpriced))

        norm = normalize_for_price(w.name)
        dist = (w.distillery or "").lower().strip()

        # ── 1A: Exact name match ─────────────────────────────────────
        if norm in name_index:
            matches = name_index[norm]
            # Prefer same distillery
            same_dist = [m for m in matches if m[2] == dist] if dist else []
            best = same_dist if same_dist else matches
            price = statistics.median([m[1] for m in best])
            matched_id = best[0][0]
            updates.append((
                w.id, round(price, 2), "exact_match", 0.95,
                f"matched name '{norm}' (ref id={matched_id})",
            ))
            stats["exact_match"] += 1
            continue

        # ── 1A: Fuzzy name match (same distillery, score >= 92) ──────
        if HAS_RAPIDFUZZ and dist and dist in distillery_index:
            best_score = 0
            best_match = None
            for (cand_norm, cand_id, cand_price) in distillery_index[dist]:
                score = fuzz.token_sort_ratio(norm, cand_norm)
                if score > best_score:
                    best_score = score
                    best_match = (cand_id, cand_price, cand_norm)
            if best_score >= 92 and best_match:
                updates.append((
                    w.id, round(best_match[1], 2), "fuzzy_match", 0.85,
                    f"fuzzy {best_score:.0f}% match '{best_match[2]}' (ref id={best_match[0]})",
                ))
                stats["fuzzy_match"] += 1
                continue

        # ── 1B: Distillery + category + age bucket median ────────────
        bucket = age_bucket(w.age)
        key = (dist, w.category, bucket)
        if key in group_index and len(group_index[key]) >= 3:
            price = statistics.median(group_index[key])
            updates.append((
                w.id, round(price, 2), "cross_ref", 0.65,
                f"median of {len(group_index[key])} in ({dist}, {w.category}, {bucket})",
            ))
            stats["cross_ref"] += 1
            continue

        # Try broader: (distillery, category) without age
        key2 = (dist, w.category, None)
        # Build this from group_index
        broader_prices = []
        for (d, c, b), prices in group_index.items():
            if d == dist and c == w.category:
                broader_prices.extend(prices)
        if len(broader_prices) >= 5:
            price = statistics.median(broader_prices)
            updates.append((
                w.id, round(price, 2), "cross_ref", 0.55,
                f"median of {len(broader_prices)} in ({dist}, {w.category}, all ages)",
            ))
            stats["cross_ref"] += 1

    log.info(
        "Phase 1 results: exact=%d, fuzzy=%d, cross_ref=%d, total=%d",
        stats["exact_match"], stats["fuzzy_match"], stats["cross_ref"],
        sum(stats.values()),
    )

    if not dry_run:
        _apply_updates(db, updates)

    return stats


# ── Phase 2: Web Price Lookup ────────────────────────────────────────────

def _build_search_query(w: Whiskey) -> str:
    """Build a clean search query for a whiskey."""
    parts = []
    dist = (w.distillery or "").strip()
    if dist and dist.lower() != "unknown":
        parts.append(dist)

    # Extract the core expression from the name (remove distillery if already added)
    name = w.name
    if dist and name.lower().startswith(dist.lower()):
        name = name[len(dist):].strip()
    # Remove type suffixes
    for suffix in _SUFFIXES:
        name = re.sub(re.escape(suffix), "", name, flags=re.I)
    # Remove sizes, cask numbers, batch numbers
    name = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", name, flags=re.I)
    name = re.sub(r"cask\s*(?:#|no\.?)\s*\d+", "", name, flags=re.I)
    name = re.sub(r"batch\s*(?:no\.?)?\s*\d+", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip().strip("-").strip()
    if name:
        parts.append(name)

    query = " ".join(parts).strip()
    # Limit query length
    if len(query) > 80:
        query = query[:80].rsplit(" ", 1)[0]
    return query


def _compute_priority(w: Whiskey) -> int:
    """Lower = higher priority for web lookup."""
    score = 50

    # Boost real commercial products (government registries)
    if w.source in ("ttb", "texas_tabc", "connecticut_liquor", "missouri_liquor"):
        score -= 20
    if w.source in ("iowa_liquor", "oregon_olcc"):
        score -= 15
    if w.source == "whiskycom":
        score -= 10

    # Penalize indie bottlings (unlikely to find retail price)
    name_lower = (w.name or "").lower()
    indie_keywords = ("smws", "single cask", "private", "exclusive", "society",
                      "independent", "signatory", "gordon & macphail", "g&m",
                      "cadenhead", "berry bros", "adelphi")
    if any(k in name_lower for k in indie_keywords):
        score += 30

    # Boost standard ages
    if w.age in (10, 12, 15, 18, 21, 25):
        score -= 10

    # Boost popular distilleries
    popular = {
        "macallan", "glenfiddich", "glenlivet", "ardbeg", "lagavulin",
        "laphroaig", "highland park", "balvenie", "jack daniel's",
        "maker's mark", "buffalo trace", "wild turkey", "jameson",
        "woodford reserve", "knob creek", "bulleit", "monkey shoulder",
        "talisker", "oban", "dalmore", "glenmorangie",
    }
    if w.distillery and w.distillery.lower() in popular:
        score -= 15

    return score


def phase2_web_lookup(db: Session, dry_run: bool = False, limit: int = 0,
                      resume_index: int = 0) -> dict:
    """
    Upgrade estimated prices using reliable public API sources.

    Sources:
      1. Iowa Liquor Products Catalog (Socrata API) — official state retail prices
      2. Curated MSRP dictionary for ~500 popular bottles

    These replace the unreliable web scraping approach since all major
    retail sites use bot protection (PerimeterX, Cloudflare).
    """
    log.info("=== Phase 2: API Price Lookup ===")

    import httpx

    stats = {"web_lookup": 0}
    updates = []

    # ── Step 1: Fetch Iowa product catalog prices ────────────────────
    log.info("Fetching Iowa Liquor Products catalog...")
    iowa_prices = _fetch_iowa_prices()
    log.info("  Loaded %d Iowa products with prices", len(iowa_prices))

    # ── Step 2: Build MSRP reference dict ────────────────────────────
    msrp = _build_msrp_dict()
    log.info("  Loaded %d MSRP reference prices", len(msrp))

    # Combine into one lookup: normalized_name → price
    combined_prices: dict[str, float] = {}
    # MSRP takes priority (more curated)
    for name, price in iowa_prices.items():
        combined_prices[name] = price
    for name, price in msrp.items():
        combined_prices[name] = price

    log.info("  Combined price reference: %d entries", len(combined_prices))

    # ── Step 3: Match against estimated whiskeys ─────────────────────
    estimated = db.query(Whiskey).filter(
        Whiskey.price_is_estimated == True,
    ).all()
    log.info("Matching %d estimated whiskeys against reference prices...", len(estimated))

    # Build index for fast fuzzy matching
    ref_names = list(combined_prices.keys())
    # Group by first 4 chars for efficient fuzzy lookup
    ref_buckets: dict[str, list[str]] = defaultdict(list)
    for name in ref_names:
        key = name[:4] if len(name) >= 4 else name
        ref_buckets[key].append(name)

    matched = 0
    for i, w in enumerate(estimated):
        if i % 5000 == 0 and i > 0:
            log.info("  Progress: %d / %d, matched %d", i, len(estimated), matched)

        norm = normalize_for_price(w.name)
        if not norm:
            continue

        # Try exact match first
        if norm in combined_prices:
            price = combined_prices[norm]
            updates.append((
                w.id, price, "web_lookup", 0.90,
                f"exact match in reference db: '{norm}'",
            ))
            matched += 1
            continue

        # Try fuzzy match within same bucket
        if HAS_RAPIDFUZZ:
            bucket_key = norm[:4] if len(norm) >= 4 else norm
            best_score = 0
            best_price = None
            best_name = None
            for cand in ref_buckets.get(bucket_key, []):
                score = fuzz.token_sort_ratio(norm, cand)
                if score > best_score:
                    best_score = score
                    best_price = combined_prices[cand]
                    best_name = cand

            if best_score >= 88 and best_price:
                updates.append((
                    w.id, best_price, "web_lookup", 0.85,
                    f"fuzzy {best_score:.0f}% ref match: '{best_name}'",
                ))
                matched += 1
                continue

    stats["web_lookup"] = matched

    if not dry_run and updates:
        _apply_updates(db, updates)

    log.info("Phase 2 results: upgraded %d estimated prices to reference prices", matched)
    return stats


def _fetch_iowa_prices() -> dict[str, float]:
    """Fetch all whiskey prices from Iowa Liquor Products catalog API."""
    import httpx

    prices = {}
    client = httpx.Client(timeout=30)

    try:
        offset = 0
        batch = 1000
        while True:
            resp = client.get(
                "https://data.iowa.gov/resource/gckp-fe7r.json",
                params={
                    "$limit": str(batch),
                    "$offset": str(offset),
                    "$where": (
                        "upper(category_name) like '%BOURBON%' OR "
                        "upper(category_name) like '%SCOTCH%' OR "
                        "upper(category_name) like '%WHISK%' OR "
                        "upper(category_name) like '%TENNESSEE%' OR "
                        "upper(category_name) like '%RYE%' OR "
                        "upper(category_name) like '%SINGLE MALT%'"
                    ),
                    "$select": "im_desc, state_bottle_retail, bottle_volume_ml",
                },
            )
            if resp.status_code != 200:
                log.warning("Iowa API error: %s", resp.status_code)
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                name = item.get("im_desc", "")
                price_str = item.get("state_bottle_retail")
                vol = item.get("bottle_volume_ml", "750")

                if not name or not price_str:
                    continue

                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                # Only use 750ml prices for consistency
                try:
                    vol_ml = int(vol)
                except (ValueError, TypeError):
                    vol_ml = 750

                if vol_ml < 600 or vol_ml > 900:
                    continue

                if 1.0 <= price <= 50000.0:
                    norm = normalize_for_price(name)
                    if norm:
                        prices[norm] = price

            offset += batch
            if len(data) < batch:
                break
    finally:
        client.close()

    return prices


def _build_msrp_dict() -> dict[str, float]:
    """Curated MSRP prices for popular whiskeys (750ml, USD)."""
    raw = {
        # ── Bourbon ──────────────────────────────────────────────
        "Buffalo Trace": 27, "Eagle Rare 10": 35, "Blanton's Single Barrel": 65,
        "Maker's Mark": 28, "Maker's Mark 46": 35, "Maker's Mark Cask Strength": 45,
        "Woodford Reserve": 36, "Woodford Reserve Double Oaked": 55,
        "Wild Turkey 101": 26, "Wild Turkey Rare Breed": 45,
        "Bulleit Bourbon": 30, "Bulleit Rye": 30, "Bulleit 10 Year": 45,
        "Jim Beam": 18, "Jim Beam Black": 25, "Jim Beam Single Barrel": 35,
        "Knob Creek 9 Year": 36, "Knob Creek 12 Year": 60,
        "Knob Creek Single Barrel": 45, "Knob Creek Rye": 36,
        "Four Roses Single Barrel": 45, "Four Roses Small Batch": 32,
        "Four Roses Small Batch Select": 60,
        "Elijah Craig Small Batch": 30, "Elijah Craig Barrel Proof": 65,
        "Evan Williams Single Barrel": 28, "Evan Williams 1783": 16,
        "Old Forester 86": 22, "Old Forester 100": 26,
        "Old Forester 1920 Prohibition Style": 60,
        "Old Forester 1897 Bottled in Bond": 50,
        "Russell's Reserve 10 Year": 36, "Russell's Reserve Single Barrel": 60,
        "Henry McKenna 10 Year Bottled in Bond": 40,
        "Larceny": 25, "Larceny Barrel Proof": 50,
        "Old Grand-Dad 114": 30, "Old Grand-Dad Bonded": 25,
        "Very Old Barton 100": 15, "1792 Small Batch": 32,
        "1792 Bottled in Bond": 38, "1792 Full Proof": 45,
        "1792 Single Barrel": 40, "1792 Sweet Wheat": 40,
        "Angel's Envy": 50, "Angel's Envy Rye": 85,
        "Baker's 7 Year": 60, "Basil Hayden's": 42,
        "Booker's": 90, "Old Fitzgerald Bottled in Bond": 50,
        "Michter's US-1 Bourbon": 45, "Michter's US-1 Rye": 45,
        "Michter's 10 Year Bourbon": 170,
        "Weller Special Reserve": 25, "Weller Antique 107": 50,
        "Weller 12 Year": 35, "Weller Full Proof": 50,
        "Pappy Van Winkle 10 Year": 70, "Pappy Van Winkle 12 Year": 80,
        "Pappy Van Winkle 15 Year": 120, "Pappy Van Winkle 20 Year": 200,
        "Pappy Van Winkle 23 Year": 300,
        "George T. Stagg": 100, "Stagg Jr": 55,
        "Thomas H. Handy Sazerac Rye": 100,
        "William Larue Weller": 100,
        "E.H. Taylor Small Batch": 40, "E.H. Taylor Single Barrel": 70,
        "Garrison Brothers": 80, "Balcones Texas Single Malt": 35,
        "WhistlePig 10 Year": 80, "WhistlePig 12 Year Old World": 120,
        "WhistlePig 15 Year": 200, "WhistlePig 6 Year PiggyBack": 50,
        "Rabbit Hole Dareringer": 45, "Rabbit Hole Heigold": 50,
        "New Riff Single Barrel": 50, "New Riff Bottled in Bond": 40,
        "Stellum Bourbon": 55, "Barrell Bourbon": 90,
        "Bardstown Bourbon Company Fusion Series": 65,
        "Jack Daniel's Old No. 7": 28, "Jack Daniel's Single Barrel": 55,
        "Jack Daniel's Gentleman Jack": 32,
        "Jack Daniel's Single Barrel Barrel Proof": 65,
        "George Dickel No. 12": 25, "George Dickel Bottled in Bond": 40,
        "Heaven Hill Bottled in Bond 7 Year": 40,
        "Yellowstone Select": 40,
        "Smoke Wagon Uncut Unfiltered": 55,
        "Wilderness Trail Bottled in Bond": 50,
        "Old Elk": 45, "Breckenridge Bourbon": 40,
        "Chattanooga Whiskey 111": 40, "Belle Meade Reserve": 60,

        # ── Scotch Single Malt ───────────────────────────────────
        "Glenfiddich 12 Year": 45, "Glenfiddich 14 Year Bourbon Barrel Reserve": 55,
        "Glenfiddich 15 Year Solera": 65, "Glenfiddich 18 Year": 100,
        "Glenfiddich 21 Year Gran Reserva": 200,
        "Glenlivet 12 Year": 40, "Glenlivet 14 Year Cognac Cask": 55,
        "Glenlivet 18 Year": 85, "Glenlivet 21 Year": 170,
        "Macallan 12 Year Double Cask": 65, "Macallan 12 Year Sherry Oak": 75,
        "Macallan 15 Year Double Cask": 110, "Macallan 18 Year Double Cask": 350,
        "Macallan 18 Year Sherry Oak": 400, "Macallan 25 Year Sherry Oak": 2000,
        "Macallan 30 Year": 5500,
        "Ardbeg 10 Year": 55, "Ardbeg Uigeadail": 75, "Ardbeg Corryvreckan": 80,
        "Ardbeg An Oa": 60, "Ardbeg Wee Beastie 5 Year": 48,
        "Lagavulin 16 Year": 90, "Lagavulin 8 Year": 65,
        "Lagavulin Offerman Edition": 80,
        "Laphroaig 10 Year": 50, "Laphroaig Quarter Cask": 60,
        "Laphroaig 10 Year Cask Strength": 70, "Laphroaig 25 Year": 600,
        "Talisker 10 Year": 55, "Talisker 18 Year": 140,
        "Talisker Storm": 60, "Talisker Skye": 50,
        "Highland Park 12 Year": 50, "Highland Park 18 Year": 130,
        "Highland Park 25 Year": 400,
        "Dalmore 12 Year": 65, "Dalmore 15 Year": 100, "Dalmore 18 Year": 200,
        "Glenmorangie 10 Year The Original": 40, "Glenmorangie 18 Year": 100,
        "Glenmorangie Quinta Ruban 14 Year": 55,
        "Glenmorangie Nectar D'Or 16 Year": 70,
        "Glenmorangie Lasanta 12 Year": 50,
        "Balvenie 12 Year DoubleWood": 60, "Balvenie 14 Year Caribbean Cask": 75,
        "Balvenie 17 Year DoubleWood": 160, "Balvenie 21 Year Portwood": 250,
        "Balvenie 25 Year": 550, "Balvenie 30 Year": 1000,
        "Oban 14 Year": 80, "Oban 18 Year": 130,
        "Aberlour 12 Year": 50, "Aberlour 16 Year": 80,
        "Aberlour A'bunadh": 90,
        "Springbank 10 Year": 70, "Springbank 15 Year": 130,
        "Springbank 18 Year": 250,
        "Bunnahabhain 12 Year": 55, "Bunnahabhain 18 Year": 120,
        "Bowmore 12 Year": 50, "Bowmore 15 Year": 70, "Bowmore 18 Year": 110,
        "Caol Ila 12 Year": 60, "Caol Ila 18 Year": 130,
        "Bruichladdich The Classic Laddie": 50,
        "Bruichladdich Port Charlotte 10 Year": 65,
        "Bruichladdich Octomore": 200,
        "Benromach 10 Year": 45, "Benromach 15 Year": 70,
        "Clynelish 14 Year": 65,
        "Cragganmore 12 Year": 45,
        "Craigellachie 13 Year": 50, "Craigellachie 17 Year": 100,
        "Glen Scotia 15 Year": 70,
        "Kilchoman Machir Bay": 55, "Kilchoman Sanaig": 65,
        "Tobermory 12 Year": 55,
        "Edradour 10 Year": 50,
        "Glen Grant 12 Year": 35, "Glen Grant 18 Year": 100,
        "Tomatin 12 Year": 35, "Tomatin 18 Year": 80,
        "Deanston 12 Year": 50, "Deanston 18 Year": 100,
        "Auchentoshan 12 Year": 35, "Auchentoshan Three Wood": 60,
        "Knockando 12 Year": 40,
        "Singleton of Glendullan 12 Year": 35,

        # ── Blended Scotch ───────────────────────────────────────
        "Johnnie Walker Black Label": 35, "Johnnie Walker Blue Label": 200,
        "Johnnie Walker Green Label 15 Year": 55,
        "Johnnie Walker Gold Label Reserve": 75,
        "Johnnie Walker Double Black": 40,
        "Chivas Regal 12 Year": 30, "Chivas Regal 18 Year": 70,
        "Dewar's 12 Year": 28, "Dewar's 15 Year": 35, "Dewar's 18 Year": 55,
        "Monkey Shoulder": 30,
        "Compass Box Great King Street": 35,
        "Compass Box Peat Monster": 50,
        "Famous Grouse": 22, "Cutty Sark": 18,
        "Royal Salute 21 Year": 200,

        # ── Irish ────────────────────────────────────────────────
        "Jameson": 28, "Jameson Black Barrel": 35, "Jameson 18 Year": 100,
        "Jameson Caskmates Stout Edition": 35,
        "Redbreast 12 Year": 65, "Redbreast 15 Year": 90,
        "Redbreast 12 Year Cask Strength": 85,
        "Green Spot": 55, "Yellow Spot 12 Year": 90,
        "Bushmills 10 Year": 35, "Bushmills 16 Year": 80,
        "Bushmills 21 Year": 200, "Bushmills Black Bush": 35,
        "Tullamore Dew": 25, "Tullamore Dew 12 Year": 40,
        "Powers Gold Label": 28, "Powers John's Lane 12 Year": 60,
        "Teeling Single Grain": 35, "Teeling Single Malt": 45,
        "Teeling Small Batch": 30,
        "Proper Twelve": 22, "Connemara Peated": 35,
        "Tyrconnell": 30, "Knappogue Castle 12 Year": 35,
        "Writers' Tears Copper Pot": 35,
        "Midleton Very Rare": 200,

        # ── Japanese ─────────────────────────────────────────────
        "Suntory Toki": 35, "Suntory Hibiki Harmony": 70,
        "Suntory Hibiki 17 Year": 400, "Suntory Hibiki 21 Year": 800,
        "Yamazaki 12 Year": 150, "Yamazaki 18 Year": 500,
        "Hakushu 12 Year": 130, "Hakushu 18 Year": 450,
        "Nikka From The Barrel": 65, "Nikka Coffey Grain": 65,
        "Nikka Coffey Malt": 70, "Nikka Yoichi Single Malt": 80,
        "Nikka Miyagikyo Single Malt": 75,
        "Taketsuru Pure Malt": 70,
        "Iwai Tradition": 35, "Iwai 45": 50,
        "Akashi White Oak": 30, "Togouchi Premium": 40,

        # ── Rye ──────────────────────────────────────────────────
        "Rittenhouse Rye Bottled in Bond": 28,
        "Sazerac Rye": 30, "High West Double Rye": 35,
        "High West Rendezvous Rye": 55,
        "Pikesville Rye 110": 50, "Old Overholt Bonded": 18,
        "Templeton Rye 4 Year": 30, "Templeton Rye 6 Year": 40,
        "Redemption Rye": 25, "Few Rye": 45,

        # ── Canadian ─────────────────────────────────────────────
        "Crown Royal": 28, "Crown Royal XR": 130,
        "Crown Royal Northern Harvest Rye": 30,
        "Canadian Club": 14, "Canadian Club 12 Year": 25,
        "Lot No. 40": 35, "Pike Creek 10 Year": 40,
        "Alberta Premium Cask Strength": 60,
        "Forty Creek Barrel Select": 22,
    }

    msrp = {}
    for name, price in raw.items():
        norm = normalize_for_price(name)
        if norm:
            msrp[norm] = float(price)
    return msrp


# ── Phase 3: Statistical Estimation ──────────────────────────────────────

def phase3_statistical(db: Session, dry_run: bool = False) -> dict:
    """
    Estimate prices for remaining unpriced whiskeys using statistical models
    based on category, age, ABV, and distillery.
    """
    log.info("=== Phase 3: Statistical Price Estimation ===")

    # Load all priced whiskeys (including newly enriched from Phase 1/2)
    priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
    ).all()
    log.info("Building models from %d priced whiskeys", len(priced))

    # ── Build per-category models ────────────────────────────────────
    category_data: dict[str, list[dict]] = defaultdict(list)
    distillery_prices: dict[str, list[float]] = defaultdict(list)

    for w in priced:
        cat = w.category or "world"
        category_data[cat].append({
            "age": w.age,
            "abv": w.abv,
            "price": w.price_usd,
            "distillery": (w.distillery or "").lower().strip(),
        })
        dist = (w.distillery or "").lower().strip()
        if dist:
            distillery_prices[dist].append(w.price_usd)

    # Compute distillery multipliers (relative to category median)
    category_medians = {}
    for cat, items in category_data.items():
        prices = [x["price"] for x in items]
        category_medians[cat] = statistics.median(prices) if prices else 50.0

    MAX_DISTILLERY_MULT = 4.0
    MIN_DISTILLERY_MULT = 0.25

    distillery_mults = {}
    for dist, prices in distillery_prices.items():
        if len(prices) >= 3:
            dist_median = statistics.median(prices)
            # Get the category of most entries for this distillery
            cats = defaultdict(int)
            for w in priced:
                if (w.distillery or "").lower().strip() == dist:
                    cats[w.category or "world"] += 1
            primary_cat = max(cats, key=cats.get) if cats else "world"
            cat_med = category_medians.get(primary_cat, 50.0)
            if cat_med > 0:
                raw_mult = dist_median / cat_med
                # Cap to prevent runaway multipliers (e.g. Brora at 700x)
                distillery_mults[dist] = max(MIN_DISTILLERY_MULT, min(raw_mult, MAX_DISTILLERY_MULT))

    # Build age curves per category
    age_curves = {}
    for cat, items in category_data.items():
        aged = [(x["age"], x["price"]) for x in items if x["age"] and x["age"] > 0]
        if len(aged) >= 10:
            ages = np.array([a for a, _ in aged], dtype=float)
            prices = np.array([p for _, p in aged], dtype=float)
            # Fit log-linear: price = a * ln(age) + b
            log_ages = np.log(ages + 1)
            try:
                coeffs = np.polyfit(log_ages, prices, 1)
                age_curves[cat] = coeffs  # (slope, intercept)
            except Exception:
                pass

    # ── Estimate prices for remaining unpriced whiskeys ──────────────
    already_enriched = set(
        r[0] for r in db.query(PriceEnrichmentLog.whiskey_id).all()
    )

    unpriced = db.query(Whiskey).filter(
        or_(Whiskey.price_usd.is_(None), Whiskey.price_usd == 0),
    ).all()

    remaining = [w for w in unpriced if w.id not in already_enriched]
    log.info("Estimating prices for %d remaining whiskeys", len(remaining))

    stats = {"statistical": 0}
    updates = []

    for i, w in enumerate(remaining):
        if i % 5000 == 0 and i > 0:
            log.info("  Phase 3 progress: %d / %d", i, len(remaining))

        cat = w.category or "world"
        base = category_medians.get(cat, 50.0)
        confidence = 0.30

        # Age adjustment
        if w.age and cat in age_curves:
            slope, intercept = age_curves[cat]
            predicted = slope * np.log(w.age + 1) + intercept
            if predicted > 0:
                base = predicted
                confidence += 0.10

        # ABV premium (cask strength) — dampened to avoid over-inflation
        if w.abv and w.abv > 50.0:
            base *= 1.0 + (w.abv - 46.0) * 0.008
            confidence += 0.05

        # Distillery multiplier
        dist = (w.distillery or "").lower().strip()
        if dist in distillery_mults:
            base *= distillery_mults[dist]
            confidence += 0.15

        # Per-category cap instead of flat $50k — prevents absurd estimates
        _CAT_CAPS = {
            "bourbon": 500, "rye": 400, "canadian": 200, "irish": 400,
            "japanese": 1500, "scotch": 800, "single malt": 800,
            "blended": 300, "world": 400, "whiskey": 300, "tennessee": 300,
        }
        _base_cap = _CAT_CAPS.get(cat, 400)
        if w.age and w.age >= 25:
            _base_cap *= 3.0
        elif w.age and w.age >= 18:
            _base_cap *= 2.0
        elif w.age and w.age >= 15:
            _base_cap *= 1.5
        _cap = min(_base_cap, 5000.0)
        price = max(10.0, min(base, _cap))

        detail_parts = [f"cat={cat}"]
        if w.age:
            detail_parts.append(f"age={w.age}")
        if dist in distillery_mults:
            detail_parts.append(f"dist_mult={distillery_mults[dist]:.2f}")
        detail = "statistical: " + ", ".join(detail_parts)

        updates.append((
            w.id, round(price, 2), "statistical", min(confidence, 1.0), detail,
        ))
        stats["statistical"] += 1

    if not dry_run:
        _apply_updates(db, updates)

    log.info("Phase 3 results: estimated=%d", stats["statistical"])
    return stats


# ── Phase 4: Audit & Verification ────────────────────────────────────────

def phase4_audit(db: Session) -> dict:
    """
    Verify price accuracy via cross-validation and outlier detection.
    """
    log.info("=== Phase 4: Audit & Verification ===")

    # ── Cross-validation ─────────────────────────────────────────────
    priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
    ).all()

    # Only cross-validate with originally-priced whiskeys (not enriched)
    enriched_ids = set(
        r[0] for r in db.query(PriceEnrichmentLog.whiskey_id).all()
    )
    original_priced = [w for w in priced if w.id not in enriched_ids]

    if len(original_priced) < 100:
        log.warning("Too few original prices for cross-validation (%d)", len(original_priced))
        cv_results = {"error": "insufficient data"}
    else:
        random.seed(42)
        random.shuffle(original_priced)
        holdout_size = len(original_priced) // 5
        holdout = original_priced[:holdout_size]
        training = original_priced[holdout_size:]

        # Build simple model from training set
        cat_medians = defaultdict(list)
        for w in training:
            cat_medians[w.category or "world"].append(w.price_usd)
        cat_medians = {k: statistics.median(v) for k, v in cat_medians.items()}

        errors = []
        for w in holdout:
            estimated = cat_medians.get(w.category or "world", 50.0)
            pct_error = abs(estimated - w.price_usd) / w.price_usd if w.price_usd > 0 else 0
            errors.append(pct_error)

        cv_results = {
            "holdout_size": holdout_size,
            "training_size": len(training),
            "mean_absolute_pct_error": round(float(np.mean(errors)), 4),
            "median_absolute_pct_error": round(float(np.median(errors)), 4),
            "p90_pct_error": round(float(np.percentile(errors, 90)), 4),
        }
        log.info(
            "Cross-validation: MAE=%.1f%%, Median=%.1f%%, P90=%.1f%%",
            cv_results["mean_absolute_pct_error"] * 100,
            cv_results["median_absolute_pct_error"] * 100,
            cv_results["p90_pct_error"] * 100,
        )

    # ── Outlier detection ────────────────────────────────────────────
    # Build category+age percentiles from all priced entries
    group_prices: dict[tuple, list[float]] = defaultdict(list)
    for w in priced:
        bucket = age_bucket(w.age)
        group_prices[(w.category or "world", bucket)].append(w.price_usd)

    percentiles = {}
    for key, prices in group_prices.items():
        if len(prices) >= 5:
            percentiles[key] = {
                "p5": float(np.percentile(prices, 5)),
                "p25": float(np.percentile(prices, 25)),
                "p50": float(np.percentile(prices, 50)),
                "p75": float(np.percentile(prices, 75)),
                "p95": float(np.percentile(prices, 95)),
                "count": len(prices),
            }

    outliers = []
    enriched = db.query(PriceEnrichmentLog).all()
    for log_entry in enriched:
        w = db.query(Whiskey).get(log_entry.whiskey_id)
        if not w or not w.price_usd:
            continue
        bucket = age_bucket(w.age)
        key = (w.category or "world", bucket)
        if key not in percentiles:
            continue
        p = percentiles[key]
        if w.price_usd < p["p5"] * 0.5:
            outliers.append({
                "id": w.id, "name": w.name, "price": w.price_usd,
                "method": log_entry.method, "reason": "suspiciously_low",
                "expected_range": f"${p['p5']:.0f}-${p['p95']:.0f}",
            })
        elif w.price_usd > p["p95"] * 2.0:
            outliers.append({
                "id": w.id, "name": w.name, "price": w.price_usd,
                "method": log_entry.method, "reason": "suspiciously_high",
                "expected_range": f"${p['p5']:.0f}-${p['p95']:.0f}",
            })

    log.info("Outlier detection: %d suspicious prices flagged", len(outliers))

    # ── Summary stats ────────────────────────────────────────────────
    method_counts = defaultdict(int)
    for entry in enriched:
        method_counts[entry.method] += 1

    total_priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None), Whiskey.price_usd > 0,
    ).count()
    total_whiskeys = db.query(Whiskey).count()

    report = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "total_whiskeys": total_whiskeys,
        "total_priced": total_priced,
        "coverage_pct": round(total_priced / total_whiskeys * 100, 1) if total_whiskeys > 0 else 0,
        "enriched_by_method": dict(method_counts),
        "cross_validation": cv_results,
        "outliers_count": len(outliers),
        "outliers_sample": outliers[:50],
    }

    # Write report
    report_path = Path(__file__).parent / "price_audit_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    log.info("Audit report written to %s", report_path)

    return report


# ── Database update helper ───────────────────────────────────────────────

def _apply_updates(db: Session, updates: list[tuple]):
    """
    Apply price updates to the database.
    Each update: (whiskey_id, price, method, confidence, source_detail)
    """
    if not updates:
        return

    # Methods where the price is an estimate (not a real retail price)
    ESTIMATED_METHODS = {"cross_ref", "statistical"}

    batch_size = 200
    applied = 0

    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        for whiskey_id, price, method, confidence, source_detail in batch:
            is_estimated = method in ESTIMATED_METHODS
            # Update whiskey price
            db.query(Whiskey).filter(Whiskey.id == whiskey_id).update(
                {"price_usd": price, "price_is_estimated": is_estimated},
                synchronize_session=False,
            )
            # Upsert enrichment log
            existing = db.query(PriceEnrichmentLog).filter(
                PriceEnrichmentLog.whiskey_id == whiskey_id,
            ).first()
            if existing:
                existing.method = method
                existing.confidence = confidence
                existing.source_detail = source_detail
                existing.enriched_at = datetime.now(timezone.utc)
            else:
                db.add(PriceEnrichmentLog(
                    whiskey_id=whiskey_id,
                    method=method,
                    confidence=confidence,
                    source_detail=source_detail,
                    original_price=None,
                ))
            applied += 1
        db.commit()

    log.info("Applied %d price updates to database", applied)


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Enrich whiskey prices")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], help="Run specific phase")
    parser.add_argument("--audit", action="store_true", help="Run audit only")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--limit", type=int, default=0, help="Max items for phase 2 web lookup")
    args = parser.parse_args()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    progress = load_progress() if args.resume else dict(PROGRESS_DEFAULTS)

    try:
        if args.audit:
            report = phase4_audit(db)
            print(json.dumps(report, indent=2, default=str))
            return

        run_all = args.phase is None

        # Phase 1
        if run_all or args.phase == 1:
            if not (args.resume and progress.get("phase1_done")):
                stats = phase1_cross_reference(db, dry_run=args.dry_run)
                progress["phase1_done"] = True
                for k, v in stats.items():
                    progress["by_method"][k] = progress["by_method"].get(k, 0) + v
                progress["total_enriched"] += sum(stats.values())
                save_progress(progress)
            else:
                log.info("Phase 1 already complete, skipping.")

        # Phase 2
        if run_all or args.phase == 2:
            if not (args.resume and progress.get("phase2_done")):
                resume_idx = progress.get("phase2_index", 0) if args.resume else 0
                stats = phase2_web_lookup(
                    db, dry_run=args.dry_run, limit=args.limit,
                    resume_index=resume_idx,
                )
                progress["phase2_done"] = True
                for k, v in stats.items():
                    if k in progress["by_method"]:
                        progress["by_method"][k] += v
                progress["total_enriched"] += stats.get("web_lookup", 0)
                save_progress(progress)
            else:
                log.info("Phase 2 already complete, skipping.")

        # Phase 3
        if run_all or args.phase == 3:
            if not (args.resume and progress.get("phase3_done")):
                stats = phase3_statistical(db, dry_run=args.dry_run)
                progress["phase3_done"] = True
                for k, v in stats.items():
                    if k in progress["by_method"]:
                        progress["by_method"][k] += v
                progress["total_enriched"] += stats.get("statistical", 0)
                save_progress(progress)
            else:
                log.info("Phase 3 already complete, skipping.")

        # Always run audit at the end
        if run_all and not args.dry_run:
            phase4_audit(db)

        log.info("=== Done! Total enriched: %d ===", progress["total_enriched"])
        log.info("By method: %s", json.dumps(progress["by_method"]))

    finally:
        db.close()


if __name__ == "__main__":
    main()
