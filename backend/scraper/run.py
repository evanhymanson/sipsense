"""
SipSense whiskey scraper CLI.

Sources:
  github          — 2,636 whiskeys from a GitHub CSV dataset (~5s, no rate limits)
  kaggle          — multiple Kaggle CSV datasets (~2,500 whiskeys, no rate limits)
  distiller       — scrapes distiller.com detail pages (~6k–8k whiskeys)
  ttb_kaggle      — TTB COLA from Kaggle demo CSV (~5-10k whiskeys, no rate limits)
  ttb_online      — TTB COLA online registry search (~15-40k whiskeys)
  whiskycom       — whisky.com database (~41k bottles)
  whiskyadvocate  — Whisky Advocate expert reviews (~7k whiskeys)
  whiskybase      — scrapes whiskybase.com (~220k+ whiskeys, needs Playwright)
  openfoodfacts   — OpenFoodFacts API (~3-5k with UPC barcodes)
  masterofmalt    — masterofmalt.com product listings (~20k, needs Playwright)
  whiskyexchange  — thewhiskyexchange.com listings (~15k, needs Playwright)
  vinmonopolet    — Vinmonopolet public API (~2-3k, Norway state monopoly)
  all             — runs all working sources in order (default)

Usage (run from backend/ directory):
  python -m scraper.run                                       # all sources
  python -m scraper.run --source github                       # fast CSV import (~5s)
  python -m scraper.run --source kaggle --kaggle-dir scraper/data/kaggle
  python -m scraper.run --source ttb_kaggle --ttb-file scraper/data/ttb-demo.csv
  python -m scraper.run --source whiskycom --resume
  python -m scraper.run --source ttb_online --resume
  python -m scraper.run --source whiskyadvocate --resume
  python -m scraper.run --source distiller --resume
  python -m scraper.run --limit 50 --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from tqdm import tqdm

from app.database import SessionLocal, engine, Base
from app import models

from .normalizer import normalize
from .github_csv import fetch_github_whiskeys
from .distiller import DistillerScraper
from .dedup import DedupIndex

PROGRESS_FILE = Path(__file__).parent / "progress.json"
DEFAULT_KAGGLE_DIR = Path(__file__).parent / "data" / "kaggle"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper.run")


# ── Schema migration ──────────────────────────────────────────────────────

def migrate_schema():
    """
    Add new columns to existing DB without destroying data.
    Safe to run multiple times — silently skips already-existing columns.
    """
    new_columns = [
        "ALTER TABLE whiskeys ADD COLUMN upc TEXT",
        "ALTER TABLE whiskeys ADD COLUMN source TEXT DEFAULT 'manual'",
    ]
    with engine.connect() as conn:
        for stmt in new_columns:
            try:
                conn.execute(text(stmt))
                conn.commit()
                col_name = stmt.split("COLUMN")[1].strip().split()[0]
                log.info("Migration: added column '%s'", col_name)
            except Exception as e:
                err_msg = str(e).lower()
                if "duplicate column" in err_msg or "already exists" in err_msg:
                    pass  # column already exists — fine
                else:
                    log.error("Migration failed for '%s': %s", stmt, e)

    # Add indexes for better query performance at scale
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_whiskeys_category ON whiskeys(category)",
        "CREATE INDEX IF NOT EXISTS ix_whiskeys_distillery ON whiskeys(distillery)",
        "CREATE INDEX IF NOT EXISTS ix_whiskeys_source ON whiskeys(source)",
    ]
    with engine.connect() as conn:
        for stmt in indexes:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass


# ── Progress helpers ──────────────────────────────────────────────────────

_PROGRESS_DEFAULTS = {
    "completed_sources": [],
    "distiller_index": 0,
    "whiskybase_index": 0,
    "masterofmalt_start": 0,
    "whiskyexchange_page": 1,
    "whiskycom_page": 0,
    "ttb_online_type_index": 0,
    "whiskyadvocate_page": 1,
    "total_saved": 0,
}


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            data = json.load(f)
        # fill in any keys added since the file was written
        for k, v in _PROGRESS_DEFAULTS.items():
            data.setdefault(k, v)
        return data
    return dict(_PROGRESS_DEFAULTS)


def save_progress(data: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── DB helpers ────────────────────────────────────────────────────────────

def build_dedup_index(db) -> DedupIndex:
    """Build an in-memory dedup index from all existing whiskeys."""
    rows = db.query(models.Whiskey.name).all()
    index = DedupIndex()
    for r in rows:
        index.add(r.name)
    return index


_BATCH_SIZE = 200
_pending_count = 0


def save_whiskey(db, data: dict, dedup: DedupIndex, dry_run: bool) -> bool:
    """Insert one whiskey. Batches commits every _BATCH_SIZE rows for performance."""
    global _pending_count
    if dedup.is_duplicate(data["name"]):
        return False
    if dry_run:
        log.info(
            "[DRY RUN] %s | %s | %s | ABV=%s%%",
            data["name"], data.get("distillery"),
            data.get("category"), data.get("abv"),
        )
        dedup.add(data["name"])
        return True
    db.add(models.Whiskey(**data))
    _pending_count += 1
    if _pending_count >= _BATCH_SIZE:
        db.commit()
        _pending_count = 0
    dedup.add(data["name"])
    return True


def flush_pending(db, dry_run: bool):
    """Commit any remaining uncommitted whiskeys."""
    global _pending_count
    if not dry_run and _pending_count > 0:
        db.commit()
        _pending_count = 0


# ── Source runners ────────────────────────────────────────────────────────

def run_github(db, dedup, dry_run, limit):
    log.info("=== SOURCE: GitHub CSV dataset ===")
    rows = fetch_github_whiskeys()
    saved = skipped = 0
    with tqdm(rows[:limit], desc="GitHub CSV", unit="whiskey") as pbar:
        for data in pbar:
            data["source"] = "github"
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.set_postfix(saved=saved, skipped=skipped)
    log.info("GitHub CSV done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_kaggle(db, dedup, dry_run, limit, kaggle_dir):
    log.info("=== SOURCE: Kaggle CSV datasets ===")
    from .kaggle_csv import iter_kaggle_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Kaggle CSVs", unit="whiskey") as pbar:
        for data in iter_kaggle_whiskeys(kaggle_dir):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Kaggle CSVs done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_distiller(db, dedup, dry_run, limit, start_index, progress):
    log.info("=== SOURCE: Distiller.com ===")
    saved = skipped = failed = 0

    with DistillerScraper(verbose=False) as scraper:
        total_slugs = scraper.slug_count()
        log.info(
            "Distiller: %d whiskey slugs available (starting at index %d)",
            total_slugs, start_index,
        )

        with tqdm(
            total=min(limit, total_slugs - start_index),
            desc="Distiller", unit="whiskey",
        ) as pbar:
            for raw in scraper.iter_whiskeys(limit=limit, start_index=start_index):
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "distiller"
                if save_whiskey(db, normalized, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if (saved + skipped + failed) % 50 == 0 and not dry_run:
                    progress["distiller_index"] = (
                        start_index + saved + skipped + failed
                    )
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info(
        "Distiller done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["distiller_index"] = start_index + saved + skipped + failed
        progress["total_saved"] = len(dedup)
        save_progress(progress)

    return saved


def run_ttb_kaggle(db, dedup, dry_run, limit, ttb_file):
    log.info("=== SOURCE: TTB COLA (Kaggle demo) ===")
    from .ttb_kaggle import iter_ttb_whiskeys

    if not ttb_file:
        # Try known file names in scraper/data/
        data_dir = Path(__file__).parent / "data"
        for candidate in ["colas_2017.csv", "ttb-colas-demo.csv", "colas.csv"]:
            path = data_dir / candidate
            if path.exists():
                ttb_file = str(path)
                break
        # Also check for any large CSV in data_dir (TTB files are > 1MB)
        if not ttb_file and data_dir.exists():
            for f in sorted(data_dir.glob("*.csv"), key=lambda p: p.stat().st_size, reverse=True):
                if f.stat().st_size > 1_000_000:
                    ttb_file = str(f)
                    break
        if not ttb_file:
            log.warning(
                "No TTB file found. Download from "
                "https://www.kaggle.com/datasets/colacloud/ttb-colas-demo "
                "and pass --ttb-file PATH, or place CSV in scraper/data/"
            )
            return 0

    saved = skipped = 0
    with tqdm(total=limit, desc="TTB Kaggle", unit="whiskey") as pbar:
        for data in iter_ttb_whiskeys(ttb_file):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("TTB Kaggle done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_ttb_online(db, dedup, dry_run, limit, start_type_index, progress):
    log.info("=== SOURCE: TTB COLA Online Registry ===")
    from .ttb_online import TTBOnlineScraper

    saved = skipped = failed = 0

    with TTBOnlineScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="TTB Online", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(
                limit=limit,
                start_type_index=start_type_index,
            ):
                if save_whiskey(db, raw, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped)

                if (saved + skipped) % 100 == 0 and not dry_run:
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info(
        "TTB Online done: saved=%d  skipped(dup)=%d",
        saved, skipped,
    )
    if not dry_run:
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_whiskycom(db, dedup, dry_run, limit, start_page, progress):
    log.info("=== SOURCE: Whisky.com database ===")
    from .whiskycom import WhiskyComScraper

    saved = skipped = 0

    with WhiskyComScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="Whisky.com", unit="whiskey") as pbar:
            for data in scraper.iter_whiskeys(limit=limit, start_page=start_page):
                if save_whiskey(db, data, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped)

                if (saved + skipped) % 50 == 0 and not dry_run:
                    progress["whiskycom_page"] = start_page + (saved + skipped) // 16
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info("Whisky.com done: saved=%d  skipped(dup)=%d", saved, skipped)
    if not dry_run:
        progress["whiskycom_page"] = start_page + (saved + skipped) // 16
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_whiskyadvocate(db, dedup, dry_run, limit, start_page, progress):
    log.info("=== SOURCE: Whisky Advocate ===")
    from .whiskyadvocate import WhiskyAdvocateScraper

    saved = skipped = 0

    with WhiskyAdvocateScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="WhiskyAdvocate", unit="whiskey") as pbar:
            for data in scraper.iter_whiskeys(limit=limit, start_page=start_page):
                if save_whiskey(db, data, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped)

                if (saved + skipped) % 50 == 0 and not dry_run:
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info("Whisky Advocate done: saved=%d  skipped(dup)=%d", saved, skipped)
    if not dry_run:
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_whiskybase(db, dedup, dry_run, limit, start_index, progress, proxy=None):
    log.info("=== SOURCE: Whiskybase.com (Playwright browser automation) ===")

    try:
        from .browser_base import HAS_PLAYWRIGHT
    except ImportError:
        HAS_PLAYWRIGHT = False

    if not HAS_PLAYWRIGHT:
        log.warning(
            "Playwright is not installed. Install with:\n"
            "  pip install playwright>=1.40.0\n"
            "  playwright install chromium\n"
            "Skipping Whiskybase."
        )
        return 0

    from .whiskybase import WhiskybaseScraper

    # Fields that the Whiskey model accepts
    _DB_FIELDS = {
        "name", "distillery", "category", "region", "age", "abv",
        "price_usd", "description", "flavor_profile", "rating_avg",
        "rating_count", "upc", "source", "image_url",
    }

    saved = skipped = failed = 0
    count = 0

    with WhiskybaseScraper(verbose=True, proxy=proxy) as scraper:
        with tqdm(total=limit, desc="Whiskybase", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit, start_offset=start_index):
                count += 1

                # The scraper yields pre-processed dicts — just validate
                name = raw.get("name")
                distillery = raw.get("distillery", "Unknown")
                abv = raw.get("abv")

                if not name or len(name) < 3:
                    failed += 1
                    pbar.update(1)
                    continue

                # ABV is required — default to 40.0 if missing
                if abv is None:
                    abv = 40.0

                # Build clean dict for DB insertion
                data = {
                    "name": name,
                    "distillery": distillery,
                    "category": raw.get("category", "world"),
                    "region": raw.get("region"),
                    "age": raw.get("age"),
                    "abv": abv,
                    "rating_avg": raw.get("rating", 0.0) or 0.0,
                    "source": "whiskybase",
                }

                if save_whiskey(db, data, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                # Save progress using actual distillery index (not whiskey count)
                if count % 100 == 0 and not dry_run:
                    progress["whiskybase_index"] = scraper.last_distillery_index
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info(
        "Whiskybase done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["whiskybase_index"] = scraper.last_distillery_index
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_ttb(db, dedup, dry_run, limit, ttb_file=None):
    log.info("=== SOURCE: TTB COLA Registry (legacy) ===")
    log.warning("Legacy TTB FOIA URL is offline. Use --source ttb_kaggle or ttb_online instead.")
    return 0


def run_openfoodfacts(db, dedup, dry_run, limit):
    log.info("=== SOURCE: OpenFoodFacts ===")
    from .openfoodfacts import OpenFoodFactsScraper

    saved = skipped = failed = 0

    with OpenFoodFactsScraper() as scraper:
        with tqdm(total=limit, desc="OpenFoodFacts", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys():
                if saved + skipped + failed >= limit:
                    break

                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                # UPC comes from OpenFoodFacts raw data — preserve it
                normalized["source"] = "openfoodfacts"
                normalized["upc"] = raw.get("upc")
                if save_whiskey(db, normalized, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

    log.info(
        "OpenFoodFacts done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    return saved


def run_masterofmalt(db, dedup, dry_run, limit, start_offset, progress):
    log.info("=== SOURCE: Master of Malt ===")
    log.warning(
        "Master of Malt is currently blocked by Vercel bot protection (429). "
        "Their site is now JS-rendered — skipping until Playwright support is added."
    )
    return 0
    # ── blocked — code below kept for when a bypass is in place ──
    from .masterofmalt import MasterOfMaltScraper

    saved = skipped = failed = 0
    count = 0

    with MasterOfMaltScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="MasterOfMalt", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit, start_offset=start_offset):
                count += 1
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "masterofmalt"
                if save_whiskey(db, normalized, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if count % 50 == 0 and not dry_run:
                    progress["masterofmalt_start"] = start_offset + count
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info(
        "Master of Malt done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["masterofmalt_start"] = start_offset + count
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_whiskyexchange(db, dedup, dry_run, limit, start_page, progress):
    log.info("=== SOURCE: The Whisky Exchange ===")
    log.warning(
        "The Whisky Exchange is currently blocked by Cloudflare bot protection (403). "
        "Skipping — re-enable when a browser-automation solution is in place."
    )
    return 0
    # ── blocked — code below kept for when Cloudflare is bypassed ──
    from .whiskyexchange import WhiskyExchangeScraper

    saved = skipped = failed = 0
    count = 0

    with WhiskyExchangeScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="WhiskyExchange", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit, start_page=start_page):
                count += 1
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "whiskyexchange"
                if save_whiskey(db, normalized, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if count % 50 == 0 and not dry_run:
                    progress["whiskyexchange_page"] = start_page + count // 24
                    progress["total_saved"] = len(dedup)
                    save_progress(progress)

    log.info(
        "Whisky Exchange done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["whiskyexchange_page"] = start_page + count // 24
        progress["total_saved"] = len(dedup)
        save_progress(progress)
    return saved


def run_vinmonopolet(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Vinmonopolet (Norway) ===")
    from .vinmonopolet import VinmonopoletScraper

    saved = skipped = failed = 0

    with VinmonopoletScraper() as scraper:
        with tqdm(total=limit, desc="Vinmonopolet", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit):
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "vinmonopolet"
                if save_whiskey(db, normalized, dedup, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

    log.info(
        "Vinmonopolet done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    return saved


def run_iowa_liquor(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Iowa Liquor (SODA API — no auth required) ===")
    from .iowa_liquor import iter_iowa_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Iowa Liquor", unit="whiskey") as pbar:
        for data in iter_iowa_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Iowa Liquor done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_oregon_olcc(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Oregon OLCC (SODA API — no auth required) ===")
    from .oregon_olcc import iter_oregon_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Oregon OLCC", unit="whiskey") as pbar:
        for data in iter_oregon_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Oregon OLCC done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_lcbo(db, dedup, dry_run, limit):
    log.info("=== SOURCE: LCBO.dev (GraphQL API — no auth required) ===")
    from .lcbo import iter_lcbo_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="LCBO", unit="whiskey") as pbar:
        for data in iter_lcbo_whiskeys():
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("LCBO done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_missouri_liquor(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Missouri Liquor Brands (SODA API — no auth required) ===")
    from .missouri_liquor import iter_missouri_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Missouri", unit="whiskey") as pbar:
        for data in iter_missouri_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Missouri done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_wikiliq(db, dedup, dry_run, limit, wikiliq_dir):
    log.info("=== SOURCE: Wikiliq (Kaggle dataset) ===")
    from .wikiliq import iter_wikiliq_whiskeys

    data_dir = wikiliq_dir or str(Path(__file__).parent / "data" / "wikiliq")

    items = iter_wikiliq_whiskeys(data_dir)
    if not items:
        log.warning(
            "No Wikiliq data found. Download with:\n"
            "  kaggle datasets download -d limtis/wikiliq-dataset "
            "-p scraper/data/wikiliq --unzip"
        )
        return 0

    saved = skipped = 0
    with tqdm(items[:limit], desc="Wikiliq", unit="whiskey") as pbar:
        for data in pbar:
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Wikiliq done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_texas_tabc(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Texas TABC Labels (SODA API — no auth required) ===")
    from .texas_tabc import iter_texas_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Texas TABC", unit="whiskey") as pbar:
        for data in iter_texas_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Texas TABC done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_connecticut_liquor(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Connecticut Liquor Brands (SODA API — no auth required) ===")
    from .connecticut_liquor import iter_connecticut_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Connecticut", unit="whiskey") as pbar:
        for data in iter_connecticut_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Connecticut done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_montgomery_md(db, dedup, dry_run, limit):
    log.info("=== SOURCE: Montgomery County MD (SODA API — no auth required) ===")
    from .montgomery_md import iter_montgomery_whiskeys

    saved = skipped = 0
    with tqdm(total=limit, desc="Montgomery MD", unit="whiskey") as pbar:
        for data in iter_montgomery_whiskeys(limit=limit):
            if saved + skipped >= limit:
                break
            if save_whiskey(db, data, dedup, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.update(1)
            pbar.set_postfix(saved=saved, skipped=skipped)

    log.info("Montgomery MD done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


# ── Main ──────────────────────────────────────────────────────────────────

ALL_SOURCES = [
    "github", "kaggle", "distiller", "ttb_kaggle", "ttb_online",
    "whiskycom", "whiskyadvocate", "whiskybase", "openfoodfacts",
    "masterofmalt", "whiskyexchange", "vinmonopolet",
    "iowa_liquor", "wikiliq", "oregon_olcc", "lcbo", "missouri_liquor",
    "texas_tabc", "connecticut_liquor", "montgomery_md",
    # connosr: removed — listing pages lack ABV, inserts fake abv=43.0
    # ttb: removed — FOIA URL dead as of Feb 2026, replaced by ttb_kaggle/ttb_online
    # wikidata: removed — entity IDs broken, only ~40 results
]


def main():
    parser = argparse.ArgumentParser(description="SipSense whiskey scraper")
    parser.add_argument(
        "--source",
        choices=ALL_SOURCES + ["all", "ttb", "connosr", "wikidata"],
        default="all",
        help="Data source (default: all)",
    )
    parser.add_argument(
        "--limit", type=int, default=300_000,
        help="Max whiskeys to add per source (default 300000)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume scrape from last saved position",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print entries without writing to DB",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Extra debug logging",
    )
    parser.add_argument(
        "--ttb-file", type=str, default=None, metavar="PATH",
        help="Path to a TTB COLA CSV file (for ttb_kaggle source)",
    )
    parser.add_argument(
        "--kaggle-dir", type=str, default=None, metavar="PATH",
        help="Directory containing downloaded Kaggle CSV files",
    )
    parser.add_argument(
        "--proxy", type=str, default=None, metavar="URL",
        help="SOCKS5 proxy URL (e.g., socks5://127.0.0.1:9150 for Tor)",
    )
    parser.add_argument(
        "--wikiliq-dir", type=str, default=None, metavar="PATH",
        help="Directory containing Wikiliq CSV files",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Ensure tables exist and new columns are present
    Base.metadata.create_all(bind=engine)
    if not args.dry_run:
        migrate_schema()

    db = SessionLocal()
    try:
        progress = load_progress() if args.resume else dict(_PROGRESS_DEFAULTS)
        dedup = build_dedup_index(db)
        log.info("DB currently has %d whiskeys (dedup index: %d entries).",
                 len(dedup), len(dedup))

        if args.dry_run:
            log.info("DRY RUN mode — nothing will be written to the database.")

        total_saved = 0
        sources = ALL_SOURCES if args.source == "all" else [args.source]
        completed = set(progress.get("completed_sources", []))

        kaggle_dir = args.kaggle_dir or str(DEFAULT_KAGGLE_DIR)

        for source in sources:
            # When resuming, skip sources that already finished
            if args.resume and source in completed:
                log.info("=== SOURCE: %s — already completed, skipping ===", source)
                continue

            remaining = (
                max(0, args.limit - len(dedup))
                if args.source == "all"
                else args.limit
            )

            if source == "github":
                total_saved += run_github(db, dedup, args.dry_run, remaining)

            elif source == "kaggle":
                total_saved += run_kaggle(
                    db, dedup, args.dry_run, remaining, kaggle_dir
                )

            elif source == "distiller":
                start = progress.get("distiller_index", 0) if args.resume else 0
                total_saved += run_distiller(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "ttb_kaggle":
                total_saved += run_ttb_kaggle(
                    db, dedup, args.dry_run, remaining,
                    ttb_file=args.ttb_file,
                )

            elif source == "ttb_online":
                start = progress.get("ttb_online_type_index", 0) if args.resume else 0
                total_saved += run_ttb_online(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "whiskycom":
                start = progress.get("whiskycom_page", 0) if args.resume else 0
                total_saved += run_whiskycom(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "whiskyadvocate":
                start = progress.get("whiskyadvocate_page", 1) if args.resume else 1
                total_saved += run_whiskyadvocate(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "whiskybase":
                start = progress.get("whiskybase_index", 0) if args.resume else 0
                total_saved += run_whiskybase(
                    db, dedup, args.dry_run, remaining, start, progress,
                    proxy=args.proxy,
                )

            elif source == "ttb":
                total_saved += run_ttb(
                    db, dedup, args.dry_run, remaining,
                    ttb_file=args.ttb_file,
                )

            elif source == "openfoodfacts":
                total_saved += run_openfoodfacts(
                    db, dedup, args.dry_run, remaining
                )

            elif source == "masterofmalt":
                start = progress.get("masterofmalt_start", 0) if args.resume else 0
                total_saved += run_masterofmalt(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "whiskyexchange":
                start = progress.get("whiskyexchange_page", 1) if args.resume else 1
                total_saved += run_whiskyexchange(
                    db, dedup, args.dry_run, remaining, start, progress
                )

            elif source == "vinmonopolet":
                total_saved += run_vinmonopolet(db, dedup, args.dry_run, remaining)

            elif source == "iowa_liquor":
                total_saved += run_iowa_liquor(db, dedup, args.dry_run, remaining)

            elif source == "wikiliq":
                total_saved += run_wikiliq(
                    db, dedup, args.dry_run, remaining,
                    wikiliq_dir=args.wikiliq_dir,
                )

            elif source == "oregon_olcc":
                total_saved += run_oregon_olcc(db, dedup, args.dry_run, remaining)

            elif source == "lcbo":
                total_saved += run_lcbo(db, dedup, args.dry_run, remaining)

            elif source == "missouri_liquor":
                total_saved += run_missouri_liquor(db, dedup, args.dry_run, remaining)

            elif source == "texas_tabc":
                total_saved += run_texas_tabc(db, dedup, args.dry_run, remaining)

            elif source == "connecticut_liquor":
                total_saved += run_connecticut_liquor(db, dedup, args.dry_run, remaining)

            elif source == "montgomery_md":
                total_saved += run_montgomery_md(db, dedup, args.dry_run, remaining)

            elif source in ("connosr", "wikidata"):
                log.warning("Source '%s' is deprecated and will be skipped.", source)

            # Flush any pending batch inserts before marking complete
            flush_pending(db, args.dry_run)

            # Mark source as done so future --resume skips it
            if not args.dry_run and source not in completed:
                completed.add(source)
                progress["completed_sources"] = list(completed)
                save_progress(progress)

        flush_pending(db, args.dry_run)
        final_count = len(dedup)
        log.info(
            "Done! Total whiskeys in DB: %d (added %d this run)",
            final_count, total_saved,
        )

        log.info(
            "To resume: python -m scraper.run --resume  "
            "(or ./scrape_all.sh)"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
