"""
SipSense database cleanup script.

Fixes data quality issues identified in the whiskey database:
  1. Removes non-whiskey products (ABV < 25%, known non-whiskeys)
  2. Deduplicates identical names
  3. Fixes specific misclassified entries (Jack Daniel's, Tennessee whiskeys)
  4. Normalizes region names (multi-language -> English)
  5. Fixes category-bound regions (scotch sold in France -> Scotland)
  6. Infers missing regions from category

Usage:
  cd backend
  python cleanup_db.py              # run all fixes
  python cleanup_db.py --dry-run    # preview changes without writing
"""

import argparse
import logging
import shutil
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import func
from app.database import SessionLocal, engine, Base
from app import models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cleanup")

DB_PATH = Path(__file__).parent / "sipsense.db"

# ── Non-whiskey IDs to force-delete ──────────────────────────────────────────
FORCE_DELETE_IDS = {
    4140,  # Bodyme Organic Vegan Protein Powder
    4404,  # Fireball (cinnamon liqueur, 33%)
    4337,  # Regal Apple (flavored spirit, 79.5%)
}

# ── Region language-variant mapping ──────────────────────────────────────────
REGION_LANGUAGE_MAP = {
    # Scottish sub-regions (preserve as-is)
    "speyside": "Speyside",
    "islay": "Islay",
    "highlands": "Highlands",
    "highland": "Highlands",
    "lowlands": "Lowlands",
    "lowland": "Lowlands",
    "campbeltown": "Campbeltown",
    "islands": "Islands",

    # USA sub-regions
    "kentucky": "Kentucky",
    "tennessee": "Tennessee",
    "vermont": "Vermont",
    "indiana": "Indiana",

    # Countries — English canonical
    "scotland": "Scotland",
    "ireland": "Ireland",
    "japan": "Japan",
    "canada": "Canada",
    "france": "France",
    "germany": "Germany",
    "india": "India",
    "taiwan": "Taiwan",
    "australia": "Australia",
    "england": "England",
    "wales": "Wales",
    "usa": "USA",
    "united states": "USA",
    "norway": "Norway",
    "sweden": "Sweden",
    "denmark": "Denmark",
    "finland": "Finland",
    "belgium": "Belgium",
    "netherlands": "Netherlands",
    "italy": "Italy",
    "spain": "Spain",
    "portugal": "Portugal",
    "new zealand": "New Zealand",
    "south africa": "South Africa",
    "mexico": "Mexico",
    "argentina": "Argentina",
    "bolivia": "Bolivia",
    "venezuela": "Venezuela",
    "romania": "Romania",
    "bulgaria": "Bulgaria",
    "latvia": "Latvia",
    "israel": "Israel",
    "lebanon": "Lebanon",
    "united kingdom": "United Kingdom",
    "county cork": "County Cork",

    # Norwegian / Swedish
    "skottland": "Scotland",
    "frankrike": "France",
    "storbritannia": "United Kingdom",
    "spania": "Spain",
    "tyskland": "Germany",
    "danmark": "Denmark",
    "sverige": "Sweden",
    "norge": "Norway",
    "belgia": "Belgium",
    "libanon": "Lebanon",

    # German
    "deutschland": "Germany",
    "frankreich": "France",
    "belgien": "Belgium",
    "australien": "Australia",
    "irland": "Ireland",
    "schweiz": "Switzerland",
    "schweden": "Sweden",
    "kanada": "Canada",
    "indien": "India",
    "vereinigtes konigreich": "United Kingdom",

    # French
    "ecosse": "Scotland",
    "australie": "Australia",
    "belgique": "Belgium",
    "nederland": "Netherlands",
    "suisse": "Switzerland",
    "republique tcheque": "Czech Republic",
    "reunion": "France",

    # Spanish / Italian / Portuguese
    "francia": "France",
    "alemania": "Germany",
    "belgica": "Belgium",
    "espana": "Spain",
    "italia": "Italy",
    "spagna": "Italy",  # Italian for Spain (but likely means Italy context)

    # Polish
    "polska": "Poland",
    "szwajcaria": "Switzerland",

    # Dutch
    "nl:verenigd koninkrijk": "United Kingdom",

    # Cyrillic
    "\u0420\u043e\u0441\u0441\u0438\u044f": "Russia",
    "\u0411\u0435\u043b\u043e\u0440\u0443\u0441\u0441\u0438\u044f": "Belarus",

    # OpenFoodFacts En: prefixed (without prefix, handled separately)
    "switzerland": "Switzerland",
    "czech republic": "Czech Republic",
    "poland": "Poland",
    "russia": "Russia",
    "belarus": "Belarus",

    # Irish sub-regions
    "county antrim": "County Antrim",
    "nord irland": "Northern Ireland",
    "northern ireland": "Northern Ireland",
}

# ── Valid regions per category ───────────────────────────────────────────────
VALID_SCOTCH_REGIONS = {
    "speyside", "islay", "highlands", "lowlands", "campbeltown", "islands", "scotland",
}
VALID_BOURBON_RYE_REGIONS = {
    "kentucky", "tennessee", "usa", "indiana", "new york", "texas", "colorado",
    "vermont", "virginia", "oregon", "washington", "wyoming", "california",
    "montana", "utah", "north carolina", "new mexico", "minnesota", "iowa",
    "michigan", "wisconsin", "illinois", "missouri", "pennsylvania", "ohio",
    "maryland", "georgia", "florida", "arizona",
}
VALID_IRISH_REGIONS = {"ireland", "county cork", "county antrim", "northern ireland"}
VALID_JAPANESE_REGIONS = {"japan"}
VALID_CANADIAN_REGIONS = {"canada"}

# ── Category inference for missing regions ───────────────────────────────────
CATEGORY_TO_DEFAULT_REGION = {
    "scotch": "Scotland",
    "bourbon": "USA",
    "rye": "USA",
    "irish": "Ireland",
    "japanese": "Japan",
    "canadian": "Canada",
}


def _cascade_delete_whiskey_ids(db, ids: set):
    """Delete FK references before deleting whiskey entries."""
    if not ids:
        return
    db.query(models.UserFavorite).filter(
        models.UserFavorite.whiskey_id.in_(ids)
    ).delete(synchronize_session=False)
    db.query(models.UserRating).filter(
        models.UserRating.whiskey_id.in_(ids)
    ).delete(synchronize_session=False)
    db.query(models.StoreAvailability).filter(
        models.StoreAvailability.whiskey_id.in_(ids)
    ).delete(synchronize_session=False)


def _richness_score(w):
    """Score a whiskey entry by how many useful fields it has."""
    fields = [w.distillery, w.region, w.age, w.price_usd,
              w.description, w.flavor_profile, w.upc]
    score = sum(1 for f in fields if f is not None and str(f).strip() not in ("", "Unknown"))
    if w.rating_avg and w.rating_avg > 0:
        score += 1
    return score


def fix_1_remove_non_whiskey(db):
    """Remove entries that are not actual whiskey (beers, wines, cocktails, etc.)."""
    log.info("=" * 60)
    log.info("FIX 1: Remove non-whiskey products")

    # Low ABV entries
    low_abv = db.query(models.Whiskey).filter(models.Whiskey.abv < 25.0).all()
    low_abv_ids = {w.id for w in low_abv}
    for w in low_abv:
        log.info("  ABV < 25: id=%d name='%s' abv=%.1f cat='%s'", w.id, w.name, w.abv, w.category)

    # Force-delete specific IDs
    force_ids = set()
    for fid in FORCE_DELETE_IDS:
        w = db.query(models.Whiskey).filter(models.Whiskey.id == fid).first()
        if w:
            log.info("  Force delete: id=%d name='%s' abv=%.1f", w.id, w.name, w.abv)
            force_ids.add(fid)
        else:
            log.warning("  Force delete id=%d not found, skipping", fid)

    all_delete_ids = low_abv_ids | force_ids
    if not all_delete_ids:
        log.info("  No non-whiskey products found.")
        return 0

    _cascade_delete_whiskey_ids(db, all_delete_ids)
    count = db.query(models.Whiskey).filter(
        models.Whiskey.id.in_(all_delete_ids)
    ).delete(synchronize_session=False)
    log.info("  Deleted %d non-whiskey products", count)
    return count


def fix_2_deduplicate(db):
    """Remove duplicate whiskey entries, keeping the richest one."""
    log.info("=" * 60)
    log.info("FIX 2: Deduplicate names")

    dupes = (
        db.query(func.lower(models.Whiskey.name), func.count(models.Whiskey.id))
        .group_by(func.lower(models.Whiskey.name))
        .having(func.count(models.Whiskey.id) > 1)
        .all()
    )

    total_removed = 0
    for name_lower, cnt in dupes:
        entries = db.query(models.Whiskey).filter(
            func.lower(models.Whiskey.name) == name_lower
        ).all()
        entries.sort(key=_richness_score, reverse=True)
        keep = entries[0]
        remove = entries[1:]
        for w in remove:
            log.info("  Dedup: keeping id=%d, deleting id=%d for '%s'", keep.id, w.id, w.name)
        remove_ids = {w.id for w in remove}
        _cascade_delete_whiskey_ids(db, remove_ids)
        db.query(models.Whiskey).filter(
            models.Whiskey.id.in_(remove_ids)
        ).delete(synchronize_session=False)
        total_removed += len(remove)

    log.info("  Removed %d duplicate entries", total_removed)
    return total_removed


def fix_3_jack_daniels(db):
    """Fix specific misclassified entries."""
    log.info("=" * 60)
    log.info("FIX 3: Fix misclassified entries")

    fixes = 0

    # Jack Daniel's
    jd = db.query(models.Whiskey).filter(models.Whiskey.id == 4141).first()
    if jd and jd.category != "bourbon":
        log.info("  Jack Daniel's (id=%d): category '%s'->'bourbon', abv %.1f->40.0, region->'Tennessee'",
                 jd.id, jd.category, jd.abv)
        jd.category = "bourbon"
        jd.abv = 40.0
        jd.region = "Tennessee"
        fixes += 1

    # Any other Tennessee whiskeys miscategorized
    tennessee = db.query(models.Whiskey).filter(
        models.Whiskey.name.ilike("%tennessee%"),
        models.Whiskey.category != "bourbon",
        models.Whiskey.category != "rye",
    ).all()
    for w in tennessee:
        log.info("  Tennessee fix: id=%d '%s' category '%s'->'bourbon'", w.id, w.name, w.category)
        w.category = "bourbon"
        if not w.region or w.region.lower() not in VALID_BOURBON_RYE_REGIONS:
            w.region = "Tennessee"
        fixes += 1

    log.info("  Fixed %d misclassified entries", fixes)
    return fixes


def fix_4_normalize_regions(db):
    """Normalize region names from multiple languages to English."""
    log.info("=" * 60)
    log.info("FIX 4: Normalize region names")

    all_whiskeys = db.query(models.Whiskey).filter(
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all()

    updates = 0
    for w in all_whiskeys:
        original = w.region
        cleaned = original.strip()

        # Strip OpenFoodFacts "En:" / "Nl:" etc. prefix
        if len(cleaned) > 3 and cleaned[2] == ":" and cleaned[:2].isalpha():
            cleaned = cleaned[3:]

        lookup = cleaned.lower().strip()

        # Remove accents for lookup (simple cases)
        lookup_normalized = (
            lookup
            .replace("\u00e9", "e")   # e-acute
            .replace("\u00e8", "e")   # e-grave
            .replace("\u00f6", "o")   # o-umlaut
            .replace("\u00fc", "u")   # u-umlaut
            .replace("\u00e4", "a")   # a-umlaut
            .replace("\u00f8", "o")   # o-slash
            .replace("\u00e5", "a")   # a-ring
            .replace("\u00c3\u00b8", "o")
        )

        mapped = REGION_LANGUAGE_MAP.get(lookup) or REGION_LANGUAGE_MAP.get(lookup_normalized)
        if mapped and mapped != original:
            w.region = mapped
            updates += 1
            if updates <= 50:  # Don't spam logs
                log.info("  Region: '%s' -> '%s' (id=%d)", original, mapped, w.id)

    if updates > 50:
        log.info("  ... and %d more region normalizations", updates - 50)
    log.info("  Normalized %d region values", updates)
    return updates


def fix_5_scotch_sale_country_regions(db):
    """Fix scotch/bourbon/irish/japanese entries where region is the sale country, not origin."""
    log.info("=" * 60)
    log.info("FIX 5: Fix sale-country regions")

    fixes = 0

    # Scotch: must be from Scotland or a Scottish sub-region
    for w in db.query(models.Whiskey).filter(
        models.Whiskey.category == "scotch",
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all():
        if w.region.lower() not in VALID_SCOTCH_REGIONS:
            log.info("  Scotch: id=%d '%s' region '%s' -> 'Scotland'", w.id, w.name[:50], w.region) if fixes < 30 else None
            w.region = "Scotland"
            fixes += 1

    # Bourbon & Rye: must be from USA
    for w in db.query(models.Whiskey).filter(
        models.Whiskey.category.in_(["bourbon", "rye"]),
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all():
        if w.region.lower() not in VALID_BOURBON_RYE_REGIONS:
            log.info("  Bourbon/Rye: id=%d '%s' region '%s' -> 'USA'", w.id, w.name[:50], w.region) if fixes < 30 else None
            w.region = "USA"
            fixes += 1

    # Irish: must be from Ireland
    for w in db.query(models.Whiskey).filter(
        models.Whiskey.category == "irish",
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all():
        if w.region.lower() not in VALID_IRISH_REGIONS:
            log.info("  Irish: id=%d '%s' region '%s' -> 'Ireland'", w.id, w.name[:50], w.region) if fixes < 30 else None
            w.region = "Ireland"
            fixes += 1

    # Japanese: must be from Japan
    for w in db.query(models.Whiskey).filter(
        models.Whiskey.category == "japanese",
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all():
        if w.region.lower() not in VALID_JAPANESE_REGIONS:
            log.info("  Japanese: id=%d '%s' region '%s' -> 'Japan'", w.id, w.name[:50], w.region) if fixes < 30 else None
            w.region = "Japan"
            fixes += 1

    # Canadian: must be from Canada
    for w in db.query(models.Whiskey).filter(
        models.Whiskey.category == "canadian",
        models.Whiskey.region.isnot(None),
        models.Whiskey.region != "",
    ).all():
        if w.region.lower() not in VALID_CANADIAN_REGIONS:
            log.info("  Canadian: id=%d '%s' region '%s' -> 'Canada'", w.id, w.name[:50], w.region) if fixes < 30 else None
            w.region = "Canada"
            fixes += 1

    if fixes > 30:
        log.info("  ... and %d more sale-country fixes", fixes - 30)
    log.info("  Fixed %d entries with sale-country regions", fixes)
    return fixes


def fix_6_infer_missing_regions(db):
    """Fill in missing regions from category."""
    log.info("=" * 60)
    log.info("FIX 6: Infer missing regions from category")

    missing = db.query(models.Whiskey).filter(
        (models.Whiskey.region.is_(None)) | (models.Whiskey.region == "")
    ).all()

    inferred = 0
    for w in missing:
        cat = (w.category or "").lower()
        default_region = CATEGORY_TO_DEFAULT_REGION.get(cat)
        if default_region:
            w.region = default_region
            inferred += 1

    log.info("  Inferred region for %d of %d whiskeys with missing regions", inferred, len(missing))
    return inferred


def main():
    parser = argparse.ArgumentParser(description="Clean up the SipSense whiskey database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        log.error("Database not found at %s", DB_PATH)
        sys.exit(1)

    # Backup
    backup_name = f"sipsense.db.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = DB_PATH.parent / backup_name
    log.info("Backing up database to %s", backup_name)
    shutil.copy2(DB_PATH, backup_path)

    db = SessionLocal()
    original_count = db.query(models.Whiskey).count()
    log.info("Starting cleanup. Original whiskey count: %d", original_count)

    if args.dry_run:
        log.info("[DRY RUN MODE - no changes will be written]")

    try:
        deleted_non_whiskey = fix_1_remove_non_whiskey(db)
        db.flush()  # ensure deletions visible to dedup queries
        deleted_dupes = fix_2_deduplicate(db)
        db.flush()  # ensure dedup visible to misclass queries
        fixed_miscat = fix_3_jack_daniels(db)
        db.flush()  # ensure category changes visible to region queries
        normalized_regions = fix_4_normalize_regions(db)
        db.flush()  # ensure normalized regions visible to sale-country fix
        fixed_sale_regions = fix_5_scotch_sale_country_regions(db)
        db.flush()  # ensure sale-country fixes visible to inference
        inferred_regions = fix_6_infer_missing_regions(db)

        if args.dry_run:
            db.rollback()
            log.info("=" * 60)
            log.info("[DRY RUN] No changes written. Re-run without --dry-run to apply.")
        else:
            db.commit()
            final_count = db.query(models.Whiskey).count()
            log.info("=" * 60)
            log.info("CLEANUP COMPLETE")
            log.info("  Original count:       %d", original_count)
            log.info("  Final count:           %d", final_count)
            log.info("  Deleted (non-whiskey): %d", deleted_non_whiskey)
            log.info("  Deleted (duplicates):  %d", deleted_dupes)
            log.info("  Fixed misclassified:   %d", fixed_miscat)
            log.info("  Regions normalized:    %d", normalized_regions)
            log.info("  Sale-country fixed:    %d", fixed_sale_regions)
            log.info("  Regions inferred:      %d", inferred_regions)
            log.info("  Backup at:             %s", backup_path)
            log.info("=" * 60)
    except Exception:
        db.rollback()
        log.exception("Cleanup failed, rolled back all changes")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
