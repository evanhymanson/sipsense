"""
Data quality fix script for SipSense DB.

Issues found:
  1. age=51 on 1,798 entries (IDs 5304-7107) — scraper bug, not real age
     Fix: re-extract age from name; null out if can't parse.
  2. ABV < 35 on some OpenFoodFacts entries — wrong parse (some legit for flavored)
     Fix: null out ABV that is clearly impossible (< 20 or > 80) — leave edge cases.
  3. Descriptions ending '...' — truncated scrapes
     Fix: already handled at runtime by blurb endpoint; optionally null them here
     so the blurb endpoint regenerates them proactively.

Usage:
    cd backend
    .venv/bin/python -m scripts.fix_data_quality [--dry-run]
"""

import re
import sys
import argparse

sys.path.insert(0, ".")
from app.database import SessionLocal
from app import models

# ── Helpers ────────────────────────────────────────────────────────────────

def extract_age_from_name(name: str):
    """Pull the first plausible age (1-50) from the whiskey name."""
    m = re.search(r"\b(\d{1,2})\s*(?:year|yr|yo)\b", name, re.I)
    if m:
        age = int(m.group(1))
        if 1 <= age <= 50:
            return age
    return None


def run(dry_run: bool):
    db = SessionLocal()
    fixed_age = 0
    nulled_age = 0
    fixed_abv = 0
    nulled_desc = 0

    try:
        whiskeys = db.query(models.Whiskey).all()

        for w in whiskeys:

            # ── Fix age=51 bug ─────────────────────────────────────────
            if w.age == 51:
                real_age = extract_age_from_name(w.name)
                if real_age:
                    if not dry_run:
                        w.age = real_age
                    print(f"  [AGE FIX]  id={w.id}  '{w.name}'  51 → {real_age}")
                    fixed_age += 1
                else:
                    if not dry_run:
                        w.age = None
                    print(f"  [AGE NULL] id={w.id}  '{w.name}'  51 → NULL")
                    nulled_age += 1

            # ── Delete entries with clearly impossible ABV ──────────────
            # abv is NOT NULL in schema, so we delete rather than null.
            # Below 20% or above 80% can't be a real whiskey.
            if w.abv is not None and (w.abv < 20.0 or w.abv > 80.0):
                print(f"  [ABV DEL]  id={w.id}  '{w.name}'  abv={w.abv} → DELETED")
                if not dry_run:
                    db.delete(w)
                fixed_abv += 1
                continue

            # ── Null truncated descriptions so blurb endpoint regenerates ──
            if w.description and w.description.strip().endswith(("...", "…")):
                if not dry_run:
                    w.description = None
                nulled_desc += 1

        if not dry_run:
            db.commit()

    finally:
        db.close()

    print()
    print("=" * 50)
    print(f"  age fixed from name : {fixed_age}")
    print(f"  age nulled          : {nulled_age}")
    print(f"  abv nulled          : {fixed_abv}")
    print(f"  descriptions cleared: {nulled_desc}")
    if dry_run:
        print("  (DRY RUN — no changes written)")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
