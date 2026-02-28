#!/usr/bin/env bash
# ============================================================
# SipSense — Full scraper pipeline (~65-70k quality whiskeys)
#
# Usage:
#   ./scrape_all.sh          # fresh run (or resume from progress.json)
#
# Resume behavior:
#   Progress is saved to scraper/progress.json automatically.
#   If you stop the script mid-run, just run ./scrape_all.sh again
#   and it will skip completed sources and resume paginated ones
#   (distiller, whiskybase, masterofmalt, whiskyexchange) from where
#   they left off. Other sources (openfoodfacts, vinmonopolet, github)
#   are fast enough to re-run from the start — duplicates are skipped.
#
# Sources (in order):
#   1. Distiller.com      — detail page scraper, resumable by slug index
#   2. OpenFoodFacts      — whiskeys with UPC barcodes
#   3. Whiskybase         — community ratings + large catalog, resumable
#   4. Master of Malt     — UK retailer, ~20k, rich data, resumable
#   5. Whisky Exchange    — UK retailer, ~15k, resumable
#   6. Vinmonopolet       — Norway state monopoly, free JSON API
#   7. GitHub CSV         — fast top-up, instant dedup
#
# Removed:
#   - Connosr: listing pages don't show ABV; would insert fake
#     abv=43.0 for every new entry — pollutes the recommender
#   - TTB: FOIA URL dead as of Feb 2026
#   - Wikidata: entity IDs broken, only ~40 results
#
# Notes:
#   - Run sources one at a time (SQLite is single-writer)
#   - MoM and TWE use 2-4s delays; expect ~6-10 hours for full runs
# ============================================================

set -e
cd "$(dirname "$0")"

PYTHON=".venv/bin/python"

# ── helpers ─────────────────────────────────────────────────
count() {
    $PYTHON -c "
import sys; sys.path.insert(0,'.')
from app.database import SessionLocal; from app import models
db = SessionLocal()
print(db.query(models.Whiskey).count())
db.close()
" 2>/dev/null
}

separator() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "  DB total before: $(count) whiskeys"
    echo "============================================================"
    echo ""
}

# ── start ────────────────────────────────────────────────────
echo ""
echo "SipSense scraper pipeline starting at $(date '+%H:%M:%S')"
echo "Starting DB count: $(count) whiskeys"
echo "(Completed sources in progress.json will be skipped automatically)"
echo ""

# All steps pass --resume so run.py reads progress.json and skips
# sources already marked as complete.

# ── 1. Distiller ─────────────────────────────────────────────
separator "STEP 1/7: Distiller.com (resumable by slug index)"
$PYTHON -m scraper.run --source distiller --resume --limit 10000

# ── 2. OpenFoodFacts ─────────────────────────────────────────
separator "STEP 2/7: OpenFoodFacts (~3-5k whiskeys with UPC barcodes)"
$PYTHON -m scraper.run --source openfoodfacts --resume

# ── 3. Whiskybase ────────────────────────────────────────────
separator "STEP 3/7: Whiskybase.com (~20k whiskeys with community ratings)"
$PYTHON -m scraper.run --source whiskybase --resume --limit 20000

# ── 4. Master of Malt ────────────────────────────────────────
separator "STEP 4/7: Master of Malt (~20k whiskeys, rich data, 2-4s delay)"
$PYTHON -m scraper.run --source masterofmalt --resume --limit 20000

# ── 5. Whisky Exchange ───────────────────────────────────────
separator "STEP 5/7: The Whisky Exchange (~15k whiskeys, UK retailer)"
$PYTHON -m scraper.run --source whiskyexchange --resume --limit 15000

# ── 6. Vinmonopolet ──────────────────────────────────────────
separator "STEP 6/7: Vinmonopolet (~2-3k whiskeys, Norway public API)"
$PYTHON -m scraper.run --source vinmonopolet --resume

# ── 7. GitHub CSV top-up ─────────────────────────────────────
separator "STEP 7/7: GitHub CSV (top-up, fast, duplicates auto-skipped)"
$PYTHON -m scraper.run --source github --resume

# ── done ─────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  ALL DONE at $(date '+%H:%M:%S')"
echo "  Final DB count: $(count) whiskeys"
echo "============================================================"
echo ""
