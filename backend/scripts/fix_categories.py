"""
Fix category data in the SipSense DB.

Problems:
  - 4,147 whiskeys are categorized as 'single malt' — the app's filters don't
    recognize this. Most are Scotch; some are Japanese, Irish, or other.

Strategy:
  1. Remap by region string (Scotland / Skottland / Scottish sub-regions → scotch)
  2. Remap by known Scottish distilleries (for NULL-region single malts)
  3. Remap Japan → japanese, Ireland/Irland → irish
  4. Normalize Skottland/Scottish sub-regions into clean region names
  5. Leave USA, Norway, etc. as 'single malt' (world whisky, not a filter category yet)

Usage:
    cd backend
    python -m scripts.fix_categories [--dry-run]
"""

import argparse
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal
from app import models

# Known Scottish distilleries (used to catch NULL-region single malts)
SCOTTISH_DISTILLERIES = {
    "aberfeldy", "aberlour", "ardbeg", "ardmore", "auchentoshan", "auchroisk",
    "aultmore", "balblair", "balmenach", "balvenie", "banff", "ben nevis",
    "benriach", "benrinnes", "benromach", "blair athol", "bowmore", "braeval",
    "brora", "bruichladdich", "bunnahabhain", "caol ila", "cardhu", "clynelish",
    "craigellachie", "cragganmore", "dailuaine", "dalmore", "dalwhinnie",
    "deanston", "dufftown", "edradour", "fettercairn", "glen deveron", "glen elgin",
    "glen garioch", "glen grant", "glen keith", "glen moray", "glen ord",
    "glen scotia", "glen spey", "glenallachie", "glenburgie", "glencadam",
    "glendronach", "glendullan", "glenfarclas", "glenfiddich", "glenglassaugh",
    "glengoyne", "glenkinchie", "glenlivet", "glenlochy", "glenlossie",
    "glenmorangie", "glenrothes", "glentauchers", "glenturret", "hazelburn",
    "highland park", "imperial", "inchgower", "jura", "kilchoman", "knockando",
    "lagavulin", "laphroaig", "linkwood", "littlemill", "loch lomond",
    "longmorn", "longrow", "macallan", "the macallan", "macduff", "mannochmore",
    "millburn", "miltonduff", "mortlach", "north british", "oban",
    "pittyvaich", "port ellen", "pulteney", "roseisle", "royal brackla",
    "royal lochnagar", "scapa", "scottish leader", "speyburn", "speyside",
    "springbank", "strathisla", "strathmill", "talisker", "tamdhu", "tamnavulin",
    "teaninich", "tobermory", "tomatin", "tomintoul", "tormore", "tullibardine",
    "wolfburn",
}

SCOTTISH_REGIONS = {"scotland", "skottland", "highlands", "islay", "speyside",
                    "lowlands", "campbeltown", "orkney"}

REGION_NORMALIZE = {
    "skottland": "Scotland",
    "highlands": "Highlands",
    "islay": "Islay",
    "speyside": "Speyside",
    "lowlands": "Lowlands",
    "campbeltown": "Campbeltown",
    "orkney": "Highlands",
}

JAPANESE_REGIONS = {"japan"}
IRISH_REGIONS = {"ireland", "irland", "republic of ireland", "northern ireland"}


def is_scottish_distillery(name: str) -> bool:
    return name.lower().strip() in SCOTTISH_DISTILLERIES


def run(dry_run: bool):
    db = SessionLocal()
    counts = {"→scotch": 0, "→japanese": 0, "→irish": 0, "unchanged": 0}

    try:
        whiskeys = db.query(models.Whiskey).filter(
            models.Whiskey.category == "single malt"
        ).all()

        print(f"Found {len(whiskeys)} single malt whiskeys to evaluate\n")

        for w in whiskeys:
            region_lower = (w.region or "").lower().strip()
            distillery_lower = (w.distillery or "").lower().strip()

            if region_lower in JAPANESE_REGIONS:
                if not dry_run:
                    w.category = "japanese"
                counts["→japanese"] += 1

            elif region_lower in IRISH_REGIONS:
                if not dry_run:
                    w.category = "irish"
                counts["→irish"] += 1

            elif region_lower in SCOTTISH_REGIONS:
                if not dry_run:
                    w.category = "scotch"
                    # Normalize region name
                    normalized = REGION_NORMALIZE.get(region_lower)
                    if normalized:
                        w.region = normalized
                counts["→scotch"] += 1

            elif region_lower == "" and is_scottish_distillery(distillery_lower):
                if not dry_run:
                    w.category = "scotch"
                    w.region = "Scotland"
                counts["→scotch"] += 1

            else:
                counts["unchanged"] += 1

        if not dry_run:
            db.commit()

    finally:
        db.close()

    print("=" * 50)
    print(f"  Remapped → scotch   : {counts['→scotch']}")
    print(f"  Remapped → japanese : {counts['→japanese']}")
    print(f"  Remapped → irish    : {counts['→irish']}")
    print(f"  Left as single malt : {counts['unchanged']}")
    if dry_run:
        print("  (DRY RUN — no changes written)")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
