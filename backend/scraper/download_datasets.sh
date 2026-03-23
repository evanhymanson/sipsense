#!/usr/bin/env bash
#
# Download free whiskey datasets for SipSense.
#
# Requires: Kaggle CLI (pip install kaggle) + API key (~/.kaggle/kaggle.json)
#   OR: manual download from the URLs below.
#
# Usage:
#   cd backend
#   bash scraper/download_datasets.sh

set -euo pipefail

DATA_DIR="$(dirname "$0")/data"
echo ">>> Downloading datasets to: $DATA_DIR"

# ─── TTB COLA Demo (biggest dataset: ~5-10K whiskeys) ────────────────────
TTB_DIR="$DATA_DIR"
echo ""
echo ">>> [1/3] TTB COLA Demo dataset (~94MB CSV, ~5-10K unique whiskeys)"
if [[ -f "$TTB_DIR/ttb-colas-demo.csv" ]]; then
    echo "    Already exists, skipping."
else
    if command -v kaggle &>/dev/null; then
        echo "    Downloading via Kaggle CLI..."
        kaggle datasets download -d colacloud/ttb-colas-demo -p "$TTB_DIR" --unzip
        # Rename if needed
        if [[ -f "$TTB_DIR/colas.csv" ]] && [[ ! -f "$TTB_DIR/ttb-colas-demo.csv" ]]; then
            mv "$TTB_DIR/colas.csv" "$TTB_DIR/ttb-colas-demo.csv"
        fi
    else
        echo "    Kaggle CLI not found. Download manually:"
        echo "    1. Go to: https://www.kaggle.com/datasets/colacloud/ttb-colas-demo"
        echo "    2. Download and unzip to: $TTB_DIR/"
        echo "    3. Rename the CSV to: ttb-colas-demo.csv"
    fi
fi

# ─── Wikiliq (liquor ratings: ~2-5K whiskeys) ────────────────────────────
WIKILIQ_DIR="$DATA_DIR/wikiliq"
echo ""
echo ">>> [2/3] Wikiliq dataset (~6.5MB, ~2-5K whiskeys with ratings)"
mkdir -p "$WIKILIQ_DIR"
if ls "$WIKILIQ_DIR"/*.csv 1>/dev/null 2>&1; then
    echo "    Already exists, skipping."
else
    if command -v kaggle &>/dev/null; then
        echo "    Downloading via Kaggle CLI..."
        kaggle datasets download -d limtis/wikiliq-dataset -p "$WIKILIQ_DIR" --unzip
    else
        echo "    Kaggle CLI not found. Download manually:"
        echo "    1. Go to: https://www.kaggle.com/datasets/limtis/wikiliq-dataset"
        echo "    2. Download and unzip to: $WIKILIQ_DIR/"
    fi
fi

# ─── Kaggle Scotch Reviews (~2.2K entries) ────────────────────────────────
KAGGLE_DIR="$DATA_DIR/kaggle"
echo ""
echo ">>> [3/3] Kaggle scotch/whiskey review datasets"
mkdir -p "$KAGGLE_DIR"
if ls "$KAGGLE_DIR"/*.csv 1>/dev/null 2>&1; then
    echo "    Already exists, skipping."
else
    if command -v kaggle &>/dev/null; then
        echo "    Downloading via Kaggle CLI..."
        kaggle datasets download -d koki25ando/22000-scotch-whisky-reviews -p "$KAGGLE_DIR" --unzip
    else
        echo "    Kaggle CLI not found. Download manually:"
        echo "    1. Go to: https://www.kaggle.com/datasets/koki25ando/22000-scotch-whisky-reviews"
        echo "    2. Download and unzip to: $KAGGLE_DIR/"
    fi
fi

echo ""
echo ">>> Download complete! Now run the scrapers:"
echo "  python3 -m scraper.run --source ttb_kaggle"
echo "  python3 -m scraper.run --source wikiliq"
echo "  python3 -m scraper.run --source kaggle"
echo ""
echo ">>> Or run all new sources at once:"
echo "  python3 -m scraper.run --source ttb_kaggle && python3 -m scraper.run --source wikiliq && python3 -m scraper.run --source kaggle"
