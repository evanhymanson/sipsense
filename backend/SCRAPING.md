# Scraping & Database Commands

## Run all scrapers
```bash
cd backend && ./scrape_all.sh
```
Resumes automatically from where it left off (progress saved in `scraper/progress.json`).

## Post-scrape cleanup
Run after scraping finishes to remove non-whiskey products, clean names, and deduplicate:
```bash
cd backend
.venv/bin/python -m scripts.clean_db --dry-run   # preview changes
.venv/bin/python -m scripts.clean_db              # apply changes
```

## Fix whiskycom names specifically
```bash
cd backend
.venv/bin/python -m scripts.fix_whiskycom_names
```

## Fetch bottle images
```bash
cd backend
.venv/bin/python -m scripts.fetch_bottle_images                    # all whiskeys
.venv/bin/python -m scripts.fetch_bottle_images --source whiskycom  # whiskycom only
.venv/bin/python -m scripts.fetch_bottle_images --source whiskycom --overwrite  # re-fetch
.venv/bin/python -m scripts.fetch_bottle_images --limit 50         # first 50 only
.venv/bin/python -m scripts.fetch_bottle_images --category bourbon # by category
```

## Check database stats
```bash
cd backend && .venv/bin/python -c "
from app.database import SessionLocal
from app import models
from sqlalchemy import func
db = SessionLocal()
total = db.query(models.Whiskey).count()
print(f'Total: {total}')
for s, c in db.query(models.Whiskey.source, func.count()).group_by(models.Whiskey.source).order_by(func.count().desc()).all():
    print(f'  {s}: {c}')
db.close()
"
```

## Reset a source and re-scrape
```bash
cd backend && .venv/bin/python -c "
from app.database import SessionLocal; from app import models
import json; from pathlib import Path
db = SessionLocal()
db.query(models.Whiskey).filter(models.Whiskey.source == 'SOURCE_NAME').delete()
db.commit(); db.close()
p = Path('scraper/progress.json')
prog = json.loads(p.read_text())
if 'SOURCE_NAME' in prog.get('completed_sources', []): prog['completed_sources'].remove('SOURCE_NAME')
p.write_text(json.dumps(prog, indent=2))
"
```
Replace `SOURCE_NAME` with: `whiskycom`, `openfoodfacts`, `vinmonopolet`, `distiller`, etc.

## Run Whiskybase scraper (Playwright, ~220K whiskeys)
Requires Playwright + Chromium. Install once:
```bash
cd backend
.venv/bin/pip install playwright>=1.40.0
.venv/bin/playwright install chromium
```
Run:
```bash
cd backend
.venv/bin/python -m scraper.run --source whiskybase --resume            # full run (~2-3 hours)
.venv/bin/python -m scraper.run --source whiskybase --limit 100 --dry-run  # test first
```

## Recommended order
1. `./scrape_all.sh` — scrape all HTTP sources
2. `.venv/bin/python -m scraper.run --source whiskybase --resume` — Playwright source (~220K)
3. `.venv/bin/python -m scripts.clean_db` — cleanup
4. `.venv/bin/python -m scripts.fetch_bottle_images` — images
