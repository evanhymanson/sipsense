#!/usr/bin/env bash
# Download Kaggle datasets and import into SipSense DB.
# Usage: cd backend && source .venv/bin/activate && bash scraper/setup_kaggle.sh

set -euo pipefail
cd "$(dirname "$0")/.."

# Load .env
export $(grep KAGGLE_API_TOKEN .env | xargs)

pip install -q kagglehub 2>/dev/null

echo ">>> Downloading datasets..."
python3 -c "
import os, shutil, kagglehub
from pathlib import Path

os.environ.setdefault('KAGGLE_API_TOKEN', '$(grep KAGGLE_API_TOKEN .env | cut -d= -f2)')
DATA = Path('scraper/data')
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'kaggle').mkdir(exist_ok=True)
(DATA / 'wikiliq').mkdir(exist_ok=True)

datasets = [
    ('colacloud/ttb-colas-demo', DATA),
    ('limtis/wikiliq-dataset', DATA / 'wikiliq'),
    ('koki25ando/22000-scotch-whisky-reviews', DATA / 'kaggle'),
]

for ds, dest in datasets:
    print(f'  Downloading {ds}...')
    path = kagglehub.dataset_download(ds)
    # Copy CSVs to expected location
    for f in Path(path).rglob('*.csv'):
        target = dest / f.name
        if not target.exists():
            shutil.copy2(f, target)
            print(f'    -> {target}')
        else:
            print(f'    (exists) {target}')

print('Done!')
"

echo ""
echo ">>> Importing into database..."

# Find TTB CSV
TTB_FILE=$(find scraper/data -maxdepth 1 -name "*.csv" -size +1M | head -1)
if [[ -n "$TTB_FILE" ]]; then
    echo ">>> TTB COLA: $TTB_FILE"
    python3 -m scraper.run --source ttb_kaggle --ttb-file "$TTB_FILE"
fi

echo ">>> Wikiliq..."
python3 -m scraper.run --source wikiliq

echo ">>> Kaggle CSVs..."
python3 -m scraper.run --source kaggle

echo ""
python3 -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
total = db.execute(text('SELECT COUNT(*) FROM whiskeys')).scalar()
print(f'>>> Total whiskeys in DB: {total:,}')
db.close()
"
