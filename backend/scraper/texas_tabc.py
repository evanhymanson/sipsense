"""
Texas TABC (Alcoholic Beverage Commission) Approved Product Labels importer.

Uses the Texas Open Data SODA API — free, no auth required.
Endpoint: https://data.texas.gov/resource/2cjh-3vae.json

7,219 whiskey-related spirits labels with brand names, ABV, distillery info.
~4,559 unique whiskey brand names.
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://data.texas.gov/resource/2cjh-3vae.json"

WHISKEY_FILTER = (
    "type='SPIRITS' AND ("
    "upper(brand_name) like '%WHISK%' OR "
    "upper(brand_name) like '%BOURBON%' OR "
    "upper(brand_name) like '%SCOTCH%' OR "
    "upper(brand_name) like '%RYE%' OR "
    "upper(brand_name) like '%MALT%' OR "
    "upper(brand_name) like '%TENNESSEE%'"
    ")"
)

STRIP_PATTERNS = [
    r"\s*\d+\s*ML\b",
    r"\s*\d+(\.\d+)?\s*L\b",
    r"\s*\d+\s*PK\b",
    r"\s*\bW/?GLASS(ES)?\b",
    r"\s*\bGIFT\s*(SET|PACK)\b",
    r"\s*\bVAP\b",
    r"\s*\bCOMBO\b",
    r"\s*\d+\s*OZ\b",
]

EXCLUDE_KEYWORDS = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "sake", "liqueur", "absinthe", "schnapps",
    "wine", "beer", "cider", "vermouth", "bitters",
    "cream", "coffee", "chocolate", "sauce", "candy",
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
    whiskey_signals = [
        "whisky", "whiskey", "bourbon", "scotch", "rye",
        "malt", "tennessee", "corn whisk",
    ]
    if not any(s in name_lower for s in whiskey_signals):
        return False
    if any(s in name_lower for s in EXCLUDE_KEYWORDS):
        return False
    return True


def _parse_abv(abv_str: Optional[str]) -> Optional[float]:
    """Parse ABV from Texas data (field is sometimes bottle size, not ABV)."""
    if not abv_str:
        return None
    try:
        val = float(abv_str)
        # Texas field is inconsistent: sometimes ABV%, sometimes mL
        if 15.0 <= val <= 80.0:
            return val
        if 0.15 <= val <= 0.80:
            return val * 100  # decimal form → percentage
    except (ValueError, TypeError):
        pass
    # Try regex
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(abv_str))
    if m:
        val = float(m.group(1))
        if 15.0 <= val <= 80.0:
            return val
    return None


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


def iter_texas_whiskeys(limit: int = 50000):
    """
    Fetch unique whiskey labels from Texas TABC via SODA API.
    Yields normalized whiskey dicts.
    """
    log.info("Fetching Texas TABC approved product labels...")
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
                log.error("Texas TABC API error at offset %d: %s", offset, exc)
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

                trade_name = row.get("trade_name", "").strip()
                abv = _parse_abv(row.get("alcohol_content_by_volume"))
                category = _infer_category(name)

                # Infer distillery from trade_name
                distillery = "Unknown"
                if trade_name:
                    d = trade_name
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
                    "abv": abv or 40.0,
                    "source": "texas_tabc",
                }

            log.info("  Texas TABC: fetched %d rows (offset=%d), %d unique so far",
                     len(rows), offset, len(seen_names))
            offset += page_size
            time.sleep(0.3)

    log.info("Texas TABC total: %d unique whiskey brands", len(seen_names))
