"""
Post-scrape database cleanup.

Run after scrape_all.sh finishes to:
  1. Remove non-whiskey products (gin, rum, vodka, etc.)
  2. Clean remaining name issues (repeated words, trailing junk, missing spaces)
  3. Remove near-duplicates
  4. Report stats

Usage:
    cd backend
    .venv/bin/python -m scripts.clean_db
    .venv/bin/python -m scripts.clean_db --dry-run   # preview only
"""

import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, SQLALCHEMY_DATABASE_URL
from app import models

# ── Non-whiskey detection ─────────────────────────────────────────────────

# Only flag products that are clearly NOT whiskey.
# Be conservative — false positives (removing real whiskeys) are much worse
# than false negatives (keeping a stray gin product).
#
# Words like "rum", "wine", "port", "ale", "stout", "brandy", "cognac" are
# NOT flagged because they commonly appear in whiskey names:
#   - Distilleries: Port Ellen, Port Charlotte, Port Askaig
#   - Cask finishes: Rum Cask, Wine Cask, Brandy Cask, Cognac Cask
#   - Flavor names: Rum 'n' Raisin, Caribbean Rum
# Ultra-conservative non-whiskey detection.
# Only terms that NEVER appear in legitimate whiskey names.
# Many spirits (rum, wine, port, brandy, cognac, tequila, sake, mezcal)
# appear in cask finishes, distillery names, or product names so are NOT flagged.
_NON_WHISKEY_RE = re.compile(
    r"\b(?:vodka|absinthe|soju|baijiu|grappa|vermouth|cachaca"
    r"|liqueur|creme de|cream de)\b", re.I
)

# "Gin" needs special handling — only flag if name looks like a gin product
_GIN_PRODUCT_RE = re.compile(
    r"\b(?:dry gin|london gin|scottish gin|irish gin|craft gin"
    r"|infused gin|distilled gin|small batch.*gin|gin$)\b", re.I
)


# Scraped website UI text that isn't a whiskey product
_JUNK_NAMES = {
    "whisky scoring", "subscribe", "whisky 101", "ratings", "home",
    "about", "contact", "login", "sign up", "register", "search",
    "menu", "cart", "checkout", "privacy policy", "terms of service",
    "cookie policy", "faq", "help", "blog", "news", "newsletter",
    "shop", "store", "account", "profile", "settings", "log in",
    "sign in", "my account", "wishlist", "compare",
}


def is_non_whiskey(name: str) -> bool:
    """Check if a product name indicates it's NOT whiskey.

    Ultra-conservative: only flags products that are clearly not whiskey.
    Better to keep a stray gin than to remove Port Ellen.
    """
    if _NON_WHISKEY_RE.search(name):
        return True
    if _GIN_PRODUCT_RE.search(name):
        return True
    # Exact match against known junk names from website scraping
    if name.strip().lower() in _JUNK_NAMES:
        return True
    return False


# ── Name cleaning ─────────────────────────────────────────────────────────

# Trailing bottle size descriptors
_BOTTLE_SIZES = re.compile(
    r"\s*\b(?:miniature|mini|sample|half.?bottle|magnum|jeroboam)\s*$", re.I
)

# Repeated phrase dedup: "Signatory Vintage 11Y Signatory Vintage Signatory Vintage"
def _dedup_repeated_phrases(name: str) -> str:
    """Remove consecutive repeated multi-word phrases from name.

    Only removes phrases of 2+ words that repeat at least 3 chars each.
    Conservative: only handles obvious repetitions, not partial overlaps.
    """
    words = name.split()
    if len(words) < 6:
        return name

    # Only try phrase lengths of 2-3 words, require minimum length
    for phrase_len in range(3, 1, -1):
        for i in range(len(words) - phrase_len + 1):
            phrase = " ".join(words[i:i + phrase_len])
            if len(phrase) < 6:
                continue
            # Only remove if the exact phrase appears 3+ times (clearly repeated)
            count = name.lower().count(phrase.lower())
            if count >= 3:
                # Keep first, remove all others
                parts = re.split(re.escape(phrase), name, flags=re.I)
                name = parts[0] + phrase + " ".join(parts[1:])
                name = re.sub(r"\s+", " ", name).strip()
                return name  # one fix per call
    return name


# Fix numbers glued to letters: "Macallan1851" → "Macallan 1851"
_GLUED_NUMBERS = re.compile(r"([a-z])(\d{3,})", re.I)

# Trailing junk after cleaning
_TRAILING_JUNK = re.compile(r"\s*[-,./]+\s*$")


def clean_name(name: str) -> str:
    """General-purpose name cleanup for any source."""
    # Remove repeated phrases
    name = _dedup_repeated_phrases(name)

    # Fix numbers glued to letters (but not age markers like "12Y")
    name = _GLUED_NUMBERS.sub(r"\1 \2", name)

    # Remove bottle size descriptors
    name = _BOTTLE_SIZES.sub("", name)

    # Strip stray quotes and apostrophes at boundaries
    name = re.sub(r"^['\"\s]+|['\"\s]+$", "", name)

    # Trailing junk
    name = _TRAILING_JUNK.sub("", name)

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ── Near-duplicate detection ──────────────────────────────────────────────

def _normalize_for_dedup(name: str) -> str:
    """Aggressive normalization for duplicate detection."""
    n = name.lower().strip()
    # Strip "the " prefix
    n = re.sub(r"^the\s+", "", n)
    # Normalize age: "12 year old", "12 years", "12yr", "12 y.o." → "12y"
    n = re.sub(r"(\d+)\s*(?:year[s]?\s*old|year[s]?|yr[s]?|y\.?o\.?|Y)\b", r"\1y", n)
    # Remove common suffixes
    for suffix in ["single malt scotch whisky", "single malt whisky",
                    "single malt", "scotch whisky", "whisky", "whiskey",
                    "bourbon", "blended"]:
        n = re.sub(rf"\s*{re.escape(suffix)}\s*$", "", n)
    # Remove all punctuation
    n = re.sub(r"[^a-z0-9\s]", "", n)
    # Collapse whitespace
    n = re.sub(r"\s+", " ", n).strip()
    return n


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Post-scrape DB cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't modify DB")
    args = parser.parse_args()

    # Auto-backup before destructive operations
    if not args.dry_run and SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.backup_clean_{ts}"
            shutil.copy2(db_path, backup_path)
            print(f"Backup created: {backup_path}")
        else:
            print("WARNING: DB file not found, skipping backup")

    db = SessionLocal()
    all_whiskeys = db.query(models.Whiskey).order_by(models.Whiskey.id).all()
    total_before = len(all_whiskeys)
    print(f"Total whiskeys in DB: {total_before}")
    print()

    non_whiskey_removed = 0
    names_cleaned = 0
    dupes_removed = 0
    too_short_removed = 0

    # Pass 1: Remove non-whiskey products
    print("Pass 1: Removing non-whiskey products...")
    remaining = []
    for w in all_whiskeys:
        if is_non_whiskey(w.name):
            print(f"  REMOVE [{w.source}] {w.name}")
            if not args.dry_run:
                db.delete(w)
            non_whiskey_removed += 1
        else:
            remaining.append(w)

    # Pass 2: Clean names
    print(f"\nPass 2: Cleaning names...")
    for w in remaining:
        cleaned = clean_name(w.name)
        if cleaned != w.name:
            print(f"  CLEAN [{w.source}] {w.name!r}")
            print(f"      → {cleaned!r}")
            if not args.dry_run:
                w.name = cleaned
            names_cleaned += 1

    # Pass 3: Remove too-short names
    still_remaining = []
    for w in remaining:
        name = clean_name(w.name) if args.dry_run else w.name
        if len(name) < 3:
            print(f"  SHORT [{w.source}] {w.name!r}")
            if not args.dry_run:
                db.delete(w)
            too_short_removed += 1
        else:
            still_remaining.append(w)

    # Pass 4: Remove near-duplicates (keep lowest ID = earliest added)
    print(f"\nPass 3: Removing near-duplicates...")
    seen = {}  # normalized_name → whiskey
    for w in still_remaining:
        name = clean_name(w.name) if args.dry_run else w.name
        norm = _normalize_for_dedup(name)
        if norm in seen:
            existing = seen[norm]
            print(f"  DUPE  [{w.source}] {w.name!r}")
            print(f"    of  [{existing.source}] {existing.name!r}")
            if not args.dry_run:
                db.delete(w)
            dupes_removed += 1
        else:
            seen[norm] = w

    if not args.dry_run:
        db.commit()

    total_after = total_before - non_whiskey_removed - dupes_removed - too_short_removed
    print(f"\n{'=== DRY RUN ===' if args.dry_run else '=== RESULTS ==='}")
    print(f"Before:            {total_before}")
    print(f"Non-whiskey:       -{non_whiskey_removed}")
    print(f"Names cleaned:     {names_cleaned}")
    print(f"Too short:         -{too_short_removed}")
    print(f"Dupes removed:     -{dupes_removed}")
    print(f"After:             {total_after}")

    db.close()


if __name__ == "__main__":
    main()
