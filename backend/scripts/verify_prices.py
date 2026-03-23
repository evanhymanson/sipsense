"""
Verify prices for all displayed whiskeys (those with images) against
real retail data from government Socrata APIs.

Fetches bulk prices from Iowa, Oregon, Montgomery County, Iowa Sales,
and LCBO, then fuzzy-matches against the 3,314 displayed whiskeys.
Generates a discrepancy report and optionally applies fixes.

Usage:
  cd backend
  python -m scripts.verify_prices                     # report only (safe)
  python -m scripts.verify_prices --fix               # apply corrections
  python -m scripts.verify_prices --threshold 0.25    # 25% threshold
  python -m scripts.verify_prices --limit 100         # partial run
"""

import argparse
import json
import logging
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_
from app.database import SessionLocal
from app.models import Whiskey, PriceEnrichmentLog

from scripts.scrape_prices import (
    normalize_for_price,
    extract_age,
    ages_compatible,
    fetch_iowa_prices,
    fetch_oregon_prices,
    fetch_montgomery_prices,
    fetch_iowa_sales_prices,
    fetch_lcbo_prices,
    apply_price_update,
    backup_db,
)

try:
    from scripts.fix_display_prices import PRICE_CORRECTIONS_BY_ID
except ImportError:
    PRICE_CORRECTIONS_BY_ID = {}

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

REPORT_FILE = Path(__file__).parent / "verify_prices_report.json"


# ── Multi-source price aggregation ───────────────────────────────────

def fetch_all_sources() -> tuple[dict[str, dict[str, float]], dict]:
    """Fetch prices from all bulk API sources.

    Returns:
        per_source: {normalized_name: {source_name: price, ...}}
        source_counts: {source_name: total_products}
    """
    per_source: dict[str, dict[str, float]] = defaultdict(dict)
    source_counts = {}

    sources = [
        ("iowa_catalog", fetch_iowa_prices),
        ("oregon_olcc", fetch_oregon_prices),
        ("montgomery_md", fetch_montgomery_prices),
        ("iowa_sales", fetch_iowa_sales_prices),
        ("lcbo", fetch_lcbo_prices),
    ]

    for name, fetcher in sources:
        try:
            prices = fetcher()
            source_counts[name] = len(prices)
            for norm, price in prices.items():
                per_source[norm][name] = price
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", name, exc)
            source_counts[name] = 0

    log.info(
        "Combined: %d unique products from %d sources",
        len(per_source),
        sum(1 for c in source_counts.values() if c > 0),
    )
    return dict(per_source), source_counts


def compute_reference_price(
    source_prices: dict[str, float],
) -> tuple[float, int, float]:
    """Compute a reference price from multiple sources using median.

    Returns: (reference_price, num_sources, confidence)
    """
    values = list(source_prices.values())
    if not values:
        return 0.0, 0, 0.0

    ref_price = statistics.median(values)
    num_sources = len(values)

    # Confidence: more sources = higher
    confidence = min(0.95, 0.70 + 0.05 * num_sources)

    # Lower confidence if sources disagree significantly
    if num_sources >= 2 and ref_price > 0:
        spread = (max(values) - min(values)) / ref_price
        if spread > 0.50:
            confidence -= 0.15

    return round(ref_price, 2), num_sources, round(max(0.5, confidence), 2)


# ── Matching ─────────────────────────────────────────────────────────

def match_whiskey(
    whiskey: Whiskey,
    per_source: dict[str, dict[str, float]],
    api_names: list[str],
) -> dict | None:
    """Match a whiskey against API data.

    Returns match dict or None.
    """
    norm = normalize_for_price(whiskey.name)
    if not norm:
        return None

    # 1. Exact normalized name match
    if norm in per_source:
        sources = per_source[norm]
        ref_price, num_src, conf = compute_reference_price(sources)
        if ref_price > 0:
            return _build_match(
                whiskey, norm, "exact", 100, ref_price, num_src, conf, sources,
            )

    # 2. Fuzzy match with age compatibility
    if not HAS_RAPIDFUZZ:
        return None

    best_score = 0
    best_name = None
    prefix = norm[:4] if len(norm) >= 4 else norm
    prefix3 = norm[:3]

    for api_name in api_names:
        # Prefix filter for speed
        if api_name[:4] != prefix and api_name[:3] != prefix3:
            continue

        score = fuzz.token_sort_ratio(norm, api_name)
        _, age_penalty = ages_compatible(norm, api_name)
        score -= age_penalty

        # Reject if API name much shorter (generic entry)
        if len(norm) > 0:
            len_ratio = len(api_name) / len(norm)
            if len_ratio < 0.6:
                score -= 20

        if score > best_score:
            best_score = score
            best_name = api_name

    if best_score >= 85 and best_name and best_name in per_source:
        sources = per_source[best_name]
        ref_price, num_src, conf = compute_reference_price(sources)
        # Slightly lower confidence for fuzzy matches
        conf = round(conf * 0.95, 2)
        if ref_price > 0:
            return _build_match(
                whiskey, best_name, f"fuzzy_{best_score:.0f}",
                best_score, ref_price, num_src, conf, sources,
            )

    return None


def _build_match(
    whiskey, matched_name, method, score,
    ref_price, num_sources, confidence, sources,
) -> dict:
    db_price = whiskey.price_usd or 0
    disc_pct = (
        abs(db_price - ref_price) / ref_price * 100
        if ref_price > 0 else 0
    )
    return {
        "db_id": whiskey.id,
        "db_name": whiskey.name,
        "db_price": db_price,
        "category": whiskey.category,
        "matched_name": matched_name,
        "match_method": method,
        "match_score": score,
        "reference_price": ref_price,
        "num_sources": num_sources,
        "confidence": confidence,
        "sources": dict(sources),
        "discrepancy_pct": round(disc_pct, 1),
    }


# ── Classification ───────────────────────────────────────────────────

def classify(disc_pct: float, threshold: float) -> str:
    """Classify discrepancy: ok, minor, major, extreme."""
    pct = disc_pct / 100.0
    if pct <= 0.10:
        return "ok"
    elif pct <= threshold:
        return "minor"
    elif pct <= threshold * 2:
        return "major"
    else:
        return "extreme"


# ── Main ─────────────────────────────────────────────────────────────

def run_verify(
    fix: bool = False,
    threshold: float = 0.30,
    limit: int = 0,
    min_confidence: float = 0.75,
):
    db = SessionLocal()
    start_time = time.monotonic()

    # Load all displayed whiskeys (those with images)
    whiskeys = db.query(Whiskey).filter(
        and_(
            Whiskey.image_url.isnot(None),
            Whiskey.image_url != "",
        )
    ).order_by(Whiskey.name).all()

    if limit > 0:
        whiskeys = whiskeys[:limit]

    log.info("Loaded %d displayed whiskeys to verify", len(whiskeys))

    # Fetch all API prices
    per_source, source_counts = fetch_all_sources()
    api_names = list(per_source.keys())

    # Match each whiskey
    matches = []
    unmatched = []

    for i, w in enumerate(whiskeys):
        if i > 0 and i % 500 == 0:
            log.info("Matching: %d/%d (%.0f%%)", i, len(whiskeys),
                     100 * i / len(whiskeys))

        match = match_whiskey(w, per_source, api_names)
        if match:
            match["classification"] = classify(
                match["discrepancy_pct"], threshold,
            )
            matches.append(match)
        else:
            unmatched.append({
                "id": w.id,
                "name": w.name,
                "price": w.price_usd,
                "category": w.category,
            })

    # Tally classifications
    class_counts = defaultdict(int)
    for m in matches:
        class_counts[m["classification"]] += 1

    # Sort discrepancies by percentage (worst first)
    discrepancies = sorted(
        [m for m in matches if m["classification"] != "ok"],
        key=lambda m: m["discrepancy_pct"],
        reverse=True,
    )

    # Apply fixes if requested
    fixes_applied = 0
    protected_ids = set(PRICE_CORRECTIONS_BY_ID.keys())

    if fix and discrepancies:
        for d in discrepancies:
            if d["classification"] not in ("major", "extreme"):
                continue
            if d["db_id"] in protected_ids:
                log.debug("Skipping protected ID %d: %s", d["db_id"], d["db_name"])
                continue
            if d["confidence"] < min_confidence:
                continue
            if d["match_score"] < 85:
                continue

            # Price ratio guard: reject extreme changes with only 1 source
            # Catches false matches from year-stripping (e.g. "Balblair 1969"
            # matching generic "Balblair" at a fraction of the price)
            db_p = d["db_price"] or 0
            ref_p = d["reference_price"] or 0
            if db_p > 0 and ref_p > 0:
                ratio = max(db_p, ref_p) / min(db_p, ref_p)
                if ratio > 5.0 and d["num_sources"] < 2:
                    log.info(
                        "Skipping %s: %.1fx ratio with only %d source(s)",
                        d["db_name"], ratio, d["num_sources"],
                    )
                    d["skip_reason"] = f"ratio_{ratio:.0f}x_single_source"
                    continue

            apply_price_update(
                db, d["db_id"], d["reference_price"],
                "verification", d["confidence"],
                f"Verified against {d['num_sources']} API sources "
                f"({d['match_method']}): '{d['matched_name']}'",
                d["db_price"], dry_run=False,
            )
            d["fixed"] = True
            fixes_applied += 1

            # Batch commit
            if fixes_applied % 25 == 0:
                try:
                    db.commit()
                except Exception as exc:
                    log.error("Commit error: %s", exc)
                    db.rollback()

        # Final commit
        if fixes_applied > 0:
            try:
                db.commit()
                log.info("Applied %d price fixes", fixes_applied)
            except Exception as exc:
                log.error("Final commit error: %s", exc)
                db.rollback()

    elapsed = time.monotonic() - start_time

    # Generate report
    report = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "mode": "fix" if fix else "report",
        "threshold": threshold,
        "min_confidence": min_confidence,
        "elapsed_seconds": round(elapsed, 1),
        "api_sources": source_counts,
        "api_combined_unique": len(per_source),
        "db_summary": {
            "total_displayed": len(whiskeys),
            "matched_to_api": len(matches),
            "unmatched": len(unmatched),
            "match_rate_pct": round(
                100 * len(matches) / len(whiskeys), 1,
            ) if whiskeys else 0,
        },
        "discrepancy_summary": {
            "ok": class_counts.get("ok", 0),
            "minor": class_counts.get("minor", 0),
            "major": class_counts.get("major", 0),
            "extreme": class_counts.get("extreme", 0),
        },
        "fixes_applied": fixes_applied,
        "discrepancies": [
            {
                "id": d["db_id"],
                "name": d["db_name"],
                "category": d["category"],
                "db_price": d["db_price"],
                "reference_price": d["reference_price"],
                "discrepancy_pct": d["discrepancy_pct"],
                "classification": d["classification"],
                "match_method": d["match_method"],
                "num_sources": d["num_sources"],
                "confidence": d["confidence"],
                "sources": d["sources"],
                "fixed": d.get("fixed", False),
            }
            for d in discrepancies
        ],
    }

    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    log.info("Report saved to %s", REPORT_FILE)

    # Print human-readable summary
    print("\n" + "=" * 64)
    print("PRICE VERIFICATION REPORT")
    print("=" * 64)
    print(f"Mode:              {'FIX' if fix else 'REPORT ONLY'}")
    print(f"Threshold:         {threshold*100:.0f}%")
    print(f"Elapsed:           {elapsed:.1f}s")
    print()
    print("API Sources:")
    for src, cnt in source_counts.items():
        print(f"  {src:20s} {cnt:>5d} products")
    print(f"  {'COMBINED':20s} {len(per_source):>5d} unique")
    print()
    print(f"Displayed whiskeys:  {len(whiskeys)}")
    print(f"  Matched to API:    {len(matches)} ({report['db_summary']['match_rate_pct']}%)")
    print(f"  Unmatched:         {len(unmatched)}")
    print()
    print("Discrepancy breakdown:")
    print(f"  OK (<10%):         {class_counts.get('ok', 0)}")
    print(f"  Minor (10-{threshold*100:.0f}%):    {class_counts.get('minor', 0)}")
    print(f"  Major ({threshold*100:.0f}-{threshold*200:.0f}%):    {class_counts.get('major', 0)}")
    print(f"  Extreme (>{threshold*200:.0f}%):    {class_counts.get('extreme', 0)}")

    if fix:
        print(f"\nFixes applied:       {fixes_applied}")

    if discrepancies:
        n_show = min(20, len(discrepancies))
        print(f"\nTop {n_show} discrepancies:")
        for d in discrepancies[:n_show]:
            fixed_tag = " [FIXED]" if d.get("fixed") else ""
            print(
                f"  ${d['db_price']:>8.2f} vs ${d['reference_price']:>8.2f} "
                f"({d['discrepancy_pct']:>6.1f}%) | "
                f"{d['db_name'][:45]:45s} [{d['classification']}]{fixed_tag}"
            )
    print("=" * 64)

    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Verify whiskey prices against real retail API data",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Apply corrections for major/extreme discrepancies (default: report only)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.30,
        help="Discrepancy threshold as decimal (0.30 = 30%%)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max whiskeys to process (0 = all)",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.75,
        help="Minimum confidence to apply a fix (0.0-1.0)",
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip database backup (for --fix mode)",
    )
    args = parser.parse_args()

    if args.fix and not args.no_backup:
        backup_db()

    run_verify(
        fix=args.fix,
        threshold=args.threshold,
        limit=args.limit,
        min_confidence=args.min_confidence,
    )


if __name__ == "__main__":
    main()
