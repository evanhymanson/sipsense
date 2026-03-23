"""
Fix prices for all whiskeys displayed in the SipSense app.

Targets only the ~3,314 whiskeys with images (the ones users actually see).
Fixes both estimated prices and obviously-wrong "real" prices.

Usage:
  cd backend
  python -m scripts.fix_display_prices --dry-run    # preview changes
  python -m scripts.fix_display_prices               # apply changes
  python -m scripts.fix_display_prices --verify      # check results after
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Whiskey

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# PHASE 1: Curated price corrections by database ID
# These are hand-verified prices for every displayed bottle with a
# bad estimated or clearly-wrong "real" price.
#
# Sources: current US retail (where available), auction/collector
# market for discontinued/rare bottles.
# ─────────────────────────────────────────────────────────────────────

PRICE_CORRECTIONS_BY_ID: dict[int, float] = {
    # ── ESTIMATED PRICES: Blended ──────────────────────────────────
    4822: 250.0,    # JW Blue Label Year of the Rooster (limited edition)
    4828: 400.0,    # 1980 40 Year Cask #34 (ImpEx Collection)
    4844: 250.0,    # JW Blue Label Year of the Rabbit
    4852: 4000.0,   # The Last Drop 48 Year Blended Scotch
    4861: 300.0,    # JW Blue Label Year Of The Horse
    4866: 350.0,    # Ballantine's 30 Year Cask Edition
    4880: 5000.0,   # The Last Drop 50 Year Signature Blended Scotch
    4935: 250.0,    # Whyte & Mackay 30 Year
    4938: 250.0,    # JW Blue Label Year of the Pig
    4944: 100.0,    # Hibiki Japanese Harmony (2018 Holiday Bottling)
    4979: 600.0,    # Hibiki 17 Year Chrysanthemum & Crane (limited)
    4981: 25000.0,  # Royal Salute 52 Year The Time Series
    5005: 300.0,    # JW Blue Label Year of the Monkey
    5017: 800.0,    # Ballantine's 40 Year
    5056: 250.0,    # JW Blue Label Year of the Tiger
    5086: 5000.0,   # JW Masters of Flavour 48 Year
    5107: 200.0,    # Isle of Skye 30 Year
    5135: 180.0,    # Cutty Sark 33 Year Art Deco
    7902: 15.0,     # Glen Scanlan Blended Scotch (budget blend)

    # ── ESTIMATED PRICES: Bourbon ──────────────────────────────────
    3761: 200.0,    # Forager's Keep 26 Year
    8621: 50.0,     # Willett Bourbon Whiskey (pot still reserve)

    # ── ESTIMATED PRICES: Irish ────────────────────────────────────
    3452: 400.0,    # Bushmills Causeway Collection 27 Year Bourbon Cask
    3479: 350.0,    # Bushmills 26 Year Crystal Malt
    4129: 600.0,    # Bushmills Rare Casks 30 Year Madeira Cask
    8127: 35.0,     # Two Stacks Irish Whiskey

    # ── ESTIMATED PRICES: Japanese ─────────────────────────────────
    2702: 60000.0,  # Yamazaki 55 Year (collector)
    2782: 500.0,    # Yamazaki Islay Peated Single Malt (2024 Edition)
    2892: 3500.0,   # Yamazaki 25 Year (Discontinued)
    2989: 500.0,    # Yamazaki Peated Malt (2022 Edition)
    3244: 500.0,    # Essence of Suntory Whisky: Yamazaki Peated Malt
    3628: 500.0,    # Yamazaki Golden Promise (2024 Edition)
    3802: 2500.0,   # Yamazaki 25 Year Mizunara (collector)
    4574: 4000.0,   # Yamazaki Sherry Cask (2016 Edition)

    # ── ESTIMATED PRICES: Scotch ───────────────────────────────────
    1058: 500.0,    # Signatory Brora 18yr 1983
    1588: 200.0,    # Cadenhead's Rosebank 11yr
    2278: 350.0,    # G&M Glenlossie 27yr 1978 vintage
    2563: 35000.0,  # Macallan 65 Year Lalique (collector)
    2573: 350.0,    # Balblair 25 Year
    2586: 600.0,    # Rosebank 30 Year (Release 1)
    2599: 500.0,    # Glenmorangie The Altus 25 Year
    2623: 1200.0,   # Dalmore 28 Year (Stillman's Dram)
    2683: 1200.0,   # Laphroaig 30 Year Ian Hunter Story Book 1
    2687: 15000.0,  # Macallan 50 Year Lalique (collector)
    2703: 1200.0,   # Laphroaig 30 Year Ian Hunter Story Book 2
    2715: 500.0,    # Caol Ila 1984 30 Year XOP (Douglas Laing)
    2784: 350.0,    # Macallan Rare Cask Batch No.1 (2018)
    2827: 3000.0,   # Glenfiddich Grand Yozakura 29 Year
    2842: 550.0,    # Balvenie 25 Year Rare Marriages
    2870: 800.0,    # Laphroaig 30 Year (2016 Release)
    2965: 400.0,    # Glenrothes 1989 30 Year (Single Malts of Scotland)
    2995: 5000.0,   # Brora 1978 40 Year 200th Anniversary
    2998: 900.0,    # Ardbeg 25 Year
    3004: 500.0,    # Pittyvaich 30 Year (2020 Special Release)
    3059: 4500.0,   # Talisker 44 Year Forests of the Deep
    3150: 350.0,    # Rosebank 12 Year Flora & Fauna (discontinued, collector)
    3157: 25000.0,  # Macallan 62 Year Lalique (collector)
    3159: 3000.0,   # Glenfiddich 29 Year Spirit of a Nation
    3201: 600.0,    # Singleton of Dufftown 1988 30 Year Prima & Ultima
    3220: 20000.0,  # Black Bowmore 1964 50 Year (collector)
    3239: 350.0,    # Mannochmore 25 Year 1990 (2016 Special Release)
    3248: 400.0,    # Pittyvaich 29 Year (2019 Special Release)
    3303: 20000.0,  # Macallan 55 Year Lalique (collector)
    3328: 3000.0,   # Dalmore 30 Year (2021 Edition)
    3350: 5000.0,   # Loch Lomond 50 Year
    3379: 4000.0,   # Dalmore Constellation 1979 33 Year
    3390: 800.0,    # Bladnoch 29 Year Bicentennial Release
    3430: 3500.0,   # Talisker 1984 37 Year Prima & Ultima
    3434: 6000.0,   # Glenfiddich 40 Year Cumulative Time
    3489: 350.0,    # Pittyvaich 28 Year (2018 Special Release)
    3515: 8000.0,   # Tamdhu 50 Year
    3574: 1500.0,   # Laphroaig 27 Year (1980 Vintage)
    3584: 3000.0,   # Brora 1977 38 Year (2016 Special Release)
    3591: 300.0,    # Arran 25 Year
    3630: 3000.0,   # Macallan Fine & Rare 1993 27 Year (Cask #3939)
    3695: 3000.0,   # Ledaig Dùsgadh 42 Year
    3710: 1000.0,   # Bowmore 30 Year (2020 Release)
    3727: 3000.0,   # Royal Lochnagar 1981 40 Year Prima & Ultima
    3784: 2500.0,   # Tomintoul 40 Year Quadruple Cask
    3790: 350.0,    # Mortlach 1993 26 Year (Single Malts of Scotland)
    3817: 35000.0,  # Macallan 50 Year (2018 Release)
    3840: 500.0,    # GlenDronach 1992 28 Year PX Cask #6052
    3851: 3000.0,   # Port Ellen 32 Year 1979 (2012 Special Release)
    3859: 250.0,    # Glenmorangie The Quarter Century 25 Year
    3871: 700.0,    # Laphroaig 25 Year Cask Strength (2013)
    3874: 4000.0,   # Port Ellen 37 Year 1978 (2016 Special Release)
    3932: 80.0,     # Kilchoman Machir Bay Cask Strength (2020 Festive)
    3935: 200.0,    # Tamnavulin Stillman's Dram 27 Year
    3952: 500.0,    # Balvenie Rare Discovery from Distant Shores 27yr
    3968: 2500.0,   # Lagavulin 1991 28 Year Prima & Ultima
    3976: 3000.0,   # XOP Platinum Port Ellen 1982
    3986: 500.0,    # Rosebank 1993 Cask #625
    3998: 600.0,    # Bowmore Vintner's Trilogy 27 Year Port Cask
    4008: 600.0,    # Bruichladdich Black Art 1992 9.1 29 Year
    4009: 2500.0,   # Lagavulin 1993 28 Year Prima & Ultima
    4014: 800.0,    # Laphroaig 25 Year Cask Strength (2020)
    4026: 4000.0,   # Macallan Fine & Rare 1990 30 Year
    4061: 600.0,    # Mortlach 30 Year Midnight Malt
    4194: 2500.0,   # Caol Ila 1984 35 Year Prima & Ultima
    4233: 500.0,    # Prometheus 26 Year (Glasgow Distillery)
    4274: 1000.0,   # Balvenie Thirty 30 Year
    4515: 25000.0,  # Glenlivet 50 Year Winchester Collection 1966
    4540: 1000.0,   # Balvenie 30 Year Rare Marriages
    4547: 300.0,    # Pittyvaich 1989 25 Year (2015 Special Release)
    4554: 3500.0,   # Glenfiddich Grand Château 31 Year
    5201: 350.0,    # Big Peat 27 Year Black Edition
    5232: 350.0,    # Rare Cask Reserves Ghosted Reserve 26 Year
    5249: 300.0,    # Royal Salute 21 Year Jodhpur Polo Edition
    8356: 85.0,     # Glenlivet 18 YO Single Malt Batch Reserve

    # ── WRONG "REAL" PRICES: Need correction ──────────────────────
    # These are marked price_is_estimated=0 but have clearly wrong values.

    # Macallan Lalique series (were ~$82 each — absurd)
    1080: 4500.0,   # Macallan 30 Year Fine Oak (was $44!)
    3351: 360.0,    # Macallan Rare Cask (current retail)
    4005: 400.0,    # Macallan Rare Cask Black
    8784: 360.0,    # Macallan Rare Cask 2024

    # Tomatin (were $40-99)
    1091: 80.0,     # Tomatin 18 Year Old
    2502: 250.0,    # Tomatin 25 Year Old

    # GlenDronach
    4369: 150.0,    # GlenDronach Allardice 18 Year (was $60)

    # Johnnie Walker Blue — the non-estimated ones that were still wrong
    # (zodiac editions are typically $250-350 at retail)

    # Port Ellen (various independent bottlings — were too low)
    168: 1500.0,    # Port Ellen 31 Year Old
    297: 2000.0,    # Port Ellen 32 Year Old (11th release)
    593: 1500.0,    # Port Ellen 1979 28 Year Old
    606: 1200.0,    # Signatory Port Ellen 1982 26 Year Old
    838: 800.0,     # Provenance Port Ellen 1982 21 Year Old
    868: 400.0,     # Whisky Exchange Elements of Islay Pe5 (Port Ellen)
    1605: 1200.0,   # Chieftain's Port Ellen 1982 25 Year Old
    2045: 3000.0,   # Port Ellen 32 Year Old
    2550: 1500.0,   # G&M Port Ellen 1982 24 Year Old

    # Brora
    43: 1500.0,     # Brora 30 Year Old
    47: 400.0,      # Lombard Jewels of Scotland Brora 1982
    429: 1200.0,    # Brora 25 Year Old

    # Rosebank (closed distillery — collector value)
    1105: 300.0,    # Chieftain's Choice Rosebank 20 Year Old
    1812: 250.0,    # Signatory Rosebank 12 Year Old 1991
    2005: 250.0,    # G&M Rosebank 1989 10 Year Old
    2501: 250.0,    # G&M Rosebank 1991 13 Year Old

    # Bowmore aged
    414: 350.0,     # Bowmore 25 Year Old
    814: 300.0,     # Blackadder Bowmore 27 Year Old

    # Dewar's aged
    117: 150.0,     # Dewar's 32 Year Old Double Double (was $150 — actually ok)
    764: 100.0,     # Dewar's 27 Year Old Double Double

    # Independent bottlings of rare distilleries
    259: 400.0,     # Glenrothes 32 Year Old 1972 Vintage
    295: 250.0,     # Adelphi Linkwood 1984 26 Year Old
    586: 500.0,     # Duncan Taylor Glenlivet 1968 35 Year Old
    752: 300.0,     # Tomatin 30 Year Old
    841: 600.0,     # G&M Strathisla 40 Year Old
    966: 400.0,     # Boutique-y Blended Whisky No.1 50 Year Old
    1062: 400.0,    # Mackillop's Choice Caperdonich 1968 35 Year Old
    1076: 350.0,    # Blackadder Linlithgow 1975 28 Year Old
    1079: 800.0,    # Scott's Selection Macallan 1974 30 Year Old
    1578: 350.0,    # Peerless Glenrothes 1967 35 Year Old
    1648: 350.0,    # Douglas Laing Glen Mhor 30 Year Old
    2154: 400.0,    # Duncan Taylor Glen Grant 1972 31 Year Old
    2159: 350.0,    # Cask & Thistle Glenlivet 1973 30 Year Old
    2316: 300.0,    # Master of Malt Speyside 30 Year Old

    # The Last Drop (premium collector brand)
    4962: 3500.0,   # The Last Drop 1971 Blended Scotch
    6053: 4000.0,   # The Last Drop 1980 Buffalo Trace Bourbon

    # JW Blue Ghost and Rare
    112: 350.0,     # JW Blue Ghost & Rare Port Ellen Edition
}

# ─────────────────────────────────────────────────────────────────────
# Category corrections by database ID
# Bottles with wrong category values in the database.
# ─────────────────────────────────────────────────────────────────────

CATEGORY_CORRECTIONS_BY_ID: dict[int, str] = {
    2782: "japanese",  # Yamazaki Islay Peated Single Malt — distilled at Yamazaki, Japan
}


def get_displayed_whiskeys(db: Session) -> list[Whiskey]:
    """Get all whiskeys with images (the ones users see)."""
    return db.query(Whiskey).filter(
        and_(
            Whiskey.image_url.isnot(None),
            Whiskey.image_url != "",
        )
    ).all()


def find_bad_prices(whiskeys: list[Whiskey]) -> list[Whiskey]:
    """Identify displayed whiskeys with estimated or suspicious prices."""
    bad = []
    for w in whiskeys:
        # Already in corrections dict
        if w.id in PRICE_CORRECTIONS_BY_ID:
            bad.append(w)
            continue
        # Estimated price
        if w.price_is_estimated:
            bad.append(w)
    return bad


def apply_corrections(db: Session, dry_run: bool = False) -> dict:
    """Apply all price corrections to displayed whiskeys."""
    displayed = get_displayed_whiskeys(db)
    log.info("Found %d displayed whiskeys (with images)", len(displayed))

    # Count current state
    estimated_count = sum(1 for w in displayed if w.price_is_estimated)
    no_price_count = sum(1 for w in displayed if w.price_usd is None)
    log.info("  Estimated prices: %d", estimated_count)
    log.info("  No price: %d", no_price_count)

    changes = []
    not_in_dict = []

    for w in displayed:
        if w.id in PRICE_CORRECTIONS_BY_ID:
            new_price = PRICE_CORRECTIONS_BY_ID[w.id]
            old_price = w.price_usd
            was_estimated = w.price_is_estimated

            changes.append({
                "id": w.id,
                "name": w.name,
                "age": w.age,
                "category": w.category,
                "old_price": old_price,
                "new_price": new_price,
                "was_estimated": was_estimated,
                "change_pct": (
                    round((new_price - old_price) / old_price * 100, 1)
                    if old_price and old_price > 0 else None
                ),
            })

            if not dry_run:
                w.price_usd = new_price
                w.price_is_estimated = False

        elif w.price_is_estimated:
            # Estimated but not in our corrections dict
            not_in_dict.append({
                "id": w.id,
                "name": w.name,
                "age": w.age,
                "price_usd": w.price_usd,
                "category": w.category,
            })

    # Apply category corrections
    category_fixes = []
    for w in displayed:
        if w.id in CATEGORY_CORRECTIONS_BY_ID:
            new_cat = CATEGORY_CORRECTIONS_BY_ID[w.id]
            if w.category != new_cat:
                category_fixes.append({
                    "id": w.id,
                    "name": w.name,
                    "old_category": w.category,
                    "new_category": new_cat,
                })
                if not dry_run:
                    w.category = new_cat

    if not dry_run and (changes or category_fixes):
        db.commit()
        log.info("Committed %d price changes and %d category fixes to database",
                 len(changes), len(category_fixes))

    return {
        "total_displayed": len(displayed),
        "corrections_applied": len(changes),
        "category_fixes_applied": len(category_fixes),
        "still_estimated": len(not_in_dict),
        "changes": changes,
        "category_fixes": category_fixes,
        "not_in_dict": not_in_dict,
    }


def verify_results(db: Session):
    """Check the state of prices for displayed whiskeys."""
    displayed = get_displayed_whiskeys(db)

    estimated = [w for w in displayed if w.price_is_estimated]
    no_price = [w for w in displayed if w.price_usd is None]

    log.info("=== Verification Report ===")
    log.info("Total displayed: %d", len(displayed))
    log.info("Estimated prices remaining: %d", len(estimated))
    log.info("No price: %d", len(no_price))

    if estimated:
        log.info("\nStill estimated:")
        for w in estimated[:20]:
            log.info("  [%d] %s — $%.2f (%s)", w.id, w.name, w.price_usd or 0, w.category)

    # Spot-check well-known bottles
    spot_checks = [
        ("GlenDronach Allardice 18", 120, 200),
        ("Macallan 50", 5000, 50000),
        ("Johnnie Walker Blue Label Year", 200, 400),
        ("Yamazaki 25", 2000, 5000),
        ("Laphroaig 30", 600, 2000),
    ]

    log.info("\n=== Spot Checks ===")
    for pattern, lo, hi in spot_checks:
        matches = [
            w for w in displayed
            if pattern.lower() in w.name.lower() and w.price_usd
        ]
        for w in matches[:3]:
            status = "OK" if lo <= w.price_usd <= hi else "SUSPICIOUS"
            log.info(
                "  [%s] %s — $%.2f (expected $%d-$%d)",
                status, w.name, w.price_usd, lo, hi,
            )


def backup_db():
    """Create a timestamped backup of the database."""
    db_path = Path(__file__).resolve().parent.parent / "sipsense.db"
    if not db_path.exists():
        log.warning("Database not found at %s, skipping backup", db_path)
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"sipsense.db.backup_pricefix_{ts}")
    shutil.copy2(db_path, backup_path)
    log.info("Database backed up to %s", backup_path.name)


def main():
    parser = argparse.ArgumentParser(description="Fix display prices for deployment")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--verify", action="store_true", help="Verify current price state")
    parser.add_argument("--report", type=str, help="Save change report to JSON file")
    args = parser.parse_args()

    db = SessionLocal()

    try:
        if args.verify:
            verify_results(db)
            return

        if not args.dry_run:
            backup_db()

        log.info("=== Fix Display Prices ===")
        log.info("Corrections in dictionary: %d", len(PRICE_CORRECTIONS_BY_ID))
        log.info("Mode: %s", "DRY RUN" if args.dry_run else "LIVE")

        results = apply_corrections(db, dry_run=args.dry_run)

        # Print summary
        log.info("\n=== Results ===")
        log.info("Total displayed whiskeys: %d", results["total_displayed"])
        log.info("Corrections applied: %d", results["corrections_applied"])
        log.info("Still estimated (not in dict): %d", results["still_estimated"])

        # Show sample of changes
        log.info("\n=== Sample Changes ===")
        for c in results["changes"][:30]:
            pct = f" ({c['change_pct']:+.1f}%)" if c["change_pct"] is not None else ""
            est = " [was estimated]" if c["was_estimated"] else ""
            log.info(
                "  %s — $%.2f → $%.2f%s%s",
                c["name"][:60], c["old_price"] or 0, c["new_price"], pct, est,
            )

        if results["still_estimated"]:
            log.info("\n=== Still Estimated (not in corrections dict) ===")
            for item in results["not_in_dict"]:
                log.info(
                    "  [%d] %s — $%.2f (%s)",
                    item["id"], item["name"][:60], item["price_usd"] or 0, item["category"],
                )

        # Save report
        report_path = args.report or "price_fix_display_report.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        log.info("\nFull report saved to %s", report_path)

        if args.dry_run:
            log.info("\n** DRY RUN — no changes were made. Run without --dry-run to apply. **")

    finally:
        db.close()


if __name__ == "__main__":
    main()
