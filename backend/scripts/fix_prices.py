"""
Fix inflated and incorrect whiskey price data in SipSense database.

Root cause: The statistical estimation model in enrich_prices.py uses an
unbounded distillery multiplier that compounds the price bias of
rare/collectible bottlings (e.g. Brora at $40k avg) into every bottle from
that distillery.  78.5% of prices are estimated, with an overall avg of $366
(should be ~$50-70).

This script fixes prices in 6 phases:
  Phase 0: Backup & baseline report
  Phase 1: Build trusted-price set (read-only)
  Phase 2: Fix category misclassifications
  Phase 3: Null out known bad exact/fuzzy matches
  Phase 4: Recalculate ALL estimated prices with improved model
  Phase 5: Re-match nulled bottles with guardrails
  Phase 6: After report & diff

Usage:
  cd backend
  python -m scripts.fix_prices                  # full run
  python -m scripts.fix_prices --dry-run        # preview changes
  python -m scripts.fix_prices --report-only    # just show current stats
"""

import argparse
import json
import logging
import re
import shutil
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Allow imports from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Whiskey, PriceEnrichmentLog

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "sipsense.db"
REPORT_PATH = Path(__file__).parent / "price_fix_report.json"

# ── Reuse helpers from enrich_prices ────────────────────────────────────

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
    s = re.sub(
        r"(\d+)\s*(?:year[s]?\s*old|year[s]?|yr[s]?\s*old|yr[s]?|yo|y\.o\.?)",
        r"\1yo", s, flags=re.I,
    )
    for suffix in _SUFFIXES:
        s = s.replace(suffix, "")
    s = re.sub(r"cask\s*(?:#|no\.?)\s*\d+", "", s)
    s = re.sub(r"batch\s*(?:no\.?)?\s*\d+", "", s)
    s = re.sub(r"\b(19|20)\d{2}\b", "", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", s, flags=re.I)
    s = re.sub(r"\bsmws\s*\d+\.\d+\b", "", s, flags=re.I)
    s = s.replace("'", "").replace("\u2019", "").replace("`", "")
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip("-").strip()
    return s


def age_bucket(age) -> str:
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


# ── Per-category price caps for estimates ───────────────────────────────

CATEGORY_BASE_CAPS = {
    "bourbon":      500,
    "rye":          400,
    "canadian":     200,
    "irish":        400,
    "japanese":     1500,
    "scotch":       800,
    "single malt":  800,
    "blended":      300,
    "world":        400,
    "whiskey":      300,
    "tennessee":    300,
    "single grain": 300,
    "corn":         100,
    "indian":       400,
}

HARD_ESTIMATE_CAP = 2000.0  # No statistical estimate above this — anything higher needs hand-verification


def get_price_cap(category: str, age: int | None) -> float:
    """Get the maximum allowed estimated price for a category + age."""
    base_cap = CATEGORY_BASE_CAPS.get(category, 400)
    if age and age >= 25:
        base_cap *= 3.0
    elif age and age >= 18:
        base_cap *= 2.0
    elif age and age >= 15:
        base_cap *= 1.5
    return min(base_cap, HARD_ESTIMATE_CAP)


# ── MSRP reference dictionary ──────────────────────────────────────────

def _build_msrp_dict() -> dict[str, float]:
    """Curated prices for popular whiskeys (750ml, USD).

    Pricing philosophy:
      - Available bottles → current US retail
      - Allocated/hard-to-find → secondary market price
      - Discontinued/collector → auction/collector market value
    """
    raw = {
        # Bourbon — allocated (secondary market)
        "Pappy Van Winkle 15 Year": 1200, "Pappy Van Winkle 20 Year": 1800,
        "Pappy Van Winkle 23 Year": 2800,
        "George T. Stagg": 1800, "Stagg Jr": 200, "Stagg": 200,
        "William Larue Weller": 1500, "Eagle Rare 17": 400,
        "Weller Special Reserve": 40, "Weller Antique 107": 100,
        "Weller 12 Year": 150, "Weller Full Proof": 400,
        "Blanton's Single Barrel": 100, "Blanton's Original": 100,
        # Bourbon — standard (current retail)
        "Buffalo Trace": 28, "Eagle Rare 10": 45,
        "Maker's Mark": 32, "Maker's Mark 46": 40, "Maker's Mark Cask Strength": 45,
        "Woodford Reserve": 40, "Woodford Reserve Double Oaked": 60,
        "Wild Turkey 101": 28, "Wild Turkey Rare Breed": 48,
        "Bulleit Bourbon": 30, "Bulleit Rye": 30, "Bulleit 10 Year": 50,
        "Jim Beam": 18, "Jim Beam Black": 25, "Jim Beam Single Barrel": 35,
        "Knob Creek 9 Year": 36, "Knob Creek 12 Year": 65,
        "Four Roses Single Barrel": 50, "Four Roses Small Batch": 35,
        "Elijah Craig Small Batch": 32, "Elijah Craig Barrel Proof": 75,
        "Evan Williams Single Barrel": 28, "Evan Williams 1783": 16,
        "Old Forester 86": 25, "Old Forester 100": 26,
        "Old Forester 1920 Prohibition Style": 60,
        "Jack Daniel's Old No. 7": 28, "Jack Daniel's Single Barrel": 55,
        "George Dickel No. 12": 25, "George Dickel Bottled in Bond": 40,
        "Heaven Hill Bottled in Bond 7 Year": 30,
        "WhistlePig 10 Year": 80, "WhistlePig 12 Year Old World": 140,
        "Angel's Envy": 55, "Booker's": 100,
        "Michter's US-1 Bourbon": 47, "Michter's US-1 Rye": 47,
        # Scotch Single Malt
        "Glenfiddich 12 Year": 55, "Glenfiddich 15 Year Solera": 60,
        "Glenfiddich 18 Year": 85, "Glenfiddich 21 Year Gran Reserva": 210,
        "Glenlivet 12 Year": 50, "Glenlivet 18 Year": 100,
        "Macallan 12 Year Double Cask": 65, "Macallan 12 Year Sherry Oak": 95,
        "Macallan 18 Year Sherry Oak": 420, "Macallan 18 Year Double Cask": 370,
        "Macallan 25 Year Sherry Oak": 2500, "Macallan 30 Year": 5500,
        "Ardbeg 10 Year": 55, "Ardbeg Uigeadail": 80, "Ardbeg Corryvreckan": 90,
        "Lagavulin 16 Year": 90, "Lagavulin 8 Year": 65,
        "Laphroaig 10 Year": 50, "Laphroaig Quarter Cask": 60,
        "Talisker 10 Year": 75, "Talisker 18 Year": 140,
        "Highland Park 12 Year": 55, "Highland Park 18 Year": 170,
        "Dalmore 12 Year": 73, "Dalmore 15 Year": 145, "Dalmore 18 Year": 360,
        "Glenmorangie 10 Year The Original": 45, "Glenmorangie 18 Year": 100,
        "Balvenie 12 Year DoubleWood": 66, "Balvenie 14 Year Caribbean Cask": 85,
        "Balvenie 21 Year Portwood": 335, "Balvenie 30 Year": 1000,
        "Oban 14 Year": 90, "Oban 18 Year": 170,
        "Aberlour 12 Year": 50, "Aberlour A'bunadh": 90,
        "Springbank 10 Year": 140, "Springbank 15 Year": 300,
        "Bunnahabhain 12 Year": 55, "Bunnahabhain 18 Year": 120,
        "Bowmore 12 Year": 45, "Bowmore 15 Year": 60, "Bowmore 18 Year": 90,
        "Caol Ila 12 Year": 60, "Caol Ila 18 Year": 130,
        "Bruichladdich The Classic Laddie": 50,
        "Benromach 10 Year": 45, "Benromach 15 Year": 70,
        "Clynelish 14 Year": 65, "Cragganmore 12 Year": 45,
        "Glen Grant 12 Year": 35, "Glen Grant 18 Year": 100,
        "Tomatin 12 Year": 35, "Auchentoshan 12 Year": 35,
        "GlenDronach 12 Year": 55, "GlenDronach 18 Year": 150,
        "Glenfarclas 12 Year": 50, "Glenfarclas 25 Year": 250,
        # Blended Scotch
        "Johnnie Walker Black Label": 35, "Johnnie Walker Blue Label": 200,
        "Johnnie Walker Green Label 15 Year": 55,
        "Chivas Regal 12 Year": 30, "Chivas Regal 18 Year": 70,
        "Dewar's 12 Year": 28, "Dewar's 18 Year": 55,
        "Monkey Shoulder": 33, "Famous Grouse": 22,
        "Royal Salute 21 Year": 200,
        # Irish
        "Jameson": 32, "Jameson Black Barrel": 40, "Jameson 18 Year": 100,
        "Redbreast 12 Year": 70, "Redbreast 15 Year": 130,
        "Green Spot": 60, "Yellow Spot 12 Year": 125,
        "Bushmills 10 Year": 35, "Bushmills 16 Year": 80,
        "Bushmills 21 Year": 150, "Tullamore Dew": 25,
        "Teeling Small Batch": 30, "Proper Twelve": 22,
        "Midleton Very Rare": 200, "Knappogue Castle 12 Year": 35,
        # Japanese (updated 2026 — post-Suntory April 2024 price hike)
        "Suntory Toki": 35, "Suntory Hibiki Harmony": 80,
        "Suntory Hibiki 17 Year": 900, "Suntory Hibiki 21 Year": 1000,
        "Yamazaki 12 Year": 190, "Yamazaki 18 Year": 900,
        "Hakushu 12 Year": 195, "Hakushu 18 Year": 800,
        "Nikka From The Barrel": 70, "Nikka Coffey Grain": 70,
        "Akashi White Oak": 30,
        # Rye
        "Rittenhouse Rye Bottled in Bond": 30, "Sazerac Rye": 30,
        "High West Double Rye": 45, "Pikesville Rye 110": 50,
        "Colonel E.H. Taylor Rye": 100,
        # Canadian
        "Crown Royal": 28, "Crown Royal XR": 130,
        "Canadian Club": 14, "Lot No. 40": 35,
        "Forty Creek Barrel Select": 22,
    }
    msrp = {}
    for name, price in raw.items():
        norm = normalize_for_price(name)
        if norm:
            msrp[norm] = float(price)
    return msrp


# ── Trusted sources ────────────────────────────────────────────────────

TRUSTED_SOURCES = {"iowa_liquor", "oregon_olcc", "montgomery_md", "vinmonopolet"}


# ── Phase 0: Backup & Baseline ─────────────────────────────────────────

def backup_db() -> Path | None:
    if not DB_PATH.exists():
        log.info("No SQLite DB at %s (likely PostgreSQL) — skipping file backup", DB_PATH)
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"sipsense.db.backup_pricefix_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    log.info("Backup created: %s", backup_path)
    return backup_path


def generate_stats(db: Session) -> dict:
    """Generate price statistics snapshot."""
    total = db.query(Whiskey).count()
    priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None), Whiskey.price_usd > 0,
    ).all()

    prices = [w.price_usd for w in priced]
    est_prices = [w.price_usd for w in priced if w.price_is_estimated]
    real_prices = [w.price_usd for w in priced if not w.price_is_estimated]

    # Per-category stats
    cat_stats = defaultdict(lambda: {"count": 0, "prices": [], "estimated": 0})
    for w in priced:
        cat = w.category or "world"
        cat_stats[cat]["count"] += 1
        cat_stats[cat]["prices"].append(w.price_usd)
        if w.price_is_estimated:
            cat_stats[cat]["estimated"] += 1

    cat_summary = {}
    for cat, data in cat_stats.items():
        cat_summary[cat] = {
            "count": data["count"],
            "avg": round(statistics.mean(data["prices"]), 2) if data["prices"] else 0,
            "median": round(statistics.median(data["prices"]), 2) if data["prices"] else 0,
            "estimated_count": data["estimated"],
        }

    # Worst distilleries (by estimated avg price)
    dist_stats = defaultdict(list)
    for w in priced:
        if w.price_is_estimated:
            dist = (w.distillery or "Unknown").strip()
            dist_stats[dist].append(w.price_usd)

    worst = sorted(
        [(d, len(ps), round(statistics.mean(ps), 2)) for d, ps in dist_stats.items() if len(ps) >= 10],
        key=lambda x: x[2], reverse=True,
    )[:20]

    return {
        "total_whiskeys": total,
        "total_priced": len(priced),
        "avg_price": round(statistics.mean(prices), 2) if prices else 0,
        "median_price": round(statistics.median(prices), 2) if prices else 0,
        "estimated_count": len(est_prices),
        "estimated_avg": round(statistics.mean(est_prices), 2) if est_prices else 0,
        "real_count": len(real_prices),
        "real_avg": round(statistics.mean(real_prices), 2) if real_prices else 0,
        "over_1000_estimated": sum(1 for p in est_prices if p > 1000),
        "over_5000_estimated": sum(1 for p in est_prices if p > 5000),
        "over_10000_estimated": sum(1 for p in est_prices if p > 10000),
        "by_category": cat_summary,
        "worst_distilleries": [
            {"distillery": d, "count": c, "avg_price": a} for d, c, a in worst
        ],
    }


# ── Phase 1: Build Trusted Set ─────────────────────────────────────────

def phase1_trusted_ids(db: Session) -> set[int]:
    """Collect IDs of whiskeys with reliable prices that must not be changed."""
    log.info("=== Phase 1: Building trusted price set ===")

    trusted = set()

    # Source-based trust (government retail prices)
    for source in TRUSTED_SOURCES:
        ids = db.query(Whiskey.id).filter(
            Whiskey.source == source,
            Whiskey.price_usd.isnot(None),
            Whiskey.price_usd > 0,
            Whiskey.price_is_estimated == False,
        ).all()
        cnt = len(ids)
        trusted.update(r[0] for r in ids)
        log.info("  Trusted from %s: %d", source, cnt)

    # Also trust web_lookup enrichments (MSRP dictionary matches)
    web_ids = db.query(PriceEnrichmentLog.whiskey_id).filter(
        PriceEnrichmentLog.method == "web_lookup",
    ).all()
    trusted.update(r[0] for r in web_ids)
    log.info("  Trusted from web_lookup: %d", len(web_ids))

    # Trust manual source entries that aren't estimated
    manual_ids = db.query(Whiskey.id).filter(
        Whiskey.source == "manual",
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
        Whiskey.price_is_estimated == False,
    ).all()
    trusted.update(r[0] for r in manual_ids)
    log.info("  Trusted from manual: %d", len(manual_ids))

    log.info("  Total trusted: %d", len(trusted))
    return trusted


# ── Phase 2: Fix Category Misclassifications ───────────────────────────

def phase2_fix_categories(db: Session, dry_run: bool) -> int:
    """Fix whiskeys in wrong categories that affect price estimation."""
    log.info("=== Phase 2: Fixing category misclassifications ===")

    fixes = [
        # (name_like, current_category, new_category, new_region)
        ("Black Velvet%", "scotch", "canadian", None),
        ("Crown Royal%", "scotch", "canadian", "Canada"),
        ("Canadian Club%", "scotch", "canadian", "Canada"),
        ("Fireball%", "scotch", "canadian", "Canada"),
        ("Bushmills%", "scotch", "irish", "Ireland"),
        ("Tullamore%", "scotch", "irish", "Ireland"),
        ("Proper Twelve%", "scotch", "irish", "Ireland"),
        ("Connemara%", "scotch", "irish", "Ireland"),
        ("Southern Comfort%", "scotch", "whiskey", "USA"),
    ]

    total = 0
    for name_like, cur_cat, new_cat, new_region in fixes:
        matches = db.query(Whiskey).filter(
            Whiskey.name.like(name_like),
            Whiskey.category == cur_cat,
        ).all()
        for w in matches:
            if not dry_run:
                w.category = new_cat
                if new_region:
                    w.region = new_region
            total += 1
            log.info("  Category fix: '%s' %s -> %s", w.name, cur_cat, new_cat)

    if not dry_run and total > 0:
        db.commit()

    log.info("Phase 2: fixed %d category misclassifications", total)
    return total


# ── Phase 3: Null Out Bad Matches ──────────────────────────────────────

def phase3_null_bad_matches(db: Session, trusted_ids: set, dry_run: bool) -> int:
    """Null out prices from bad exact/fuzzy matches."""
    log.info("=== Phase 3: Nulling bad exact/fuzzy matches ===")

    msrp = _build_msrp_dict()
    nulled = 0

    # Get all exact_match and fuzzy_match enrichment log entries
    match_logs = db.query(PriceEnrichmentLog).filter(
        PriceEnrichmentLog.method.in_(["exact_match", "fuzzy_match"]),
    ).all()

    for log_entry in match_logs:
        if log_entry.whiskey_id in trusted_ids:
            continue
        w = db.query(Whiskey).get(log_entry.whiskey_id)
        if not w or not w.price_usd:
            continue

        norm = normalize_for_price(w.name)
        if not norm:
            continue

        # Check against MSRP reference
        if norm in msrp:
            ref_price = msrp[norm]
            if ref_price > 0:
                ratio = w.price_usd / ref_price
                if ratio > 5.0 or ratio < 0.2:
                    log.info(
                        "  Bad match: '%s' price=$%.2f, MSRP ref=$%.2f (ratio=%.1fx) [%s]",
                        w.name, w.price_usd, ref_price, ratio, log_entry.method,
                    )
                    if not dry_run:
                        w.price_usd = None
                        w.price_is_estimated = False
                        db.delete(log_entry)
                    nulled += 1
                    continue

        # Also catch obvious outliers: any NAS bottle over $2000 from matching
        if w.age is None and w.price_usd > 2000:
            log.info(
                "  Bad NAS match: '%s' price=$%.2f [%s]",
                w.name, w.price_usd, log_entry.method,
            )
            if not dry_run:
                w.price_usd = None
                w.price_is_estimated = False
                db.delete(log_entry)
            nulled += 1
            continue

        # Cap check: if match price exceeds category cap by 3x, it's bad
        cap = get_price_cap(w.category, w.age)
        if w.price_usd > cap * 3:
            log.info(
                "  Over-cap match: '%s' price=$%.2f, cap=$%.2f [%s]",
                w.name, w.price_usd, cap, log_entry.method,
            )
            if not dry_run:
                w.price_usd = None
                w.price_is_estimated = False
                db.delete(log_entry)
            nulled += 1

    # Also null the specific outliers from the audit report
    audit_path = Path(__file__).parent / "price_audit_report.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        for outlier in audit.get("outliers_sample", []):
            wid = outlier["id"]
            if wid in trusted_ids:
                continue
            w = db.query(Whiskey).get(wid)
            if not w or w.price_usd is None:
                continue
            # Only null truly bad ones (>5x or <0.2x expected range)
            reason = outlier.get("reason", "")
            if reason == "suspiciously_high" and w.price_is_estimated:
                log.info(
                    "  Audit outlier: '%s' price=$%.2f expected=%s",
                    w.name, w.price_usd, outlier.get("expected_range", "?"),
                )
                if not dry_run:
                    w.price_usd = None
                    w.price_is_estimated = False
                    db.query(PriceEnrichmentLog).filter(
                        PriceEnrichmentLog.whiskey_id == wid,
                    ).delete()
                nulled += 1

    if not dry_run and nulled > 0:
        db.commit()

    log.info("Phase 3: nulled %d bad matches", nulled)
    return nulled


# ── Phase 4: Recalculate All Estimated Prices ─────────────────────────

MAX_DISTILLERY_MULT = 2.5
MIN_DISTILLERY_MULT = 0.25


def phase4_recalculate(db: Session, trusted_ids: set, dry_run: bool) -> int:
    """Recalculate all estimated prices with the fixed model."""
    log.info("=== Phase 4: Recalculating estimated prices ===")

    # KEY FIX: Train ONLY on real (non-estimated) prices
    training = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
        Whiskey.price_is_estimated == False,
    ).all()
    log.info("Training model from %d real-priced whiskeys only", len(training))

    # Build per-category medians from REAL prices
    category_data: dict[str, list[dict]] = defaultdict(list)
    distillery_prices: dict[str, list[float]] = defaultdict(list)

    for w in training:
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

    category_medians = {}
    for cat, items in category_data.items():
        prices = [x["price"] for x in items]
        category_medians[cat] = statistics.median(prices) if prices else 45.0

    log.info("Category medians: %s", {k: round(v, 2) for k, v in sorted(category_medians.items())})

    # KEY FIX: Capped distillery multipliers
    distillery_mults = {}
    for dist, prices in distillery_prices.items():
        if len(prices) >= 3:
            dist_median = statistics.median(prices)
            # Determine primary category
            cats = defaultdict(int)
            for w in training:
                if (w.distillery or "").lower().strip() == dist:
                    cats[w.category or "world"] += 1
            primary_cat = max(cats, key=cats.get) if cats else "world"
            cat_med = category_medians.get(primary_cat, 45.0)
            if cat_med > 0:
                raw_mult = dist_median / cat_med
                # CAPPED: prevent Brora-style 700x multipliers
                capped = max(MIN_DISTILLERY_MULT, min(raw_mult, MAX_DISTILLERY_MULT))
                distillery_mults[dist] = capped
                if raw_mult > MAX_DISTILLERY_MULT:
                    log.info(
                        "  Capped distillery mult: %s %.1fx -> %.1fx",
                        dist, raw_mult, capped,
                    )

    # KEY FIX: Robust age curves using median prices per age bucket
    age_curves = {}
    for cat, items in category_data.items():
        aged = [(x["age"], x["price"]) for x in items if x["age"] and x["age"] > 0]
        if len(aged) < 10:
            continue

        # Group by age bucket and take medians to resist outliers
        bucket_data = defaultdict(list)
        for age_val, price_val in aged:
            bkt = age_bucket(age_val)
            bucket_data[bkt].append((age_val, price_val))

        points = []
        for bkt, bkt_items in bucket_data.items():
            if len(bkt_items) >= 5:
                med_age = statistics.median([a for a, _ in bkt_items])
                med_price = statistics.median([p for _, p in bkt_items])
                points.append((med_age, med_price))

        if len(points) >= 3:
            ages_arr = np.array([a for a, _ in points], dtype=float)
            prices_arr = np.array([p for _, p in points], dtype=float)
            log_ages = np.log(ages_arr + 1)
            try:
                coeffs = np.polyfit(log_ages, prices_arr, 1)
                age_curves[cat] = coeffs
            except Exception:
                pass

    # Get all whiskeys that need new prices
    estimated = db.query(Whiskey).filter(
        Whiskey.price_is_estimated == True,
    ).all()
    nulled = db.query(Whiskey).filter(
        Whiskey.price_usd.is_(None),
    ).all()

    to_fix = [w for w in (estimated + nulled) if w.id not in trusted_ids]
    log.info("Recalculating prices for %d whiskeys", len(to_fix))

    updated = 0
    batch_size = 500

    for i, w in enumerate(to_fix):
        if i % 10000 == 0 and i > 0:
            log.info("  Progress: %d / %d", i, len(to_fix))
            if not dry_run:
                db.commit()

        cat = w.category or "world"
        base = category_medians.get(cat, 45.0)
        confidence = 0.30

        # Age adjustment (using robust curves)
        if w.age and cat in age_curves:
            slope, intercept = age_curves[cat]
            predicted = slope * np.log(w.age + 1) + intercept
            cap = get_price_cap(cat, w.age)
            if 5.0 < predicted < cap:
                base = predicted
                confidence += 0.10

        # ABV premium (halved from 0.015 to 0.008)
        if w.abv and w.abv > 50.0:
            base *= 1.0 + (w.abv - 46.0) * 0.008
            confidence += 0.05

        # Distillery multiplier (CAPPED)
        dist = (w.distillery or "").lower().strip()
        if dist in distillery_mults:
            base *= distillery_mults[dist]
            confidence += 0.15

        # Apply per-category cap — cast to native float for PostgreSQL compat
        cap = get_price_cap(cat, w.age)
        price = float(max(8.0, min(base, cap)))

        if not dry_run:
            w.price_usd = round(price, 2)
            w.price_is_estimated = True

            # Update enrichment log
            detail_parts = [f"cat={cat}"]
            if w.age:
                detail_parts.append(f"age={w.age}")
            if dist in distillery_mults:
                detail_parts.append(f"dist_mult={distillery_mults[dist]:.2f}")
            detail = "statistical_v2: " + ", ".join(detail_parts)

            existing_log = db.query(PriceEnrichmentLog).filter(
                PriceEnrichmentLog.whiskey_id == w.id,
            ).first()
            if existing_log:
                existing_log.method = "statistical"
                existing_log.confidence = min(confidence, 1.0)
                existing_log.source_detail = detail
                existing_log.enriched_at = datetime.now(timezone.utc)
            else:
                db.add(PriceEnrichmentLog(
                    whiskey_id=w.id,
                    method="statistical",
                    confidence=min(confidence, 1.0),
                    source_detail=detail,
                    original_price=None,
                ))

        updated += 1

    if not dry_run:
        db.commit()

    log.info("Phase 4: recalculated %d prices", updated)
    return updated


# ── Phase 5: Re-match Nulled Bottles ───────────────────────────────────

def phase5_rematch(db: Session, trusted_ids: set, dry_run: bool) -> int:
    """Re-attempt matching for bottles still without prices."""
    log.info("=== Phase 5: Re-matching nulled bottles ===")

    # Find bottles still without prices
    nulled = db.query(Whiskey).filter(
        Whiskey.price_usd.is_(None),
    ).all()
    nulled = [w for w in nulled if w.id not in trusted_ids]

    if not nulled:
        log.info("No nulled bottles remaining")
        return 0

    log.info("Attempting to match %d nulled bottles", len(nulled))

    msrp = _build_msrp_dict()

    # Build index from all priced real bottles
    priced = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd > 0,
        Whiskey.price_is_estimated == False,
    ).all()

    name_index: dict[str, list[tuple[int, float, str]]] = defaultdict(list)
    for w in priced:
        norm = normalize_for_price(w.name)
        dist = (w.distillery or "").lower().strip()
        name_index[norm].append((w.id, w.price_usd, dist))

    matched = 0
    for w in nulled:
        norm = normalize_for_price(w.name)
        dist = (w.distillery or "").lower().strip()

        # Try MSRP first
        if norm in msrp:
            price = msrp[norm]
            cap = get_price_cap(w.category, w.age)
            if price <= cap:
                if not dry_run:
                    w.price_usd = price
                    w.price_is_estimated = False
                matched += 1
                continue

        # Try exact name match with guardrails
        if norm in name_index:
            candidates = name_index[norm]
            same_dist = [m for m in candidates if m[2] == dist] if dist else []
            best = same_dist if same_dist else candidates
            price = statistics.median([m[1] for m in best])
            cap = get_price_cap(w.category, w.age)
            if price <= cap:
                if not dry_run:
                    w.price_usd = round(price, 2)
                    w.price_is_estimated = False
                matched += 1
                continue

        # If still no match, use category median as fallback
        cat_median_q = db.query(Whiskey.price_usd).filter(
            Whiskey.category == (w.category or "world"),
            Whiskey.price_usd.isnot(None),
            Whiskey.price_is_estimated == False,
        ).all()
        if cat_median_q:
            cat_prices = [r[0] for r in cat_median_q]
            price = statistics.median(cat_prices)
            if not dry_run:
                w.price_usd = round(price, 2)
                w.price_is_estimated = True
            matched += 1

    if not dry_run and matched > 0:
        db.commit()

    log.info("Phase 5: re-matched %d bottles", matched)
    return matched


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fix SipSense whiskey prices")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--report-only", action="store_true", help="Just show current stats")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        if args.report_only:
            stats = generate_stats(db)
            print(json.dumps(stats, indent=2))
            return

        # Phase 0: Backup & baseline
        log.info("=== Phase 0: Backup & Baseline ===")
        backup_path = backup_db()
        before = generate_stats(db)
        log.info(
            "Before: avg=$%.2f, estimated_avg=$%.2f, est>$1k=%d, est>$5k=%d",
            before["avg_price"], before["estimated_avg"],
            before["over_1000_estimated"], before["over_5000_estimated"],
        )

        if args.dry_run:
            log.info("*** DRY RUN MODE - no changes will be written ***")

        # Phase 1: Build trusted set
        trusted_ids = phase1_trusted_ids(db)

        # Phase 2: Fix categories
        cat_fixes = phase2_fix_categories(db, dry_run=args.dry_run)

        # Phase 3: Null bad matches
        nulled = phase3_null_bad_matches(db, trusted_ids, dry_run=args.dry_run)

        # Phase 4: Recalculate (CORE FIX)
        recalculated = phase4_recalculate(db, trusted_ids, dry_run=args.dry_run)

        # Phase 5: Re-match any remaining nulls
        rematched = phase5_rematch(db, trusted_ids, dry_run=args.dry_run)

        # Phase 6: After report
        log.info("=== Phase 6: After Report ===")
        after = generate_stats(db)
        log.info(
            "After:  avg=$%.2f, estimated_avg=$%.2f, est>$1k=%d, est>$5k=%d",
            after["avg_price"], after["estimated_avg"],
            after["over_1000_estimated"], after["over_5000_estimated"],
        )

        report = {
            "run_date": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "backup_path": str(backup_path),
            "changes": {
                "category_fixes": cat_fixes,
                "nulled_bad_matches": nulled,
                "recalculated": recalculated,
                "rematched": rematched,
            },
            "before": before,
            "after": after,
            "diff": {
                "avg_price_change": round(after["avg_price"] - before["avg_price"], 2),
                "estimated_avg_change": round(after["estimated_avg"] - before["estimated_avg"], 2),
                "over_1000_change": after["over_1000_estimated"] - before["over_1000_estimated"],
                "over_5000_change": after["over_5000_estimated"] - before["over_5000_estimated"],
            },
        }

        if not args.dry_run:
            REPORT_PATH.write_text(json.dumps(report, indent=2))
            log.info("Report written to %s", REPORT_PATH)
        else:
            print("\n" + json.dumps(report, indent=2))

        log.info("=== Done! ===")

    finally:
        db.close()


if __name__ == "__main__":
    main()
