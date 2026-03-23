"""
Missouri Solicitor Product List importer.

Uses the Missouri Open Data SODA API — free, no auth required.
Endpoint: https://data.mo.gov/resource/gfq7-aa86.json

4,613 unique whiskey brand names from licensed Missouri distributors.
Fields: brand_name, licensee_name (producer), wholesaler info.
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://data.mo.gov/resource/gfq7-aa86.json"

WHISKEY_FILTER = (
    "type='Liquor' AND ("
    "brand_name like '%WHISK%' OR "
    "brand_name like '%BOURBON%' OR "
    "brand_name like '%SCOTCH%' OR "
    "brand_name like '%RYE%' OR "
    "brand_name like '%MALT%' OR "
    "brand_name like '%TENNESSEE%'"
    ")"
)

# Patterns to strip from brand names
STRIP_PATTERNS = [
    r"\s*\d+\s*ML\b",
    r"\s*\d+(\.\d+)?\s*L\b",
    r"\s*\d+\s*PK\b",
    r"\s*\bW/?GLASS(ES)?\b",
    r"\s*\bGFT\s*(SET|PK|PACK)\b",
    r"\s*\bVAP\b",
    r"\s*\bCOMBO\b",
    r"\s*\bTIN\b$",
]

# Non-whiskey keywords to filter out
EXCLUDE_KEYWORDS = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "sake", "liqueur", "absinthe", "schnapps",
    "wine", "beer", "cider", "vermouth", "bitters",
    "cream", "coffee", "chocolate", "sauce",
]


def _clean_name(raw: str) -> str:
    """Clean brand name."""
    name = raw.strip()
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    if name == name.upper() and len(name) > 3:
        name = name.title()
    return name


def _is_whiskey(name: str) -> bool:
    """Verify the product is actually a whiskey."""
    name_lower = name.lower()
    # Must have a whiskey signal
    whiskey_signals = [
        "whisky", "whiskey", "bourbon", "scotch", "rye",
        "malt", "tennessee", "corn whisk",
    ]
    if not any(s in name_lower for s in whiskey_signals):
        return False
    # Must not be a non-whiskey product
    if any(s in name_lower for s in EXCLUDE_KEYWORDS):
        return False
    return True


def _infer_category(name: str) -> str:
    """Infer category from brand name."""
    n = name.lower()
    if "bourbon" in n:
        return "bourbon"
    if "single malt" in n:
        return "single malt"
    if "scotch" in n:
        return "scotch"
    if "irish" in n:
        return "irish"
    if "japanese" in n or "japan" in n:
        return "japanese"
    if "rye" in n:
        return "rye"
    if "canadian" in n:
        return "canadian"
    if "tennessee" in n:
        return "tennessee"
    if "corn" in n:
        return "corn"
    if "blended" in n:
        return "blended"
    return "whiskey"


def _extract_distillery(name: str, licensee: str) -> str:
    """Extract distillery from licensee or product name."""
    if licensee:
        clean = licensee.strip()
        # Remove common suffixes
        for suffix in [" LLC", " INC", " LTD", " CO", " CORP", " COMPANY"]:
            if clean.upper().endswith(suffix):
                clean = clean[:-len(suffix)]
        if clean == clean.upper():
            clean = clean.title()
        return clean.strip()
    words = name.split()
    return " ".join(words[:min(2, len(words))])


def iter_missouri_whiskeys(limit: int = 50000):
    """
    Fetch unique whiskey brand names from Missouri open data.
    Yields normalized whiskey dicts.
    """
    log.info("Fetching Missouri liquor brand data...")
    seen_names = set()
    total_fetched = 0

    with httpx.Client(timeout=30) as client:
        offset = 0
        page_size = 5000

        while offset < limit:
            params = {
                "$select": "distinct brand_name, licensee_name",
                "$where": WHISKEY_FILTER,
                "$limit": page_size,
                "$offset": offset,
                "$order": "brand_name",
            }
            try:
                resp = client.get(ENDPOINT, params=params)
                resp.raise_for_status()
                rows = resp.json()
            except Exception as exc:
                log.error("Missouri API error at offset %d: %s", offset, exc)
                break

            if not rows:
                break

            total_fetched += len(rows)

            for row in rows:
                raw_name = row.get("brand_name", "").strip()
                if not raw_name or len(raw_name) < 3:
                    continue

                if not _is_whiskey(raw_name):
                    continue

                name = _clean_name(raw_name)
                if not name or len(name) < 3:
                    continue

                name_key = name.lower()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                licensee = row.get("licensee_name", "")
                category = _infer_category(name)

                yield {
                    "name": name,
                    "distillery": _extract_distillery(name, licensee),
                    "category": category,
                    "region": None,
                    "abv": 40.0,  # no ABV data in Missouri dataset
                    "source": "missouri_liquor",
                }

            log.info("  Missouri: fetched %d rows (offset=%d), %d unique so far",
                     len(rows), offset, len(seen_names))
            offset += page_size
            time.sleep(0.3)

    log.info("Missouri total: %d unique whiskey brands", len(seen_names))
