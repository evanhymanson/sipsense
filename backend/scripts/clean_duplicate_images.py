"""
Clean bottle images by removing duplicates and age mismatches.

Phase 1: Deduplicate by MD5 hash
  - Groups of 10+: clear ALL (generic distillery photos)
  - Groups of 2-9: keep best filename match, clear rest
  - Groups of 1: leave alone

Phase 2: Age mismatch cleanup
  - Compare age in whiskey name vs age in filename
  - Clear images where they disagree

Usage:
    cd backend
    .venv/bin/python -m scripts.clean_duplicate_images           # dry run
    .venv/bin/python -m scripts.clean_duplicate_images --fix      # apply changes
"""

import os
import sys
import re
import hashlib
import argparse
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app import models


def slugify(text: str) -> str:
    """Match the slugify used in fetch_bottle_images.py"""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def extract_age(text: str) -> int | None:
    """Extract age statement from a whiskey name or filename."""
    # Try "N year", "N yr", "N yo", "Ny" patterns
    m = re.search(r'(\d{1,2})\s*(?:year|yr|yo|y\b|-year)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Try "aged N" pattern
    m = re.search(r'aged\s+(\d{1,2})', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def name_similarity(whiskey_name: str, filename: str) -> float:
    """Score how well a whiskey name matches a filename (0.0 - 1.0)."""
    name_slug = slugify(whiskey_name)
    # Remove extension
    fname = filename.rsplit(".", 1)[0] if "." in filename else filename

    name_words = set(name_slug.split("-"))
    file_words = set(fname.split("-"))

    # Remove very short words
    name_words = {w for w in name_words if len(w) >= 3}
    file_words = {w for w in file_words if len(w) >= 3}

    if not name_words:
        return 0.0

    overlap = name_words & file_words
    return len(overlap) / len(name_words)


def phase1_dedup(db, fix: bool) -> tuple[int, int]:
    """Deduplicate images by MD5 hash."""
    whiskeys = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != "")
        .all()
    )

    # Group by file content hash
    hash_to_whiskeys: dict[str, list] = defaultdict(list)
    for w in whiskeys:
        path = w.image_url.lstrip("/")
        if os.path.exists(path):
            h = hashlib.md5(open(path, "rb").read()).hexdigest()
            hash_to_whiskeys[h].append(w)

    cleared = 0
    deleted_files = set()
    groups_cleared = 0

    for h, ws in hash_to_whiskeys.items():
        if len(ws) <= 1:
            continue

        groups_cleared += 1

        if len(ws) >= 10:
            # Large groups: clear ALL — generic distillery photos
            for w in ws:
                path = w.image_url.lstrip("/")
                if fix:
                    w.image_url = None
                    deleted_files.add(path)
                cleared += 1
        else:
            # Small groups (2-9): keep the best filename match
            filename = os.path.basename(ws[0].image_url)
            best_w = max(ws, key=lambda w: name_similarity(w.name, filename))

            for w in ws:
                if w.id != best_w.id:
                    path = w.image_url.lstrip("/")
                    if fix:
                        w.image_url = None
                        deleted_files.add(path)
                    cleared += 1

    if fix:
        db.commit()
        # Delete orphaned files
        for path in deleted_files:
            # Only delete if no other whiskey references this path
            still_used = (
                db.query(models.Whiskey)
                .filter(models.Whiskey.image_url.like(f"%{os.path.basename(path)}%"))
                .count()
            )
            if still_used == 0 and os.path.exists(path):
                os.remove(path)

    return cleared, groups_cleared


def phase2_age_mismatch(db, fix: bool) -> int:
    """Clear images where filename age doesn't match whiskey name age."""
    whiskeys = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != "")
        .all()
    )

    cleared = 0
    for w in whiskeys:
        name_age = extract_age(w.name)
        if name_age is None:
            continue

        filename = os.path.basename(w.image_url)
        file_age = extract_age(filename)
        if file_age is None:
            continue

        if name_age != file_age:
            if fix:
                path = w.image_url.lstrip("/")
                w.image_url = None
                if os.path.exists(path):
                    # Check if another whiskey uses this file
                    still_used = (
                        db.query(models.Whiskey)
                        .filter(
                            models.Whiskey.image_url.like(
                                f"%{os.path.basename(path)}%"
                            ),
                            models.Whiskey.id != w.id,
                        )
                        .count()
                    )
                    if still_used == 0:
                        os.remove(path)
            cleared += 1

    if fix:
        db.commit()
    return cleared


def main():
    parser = argparse.ArgumentParser(description="Clean duplicate & mismatched bottle images")
    parser.add_argument("--fix", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    mode = "FIXING" if args.fix else "DRY RUN"
    print(f"{'='*60}")
    print(f"BOTTLE IMAGE CLEANUP ({mode})")
    print(f"{'='*60}\n")

    db = SessionLocal()

    # Pre-counts
    total = db.query(models.Whiskey).count()
    with_img = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != "")
        .count()
    )
    print(f"Before cleanup:")
    print(f"  Total whiskeys: {total}")
    print(f"  With images: {with_img}")
    print(f"  Without images: {total - with_img}\n")

    # Phase 1: Dedup
    print(f"--- Phase 1: Deduplicate by file content ---")
    cleared1, groups1 = phase1_dedup(db, args.fix)
    print(f"  Duplicate groups found: {groups1}")
    print(f"  Images to clear: {cleared1}\n")

    # Phase 2: Age mismatch
    print(f"--- Phase 2: Age mismatch cleanup ---")
    cleared2 = phase2_age_mismatch(db, args.fix)
    print(f"  Age mismatches found: {cleared2}\n")

    # Post-counts
    if args.fix:
        with_img_after = (
            db.query(models.Whiskey)
            .filter(
                models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != ""
            )
            .count()
        )
        on_disk = len(os.listdir("uploads/bottles"))
        print(f"After cleanup:")
        print(f"  With images: {with_img_after}")
        print(f"  Files on disk: {on_disk}")
        print(f"  Total cleared: {cleared1 + cleared2}")
    else:
        print(f"Total would clear: {cleared1 + cleared2}")
        print(f"Run with --fix to apply changes.")

    db.close()


if __name__ == "__main__":
    main()
