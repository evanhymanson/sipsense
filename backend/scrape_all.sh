#!/usr/bin/env bash
# ============================================================
# SipSense — Full scraper pipeline (target: 250k whiskeys)
#
# Usage:
#   ./scrape_all.sh          # fresh run (or resume from progress.json)
#
# Resume behavior:
#   Progress is saved to scraper/progress.json automatically.
#   If you stop the script mid-run, just run ./scrape_all.sh again
#   and it will skip completed sources and resume paginated ones
#   from where they left off. Duplicates are always skipped.
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

breakdown() {
    $PYTHON -c "
import sys; sys.path.insert(0,'.')
from sqlalchemy import func
from app.database import SessionLocal; from app import models
db = SessionLocal()
rows = db.query(models.Whiskey.source, func.count()).group_by(models.Whiskey.source).all()
for src, cnt in sorted(rows, key=lambda x: -x[1]):
    print(f'    {src}: {cnt:,}')
db.close()
" 2>/dev/null
}

elapsed() {
    local end=$(date +%s)
    local dur=$((end - START_TIME))
    local hrs=$((dur / 3600))
    local mins=$(((dur % 3600) / 60))
    local secs=$((dur % 60))
    echo "${hrs}h ${mins}m ${secs}s"
}

step_elapsed() {
    local end=$(date +%s)
    local dur=$((end - STEP_START))
    local mins=$((dur / 60))
    local secs=$((dur % 60))
    echo "${mins}m ${secs}s"
}

separator() {
    local before=$(count)
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "------------------------------------------------------------"
    echo "  DB before this step:  $before whiskeys"
    echo "  Total elapsed:        $(elapsed)"
    echo "  Time now:             $(date '+%H:%M:%S')"
    echo "============================================================"
    echo ""
    STEP_START=$(date +%s)
    BEFORE_COUNT=$before
}

step_done() {
    local after=$(count)
    local added=$((after - BEFORE_COUNT))
    echo ""
    echo "  >> Step complete in $(step_elapsed)"
    echo "  >> Added $added new whiskeys (total now: $after)"
    echo ""
}

progress_bar() {
    local current=$(count)
    local target=250000
    local pct=$((current * 100 / target))
    local filled=$((pct / 2))
    local empty=$((50 - filled))
    printf "  Progress: ["
    printf "%${filled}s" | tr ' ' '#'
    printf "%${empty}s" | tr ' ' '-'
    printf "] %d%% (%s / %s)\n" "$pct" "$current" "$target"
}

# ── start ────────────────────────────────────────────────────
START_TIME=$(date +%s)
STEP_START=$START_TIME
BEFORE_COUNT=0
echo ""
echo "============================================================"
echo "  SipSense Scraper Pipeline"
echo "  Started:  $(date '+%Y-%m-%d %H:%M:%S')"
echo "  DB count: $(count) whiskeys"
echo "  Target:   250,000 whiskeys"
echo "============================================================"
progress_bar
echo ""
echo "  (Completed sources in progress.json will be skipped)"
echo ""

# ════════════════════════════════════════════════════════════
#  PHASE 1: Quick wins (CSV imports, no scraping needed)
# ════════════════════════════════════════════════════════════

separator "PHASE 1 — STEP 1/12: GitHub CSV (~2,636 whiskeys, ~5s)"
$PYTHON -m scraper.run --source github --resume
step_done

separator "PHASE 1 — STEP 2/12: Kaggle CSV datasets (~2,500 whiskeys)"
if [ -d "scraper/data/kaggle" ] && [ "$(ls -A scraper/data/kaggle 2>/dev/null)" ]; then
    $PYTHON -m scraper.run --source kaggle --resume --kaggle-dir scraper/data/kaggle
    step_done
else
    echo "  !! SKIPPED — No Kaggle CSVs found in scraper/data/kaggle/"
    echo "  !! Download datasets from Kaggle and place CSVs in that directory:"
    echo "  !!   - koki25ando/22000-scotch-whisky-reviews"
    echo "  !!   - shivd24coder/wiskey-price-dataset"
    echo "  !!   - avis02/meta-critic-whisky-database"
    echo ""
fi

separator "PHASE 1 — STEP 3/12: TTB COLA Kaggle demo (~5-10k whiskeys)"
TTB_FILE="${TTB_FILE:-scraper/data/ttb-colas-demo.csv}"
if [ -f "$TTB_FILE" ]; then
    $PYTHON -m scraper.run --source ttb_kaggle --resume --ttb-file "$TTB_FILE"
    step_done
else
    echo "  !! SKIPPED — TTB file not found at $TTB_FILE"
    echo "  !! Download from: https://www.kaggle.com/datasets/colacloud/ttb-colas-demo"
    echo "  !! Place CSV at: scraper/data/ttb-colas-demo.csv"
    echo "  !! Or set: TTB_FILE=/path/to/file.csv ./scrape_all.sh"
    echo ""
fi

echo ""
echo "  ---- Phase 1 complete ----"
progress_bar
echo ""

# ════════════════════════════════════════════════════════════
#  PHASE 2: Resume existing scrapers
# ════════════════════════════════════════════════════════════

separator "PHASE 2 — STEP 4/12: Distiller.com (resume, ~2-3k remaining)"
$PYTHON -m scraper.run --source distiller --resume --limit 10000
step_done

echo ""
echo "  ---- Phase 2 complete ----"
progress_bar
echo ""

# ════════════════════════════════════════════════════════════
#  PHASE 3: Major volume sources (slow, resumable)
# ════════════════════════════════════════════════════════════

separator "PHASE 3 — STEP 5/12: Whisky.com (~41k bottles, ~30 hours)"
echo "  (This is the big one — safe to Ctrl+C and resume later)"
$PYTHON -m scraper.run --source whiskycom --resume --limit 50000
step_done
progress_bar

separator "PHASE 3 — STEP 6/12: TTB COLA Online Registry (~15-40k whiskeys)"
echo "  (Government site — using conservative 3-5s delays)"
$PYTHON -m scraper.run --source ttb_online --resume --limit 100000
step_done
progress_bar

separator "PHASE 3 — STEP 7/12: Whisky Advocate (~7k expert reviews)"
$PYTHON -m scraper.run --source whiskyadvocate --resume --limit 10000
step_done

echo ""
echo "  ---- Phase 3 complete ----"
progress_bar
echo ""

# ════════════════════════════════════════════════════════════
#  PHASE 4: API sources
# ════════════════════════════════════════════════════════════

separator "PHASE 4 — STEP 8/12: OpenFoodFacts (~3-5k with UPC barcodes)"
$PYTHON -m scraper.run --source openfoodfacts --resume
step_done

separator "PHASE 4 — STEP 9/12: Vinmonopolet (~2-3k, Norway API)"
$PYTHON -m scraper.run --source vinmonopolet --resume
step_done

echo ""
echo "  ---- Phase 4 complete ----"
progress_bar
echo ""

# ════════════════════════════════════════════════════════════
#  PHASE 5: Blocked sources (need Playwright — will auto-skip)
# ════════════════════════════════════════════════════════════

separator "PHASE 5 — STEP 10/12: Whiskybase (~220k, needs Playwright)"
$PYTHON -m scraper.run --source whiskybase --resume --limit 250000
step_done

separator "PHASE 5 — STEP 11/12: Master of Malt (~20k, needs Playwright)"
$PYTHON -m scraper.run --source masterofmalt --resume --limit 25000
step_done

separator "PHASE 5 — STEP 12/12: Whisky Exchange (~15k, needs Playwright)"
$PYTHON -m scraper.run --source whiskyexchange --resume --limit 20000
step_done

# ════════════════════════════════════════════════════════════
#  DONE
# ════════════════════════════════════════════════════════════
echo ""
echo "============================================================"
echo "  ALL DONE!"
echo "------------------------------------------------------------"
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Elapsed:  $(elapsed)"
echo "  Final DB: $(count) whiskeys"
echo ""
progress_bar
echo ""
echo "  Breakdown by source:"
breakdown
echo ""
echo "  To resume if interrupted: ./scrape_all.sh"
echo "============================================================"
echo ""
