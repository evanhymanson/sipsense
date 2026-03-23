#!/usr/bin/env bash
# Seeds the staging database with badge definitions and sample data.
# Run after starting staging for the first time.
set -euo pipefail

echo "Seeding staging database..."
docker compose -f docker-compose.yml -f docker-compose.staging.yml exec backend \
    python -c "
from app.database import SessionLocal, engine, Base
from app import models
from app.badges import seed_badges

Base.metadata.create_all(bind=engine)
db = SessionLocal()
seed_badges(db)
db.close()
print('Staging database seeded successfully.')
"
