"""
Connecticut Liquor Brands importer.

Uses the Connecticut Open Data SODA API — free, no auth required.
Endpoint: https://data.ct.gov/resource/u6ds-fzyp.json

~3,187 whiskey brand registrations with brand names and distributor info.
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://data.ct.gov/resource/u6ds-fzyp.json"

WHISKEY_FILTER = (
    "upper(brand_name) like '%WHISK%' OR "
    "upper(brand_name) like '%BOURBON%' OR "
    "upper(brand_name) like '%SCOTCH%' OR "
    "upper(brand_name) like '%RYE %' OR "
    "upper(brand_name) like '%SINGLE MALT%' OR "
    "upper(brand_name) like '%TENNESSEE%'"
)

STRIP_PATTERNS = [
    r"\s*\d+\s*ML\b",
    r"\s*\d+(\.\d+)?\s*L\b",
    r"\s*\d+\s*PK\b",
    r"\s*\bW/?GLASS(ES)?\b",
    r"\s*\bGFT\b",
    r"\s*\d+\s*OZ\b",
    r"\s*\bVAP\b",
]

EXCLUDE_KEYWORDS = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "sake", "liqueur", "absinthe", "schnapps",
    "wine", "beer", "cider", "vermouth", "bitters",
    "cream", "coffee", "chocolate", "sauce", "candy",
]


def _clean_name(raw: str) -> str:
    name = raw.strip()
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    if name == name.upper() and len(name) > 3:
        name = name.title()
    return name


def _is_whiskey(name: str) -> bool:
    name_lower = name.lower()
    whiskey_signals = [
        "whisky", "whiskey", "bourbon", "scotch", "rye",
        "malt", "tennessee", "corn whisk",
    ]
    if not any(s in name_lower for s in whiskey_signals):
        return False
    if any(s in name_lower for s in EXCLUDE_KEYWORDS):
        return False
    return True


def _infer_category(name: str) -> str:
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


def iter_connecticut_whiskeys(limit: int = 50000):
    """
    Fetch unique whiskey brands from Connecticut open data.
    Yields normalized whiskey dicts.
    """
    log.info("Fetching Connecticut liquor brand data...")
    seen_names = set()
    total_fetched = 0

    with httpx.Client(timeout=30) as client:
        offset = 0
        page_size = 2000

        while offset < limit:
            params = {
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
                log.error("Connecticut API error at offset %d: %s", offset, exc)
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

                category = _infer_category(name)
                shipper = row.get("out_of_state_shipper", "").strip()
                distillery = "Unknown"
                if shipper:
                    d = shipper
                    for suffix in [" LLC", " INC", " LTD", " CO", " CORP", " COMPANY", " LP"]:
                        if d.upper().endswith(suffix):
                            d = d[:-len(suffix)]
                    if d == d.upper():
                        d = d.title()
                    distillery = d.strip()

                yield {
                    "name": name,
                    "distillery": distillery,
                    "category": category,
                    "region": None,
                    "abv": 40.0,
                    "source": "connecticut_liquor",
                }

            log.info("  Connecticut: fetched %d rows (offset=%d), %d unique so far",
                     len(rows), offset, len(seen_names))
            offset += page_size
            time.sleep(0.3)

    log.info("Connecticut total: %d unique whiskey brands", len(seen_names))
