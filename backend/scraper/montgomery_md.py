"""
Montgomery County MD ABS Store Inventory importer.

Uses the Socrata SODA API — free, no auth required.
Endpoint: https://data.montgomerycountymd.gov/resource/ib5t-5ncy.json

~992 whiskey products with prices and detailed categories.
Montgomery County runs its own government liquor stores.
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://data.montgomerycountymd.gov/resource/ib5t-5ncy.json"

WHISKEY_FILTER = (
    "upper(category) like '%WHISK%' OR "
    "upper(category) like '%BOURBON%' OR "
    "upper(category) like '%SCOTCH%' OR "
    "upper(category) like '%RYE%' OR "
    "upper(category) like '%MALT%' OR "
    "upper(category) like '%SOUR MASH%'"
)

CATEGORY_MAP = {
    "STRAIGHT BOURBON WHISKEY": "bourbon",
    "STRAIGHT RYE WHISKEY": "rye",
    "BLENDED WHISKEY": "blended",
    "SINGLE MALT SCOTCH": "single malt",
    "IMPORTED SCOTCH": "scotch",
    "IRISH WHISKEY": "irish",
    "CANADIAN WHISKEY": "canadian",
    "SOUR MASH WHISKEY": "tennessee",
}

STRIP_PATTERNS = [
    r"\s*-\s*\d+ML$",
    r"\s*-\s*\d+(\.\d+)?L$",
    r"\s*\d+ML$",
    r"\s*\d+\s*OZ$",
]


def _clean_name(raw: str) -> str:
    name = raw.strip()
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    if name == name.upper() and len(name) > 3:
        name = name.title()
    return name


def iter_montgomery_whiskeys(limit: int = 50000):
    """Fetch whiskey products from Montgomery County MD."""
    log.info("Fetching Montgomery County MD inventory data...")
    seen_names = set()

    with httpx.Client(timeout=30) as client:
        params = {
            "$where": WHISKEY_FILTER,
            "$limit": 5000,
            "$order": "description",
        }
        try:
            resp = client.get(ENDPOINT, params=params)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as exc:
            log.error("Montgomery County API error: %s", exc)
            return

        for row in rows:
            desc = row.get("description", "").strip()
            if not desc or len(desc) < 3:
                continue

            name = _clean_name(desc)
            if not name or len(name) < 3:
                continue

            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            md_cat = row.get("category", "")
            category = CATEGORY_MAP.get(md_cat, "whiskey")

            price = None
            price_str = row.get("price") or row.get("sale_price")
            if price_str:
                try:
                    price = float(str(price_str).replace("$", "").strip())
                except (ValueError, TypeError):
                    pass

            yield {
                "name": name,
                "distillery": "Unknown",
                "category": category,
                "region": None,
                "abv": 40.0,
                "price_usd": price,
                "source": "montgomery_md",
            }

    log.info("Montgomery County MD: %d unique whiskey products", len(seen_names))
