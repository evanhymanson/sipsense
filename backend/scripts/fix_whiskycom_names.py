"""
One-time fix: clean dirty whisky.com names already in the database.

Removes bottle sizes, ABV percentages, German text, and trailing metadata
from whiskycom entries. Deletes entries that become duplicates after cleaning.

Usage:
    cd backend
    .venv/bin/python -m scripts.fix_whiskycom_names
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app import models

CLEAN_PATTERNS = [
    re.compile(r"\s*Whisky\.de\b.*$", re.I),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l|liter|litre)\b", re.I),
    re.compile(r"-?\s*\d{2,3}(?:\.\d+)?\s*%\s*(?:vol\.?)?\s*-?", re.I),
    re.compile(r"\s*(?:Original bottling|Other bottler|Distillery bottling)\s*\d*\.?\d*\s*$", re.I),
    re.compile(r"\s*-?\s*(?:mit|with)\s+.+$", re.I),
    re.compile(r"\s*-?\s*neues?\s+\w+.*$", re.I),
    re.compile(r"\s*-?\s*neue\s+\w+.*$", re.I),
    re.compile(r"\s*-?\s*inkl\.?\s+.*$", re.I),
    re.compile(r"\s*-?\s*new\s+\w+\s*-?\s*", re.I),
    re.compile(r"\s*-?\s*(?:Traditionally|specially)\s+\w+\s*-?\s*", re.I),
    re.compile(r"\s*[/\-]\s*(?:19|20)\d{2}\s*", re.I),
    re.compile(r"\s+(?:19|20)\d{2}\s*$"),
    re.compile(r"\s+\d\.\d\s*$"),
    re.compile(r"\s+0\s*$"),
    re.compile(r"\s*-\s*-\s*"),
    re.compile(r"^\s*[-/]\s*|\s*[-/]\s*$"),
]


def clean(name: str) -> str:
    name = re.sub(
        r"^\d{1,2}\.\s*(?:Jan|Feb|Mär|Mar|Apr|Mai|May|Jun|Jul|Aug|Sep|Okt|Oct|Nov|Dez|Dec)\s*\d{4}\s*",
        "", name, flags=re.I
    )
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = re.sub(r"(\w)/(\w)", r"\1 / \2", name)
    for pat in CLEAN_PATTERNS:
        name = pat.sub(" ", name)
    name = re.sub(r"([a-zA-Z])(\d{1,2}Y)", r"\1 \2", name)
    name = re.sub(r"(\d{1,2}Y)([A-Za-z0-9])", r"\1 \2", name)
    name = re.sub(r"\s+0\s*$", "", name)
    name = re.sub(r"\s+\d\.\d\s*$", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip("- ,./")
    return name


def main():
    db = SessionLocal()

    whiskycom = db.query(models.Whiskey).filter(
        models.Whiskey.source == "whiskycom"
    ).all()

    print(f"Found {len(whiskycom)} whiskycom entries to check")

    # Get all non-whiskycom names for cross-source dedup
    other_rows = db.query(models.Whiskey.name).filter(
        models.Whiskey.source != "whiskycom"
    ).all()
    other_names = {r.name.lower().strip() for r in other_rows}

    seen_cleaned = set()
    fixed = 0
    dupes_removed = 0

    for w in whiskycom:
        cleaned = clean(w.name)
        cleaned_lower = cleaned.lower().strip()

        if not cleaned or len(cleaned) < 3:
            db.delete(w)
            dupes_removed += 1
            continue

        # Check if this cleaned name is a dupe
        if cleaned_lower in seen_cleaned or cleaned_lower in other_names:
            db.delete(w)
            dupes_removed += 1
            continue

        seen_cleaned.add(cleaned_lower)

        if cleaned != w.name:
            old = w.name
            w.name = cleaned
            fixed += 1
            print(f"  FIX: {old!r}")
            print(f"    -> {cleaned!r}")

    db.commit()

    total_remaining = db.query(models.Whiskey).filter(
        models.Whiskey.source == "whiskycom"
    ).count()
    total_db = db.query(models.Whiskey).count()

    print()
    print(f"Fixed:         {fixed} names cleaned")
    print(f"Dupes removed: {dupes_removed}")
    print(f"Whiskycom now: {total_remaining}")
    print(f"Total DB:      {total_db}")

    db.close()


if __name__ == "__main__":
    main()
