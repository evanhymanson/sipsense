"""
SipSense whiskey scraper CLI.

Sources:
  github          — 2,636 whiskeys from a GitHub CSV dataset (~5s, no rate limits)
  distiller       — scrapes distiller.com detail pages (~6k–8k whiskeys)
  whiskybase      — scrapes whiskybase.com (~20k+ whiskeys with ratings)
  openfoodfacts   — OpenFoodFacts API (~3-5k with UPC barcodes)
  masterofmalt    — masterofmalt.com product listings (~20k, UK retailer)
  whiskyexchange  — thewhiskyexchange.com listings (~15k, UK retailer)
  vinmonopolet    — Vinmonopolet public API (~2-3k, Norway state monopoly)
  connosr         — connosr.com community ratings (~10k)
  ttb             — TTB COLA registry (⚠️ offline as of Feb 2026)
  wikidata        — Wikidata SPARQL (⚠️ entity IDs broken, ~40 results)
  all             — runs all working sources in order (default)

Usage (run from backend/ directory):
  python -m scraper.run                                       # all sources
  python -m scraper.run --source github                       # fast CSV import (~5s)
  python -m scraper.run --source distiller --limit 500
  python -m scraper.run --source distiller --resume
  python -m scraper.run --source openfoodfacts
  python -m scraper.run --source masterofmalt --limit 20000
  python -m scraper.run --source whiskyexchange --limit 15000
  python -m scraper.run --source vinmonopolet
  python -m scraper.run --source connosr --limit 10000
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

PROGRESS_FILE = Path(__file__).parent / "progress.json"

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
            except Exception:
                pass  # column already exists — fine


# ── Progress helpers ──────────────────────────────────────────────────────

_PROGRESS_DEFAULTS = {
    "completed_sources": [],
    "distiller_index": 0,
    "whiskybase_index": 0,
    "masterofmalt_start": 0,
    "whiskyexchange_page": 1,
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

def get_existing_names(db) -> set[str]:
    rows = db.query(models.Whiskey.name).all()
    return {r.name.lower() for r in rows}


def save_whiskey(db, data: dict, known_names: set[str], dry_run: bool) -> bool:
    """Insert one whiskey. Returns True if saved, False if duplicate."""
    name_lower = data["name"].lower()
    if name_lower in known_names:
        return False
    if dry_run:
        log.info(
            "[DRY RUN] %s | %s | %s | ABV=%s%%",
            data["name"], data.get("distillery"),
            data.get("category"), data.get("abv"),
        )
        known_names.add(name_lower)
        return True
    db.add(models.Whiskey(**data))
    db.commit()
    known_names.add(name_lower)
    return True


# ── Source runners ────────────────────────────────────────────────────────

def run_github(db, known_names, dry_run, limit):
    log.info("=== SOURCE: GitHub CSV dataset ===")
    rows = fetch_github_whiskeys()
    saved = skipped = 0
    with tqdm(rows[:limit], desc="GitHub CSV", unit="whiskey") as pbar:
        for data in pbar:
            data["source"] = "github"
            if save_whiskey(db, data, known_names, dry_run):
                saved += 1
            else:
                skipped += 1
            pbar.set_postfix(saved=saved, skipped=skipped)
    log.info("GitHub CSV done: saved=%d  skipped(dup)=%d", saved, skipped)
    return saved


def run_distiller(db, known_names, dry_run, limit, start_index, progress):
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
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if (saved + skipped + failed) % 50 == 0 and not dry_run:
                    progress["distiller_index"] = (
                        start_index + saved + skipped + failed
                    )
                    progress["total_saved"] = db.query(models.Whiskey).count()
                    save_progress(progress)

    log.info(
        "Distiller done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["distiller_index"] = start_index + saved + skipped + failed
        progress["total_saved"] = db.query(models.Whiskey).count()
        save_progress(progress)

    return saved


def run_whiskybase(db, known_names, dry_run, limit, start_index, progress):
    log.info("=== SOURCE: Whiskybase.com ===")
    log.warning(
        "Whiskybase is currently blocked by Cloudflare bot protection (403). "
        "Skipping — re-enable when a browser-automation solution is in place."
    )
    return 0
    # ── blocked — code below kept for when Cloudflare is bypassed ──
    from .whiskybase import WhiskybaseScraper

    saved = skipped = failed = 0
    count = 0

    with WhiskybaseScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="Whiskybase", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit, start_offset=start_index):
                count += 1
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "whiskybase"
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if count % 50 == 0 and not dry_run:
                    progress["whiskybase_index"] = start_index + count
                    progress["total_saved"] = db.query(models.Whiskey).count()
                    save_progress(progress)

    log.info(
        "Whiskybase done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["whiskybase_index"] = start_index + count
        progress["total_saved"] = db.query(models.Whiskey).count()
        save_progress(progress)
    return saved


def run_ttb(db, known_names, dry_run, limit, ttb_file=None):
    log.info("=== SOURCE: TTB COLA Registry ===")
    from .ttb import TTBScraper

    saved = skipped = failed = 0

    with TTBScraper(file_path=ttb_file) as scraper:
        rows = scraper.fetch_whiskeys()
        with tqdm(rows[:limit], desc="TTB", unit="whiskey") as pbar:
            for raw in pbar:
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "ttb"
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

    log.info(
        "TTB done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    return saved


def run_wikidata(db, known_names, dry_run, limit):
    log.info("=== SOURCE: Wikidata SPARQL ===")
    from .wikidata import WikidataScraper

    saved = skipped = failed = 0

    with WikidataScraper() as scraper:
        rows = scraper.fetch_whiskeys()
        with tqdm(rows[:limit], desc="Wikidata", unit="whiskey") as pbar:
            for raw in pbar:
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "wikidata"
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

    log.info(
        "Wikidata done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    return saved


def run_openfoodfacts(db, known_names, dry_run, limit):
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
                if save_whiskey(db, normalized, known_names, dry_run):
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


def run_masterofmalt(db, known_names, dry_run, limit, start_offset, progress):
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
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if count % 50 == 0 and not dry_run:
                    progress["masterofmalt_start"] = start_offset + count
                    progress["total_saved"] = db.query(models.Whiskey).count()
                    save_progress(progress)

    log.info(
        "Master of Malt done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["masterofmalt_start"] = start_offset + count
        progress["total_saved"] = db.query(models.Whiskey).count()
        save_progress(progress)
    return saved


def run_whiskyexchange(db, known_names, dry_run, limit, start_page, progress):
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
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

                if count % 50 == 0 and not dry_run:
                    # page = start_page + items_scraped // PAGE_SIZE
                    progress["whiskyexchange_page"] = start_page + count // 24
                    progress["total_saved"] = db.query(models.Whiskey).count()
                    save_progress(progress)

    log.info(
        "Whisky Exchange done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    if not dry_run:
        progress["whiskyexchange_page"] = start_page + count // 24
        progress["total_saved"] = db.query(models.Whiskey).count()
        save_progress(progress)
    return saved


def run_vinmonopolet(db, known_names, dry_run, limit):
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
                if save_whiskey(db, normalized, known_names, dry_run):
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


def run_connosr(db, known_names, dry_run, limit):
    log.info("=== SOURCE: Connosr ===")
    from .connosr import ConnosrScraper

    saved = skipped = failed = 0

    with ConnosrScraper(verbose=False) as scraper:
        with tqdm(total=limit, desc="Connosr", unit="whiskey") as pbar:
            for raw in scraper.iter_whiskeys(limit=limit):
                normalized = normalize(raw)
                if normalized is None:
                    failed += 1
                    pbar.update(1)
                    continue

                normalized["source"] = "connosr"
                if save_whiskey(db, normalized, known_names, dry_run):
                    saved += 1
                else:
                    skipped += 1

                pbar.update(1)
                pbar.set_postfix(saved=saved, skipped=skipped, failed=failed)

    log.info(
        "Connosr done: saved=%d  skipped(dup)=%d  failed(bad data)=%d",
        saved, skipped, failed,
    )
    return saved


# ── Main ──────────────────────────────────────────────────────────────────

ALL_SOURCES = [
    "github", "distiller", "whiskybase", "openfoodfacts",
    "masterofmalt", "whiskyexchange", "vinmonopolet",
    # connosr: removed — listing pages lack ABV, inserts fake abv=43.0
    # ttb: removed — FOIA URL dead as of Feb 2026
    # wikidata: removed — entity IDs broken, only ~40 results
]


def main():
    parser = argparse.ArgumentParser(description="SipSense whiskey scraper")
    parser.add_argument(
        "--source",
        choices=ALL_SOURCES + ["all"],
        default="all",
        help="Data source (default: all)",
    )
    parser.add_argument(
        "--limit", type=int, default=200_000,
        help="Max whiskeys to add per source (default 200000)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume distiller/whiskybase scrape from last saved position",
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
        help="Path to a pre-downloaded TTB ZIP or CSV file",
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
        progress = (
            load_progress() if args.resume
            else {"distiller_index": 0, "whiskybase_index": 0, "total_saved": 0}
        )
        known_names = get_existing_names(db)
        log.info("DB currently has %d whiskeys.", len(known_names))

        if args.dry_run:
            log.info("DRY RUN mode — nothing will be written to the database.")

        total_saved = 0
        sources = ALL_SOURCES if args.source == "all" else [args.source]
        completed = set(progress.get("completed_sources", []))

        for source in sources:
            # When resuming, skip sources that already finished
            if args.resume and source in completed:
                log.info("=== SOURCE: %s — already completed, skipping ===", source)
                continue

            remaining = (
                max(0, args.limit - len(known_names))
                if args.source == "all"
                else args.limit
            )

            if source == "github":
                total_saved += run_github(db, known_names, args.dry_run, remaining)

            elif source == "distiller":
                start = progress.get("distiller_index", 0) if args.resume else 0
                total_saved += run_distiller(
                    db, known_names, args.dry_run, remaining, start, progress
                )

            elif source == "whiskybase":
                start = progress.get("whiskybase_index", 0) if args.resume else 0
                total_saved += run_whiskybase(
                    db, known_names, args.dry_run, remaining, start, progress
                )

            elif source == "ttb":
                total_saved += run_ttb(
                    db, known_names, args.dry_run, remaining,
                    ttb_file=args.ttb_file,
                )

            elif source == "wikidata":
                total_saved += run_wikidata(db, known_names, args.dry_run, remaining)

            elif source == "openfoodfacts":
                total_saved += run_openfoodfacts(
                    db, known_names, args.dry_run, remaining
                )

            elif source == "masterofmalt":
                start = progress.get("masterofmalt_start", 0) if args.resume else 0
                total_saved += run_masterofmalt(
                    db, known_names, args.dry_run, remaining, start, progress
                )

            elif source == "whiskyexchange":
                start = progress.get("whiskyexchange_page", 1) if args.resume else 1
                total_saved += run_whiskyexchange(
                    db, known_names, args.dry_run, remaining, start, progress
                )

            elif source == "vinmonopolet":
                total_saved += run_vinmonopolet(db, known_names, args.dry_run, remaining)

            elif source == "connosr":
                total_saved += run_connosr(db, known_names, args.dry_run, remaining)

            # Mark source as done so future --resume skips it
            if not args.dry_run and source not in completed:
                completed.add(source)
                progress["completed_sources"] = list(completed)
                save_progress(progress)

        final_count = db.query(models.Whiskey).count()
        log.info(
            "Done! Total whiskeys in DB: %d (added %d this run)",
            final_count, total_saved,
        )

        if args.source in ("distiller", "all"):
            log.info(
                "To resume: python -m scraper.run --resume  "
                "(or ./scrape_all.sh)"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()
