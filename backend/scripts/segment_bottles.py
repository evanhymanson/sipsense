"""
Remove backgrounds from bottle images using rembg (U2-Net).

Reads each image (JPG or PNG) from uploads/bottles/, removes the background,
saves as PNG with transparency, and updates the database image_url.

Usage:
    cd backend
    python -m scripts.segment_bottles              # all bottles
    python -m scripts.segment_bottles --limit 10   # first 10 only
    python -m scripts.segment_bottles --force       # re-process all (even existing PNGs)
    python -m scripts.segment_bottles --cleanup     # delete source JPGs after conversion

Notes:
    - Safe to interrupt and re-run; already-segmented images are skipped.
    - Processes ~1-3 seconds per image.
    - The U2-Net model (~170 MB) downloads automatically on first run.
    - Works on both JPG sources (old) and PNG sources (from fetch script).
    - Use --force to re-segment images that were fetched with rembg already.
"""

import argparse
import os
import sys

# Allow running as  python -m scripts.segment_bottles  from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from rembg import remove
from tqdm import tqdm

from app.database import SessionLocal
from app import models

BOTTLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "uploads", "bottles")
)


def _find_source(basename):
    """Return the path to the source image (JPG or PNG), or None."""
    for ext in (".jpg", ".jpeg", ".png"):
        path = os.path.join(BOTTLES_DIR, f"{basename}{ext}")
        if os.path.exists(path):
            return path
    return None


def process_bottle(whiskey, *, force=False, cleanup=False):
    """Process a single bottle image.  Returns 'processed', 'skipped', or 'failed'."""
    if not whiskey.image_url:
        return "skipped"

    basename = os.path.splitext(os.path.basename(whiskey.image_url))[0]
    png_path = os.path.join(BOTTLES_DIR, f"{basename}.png")
    new_url = f"/uploads/bottles/{basename}.png"

    # Already done?  (skip unless --force)
    if not force and os.path.exists(png_path) and whiskey.image_url.endswith(".png"):
        return "skipped"

    source_path = _find_source(basename)
    if not source_path:
        return "skipped"

    try:
        input_img = Image.open(source_path).convert("RGBA")
        output_img = remove(input_img)

        # Write to a temp path then rename, so we don't corrupt if interrupted
        tmp_path = png_path + ".tmp"
        output_img.save(tmp_path, "PNG", optimize=True)
        os.replace(tmp_path, png_path)

        whiskey.image_url = new_url

        # Clean up source JPG if requested (never delete the PNG we just wrote)
        if cleanup and source_path != png_path and os.path.exists(source_path):
            os.remove(source_path)

        return "processed"
    except Exception as exc:
        tqdm.write(f"  ERROR ({whiskey.name}): {exc}")
        return "failed"


def main():
    parser = argparse.ArgumentParser(description="Segment bottle images (remove backgrounds)")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N bottles")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N bottles")
    parser.add_argument("--force", action="store_true", help="Re-process even if PNG exists")
    parser.add_argument("--cleanup", action="store_true", help="Delete source JPG after conversion")
    parser.add_argument("--category", type=str, default="", help="Filter by whiskey category")
    args = parser.parse_args()

    os.makedirs(BOTTLES_DIR, exist_ok=True)

    db = SessionLocal()
    try:
        query = db.query(models.Whiskey).filter(models.Whiskey.image_url.isnot(None))
        if args.category:
            query = query.filter(models.Whiskey.category == args.category)
        query = query.order_by(models.Whiskey.id)

        whiskeys = query.all()

        if args.offset:
            whiskeys = whiskeys[args.offset:]
        if args.limit:
            whiskeys = whiskeys[: args.limit]

        counts = {"processed": 0, "skipped": 0, "failed": 0}

        for w in tqdm(whiskeys, desc="Segmenting bottles"):
            result = process_bottle(w, force=args.force, cleanup=args.cleanup)
            counts[result] += 1
            # Commit after each success so progress survives interruption
            if result == "processed":
                db.commit()

        # Final commit for any remaining DB-only updates (skipped but URL fixed)
        db.commit()

        print(f"\nDone!  processed={counts['processed']}  "
              f"skipped={counts['skipped']}  failed={counts['failed']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
