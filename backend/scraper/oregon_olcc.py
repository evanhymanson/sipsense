"""
Oregon OLCC (Oregon Liquor & Cannabis Commission) pricing data importer.

Uses the Socrata Open Data API (SODA) — completely free, no auth required.
Endpoint: https://data.oregon.gov/resource/vmf2-f83h.json

28,161 whiskey-related records across categories:
  DOMESTIC WHISKEY (15,344), SCOTCH (10,769), CANADIAN (2,078),
  OTHER IMPORTED WHISKY (1,800), IRISH (1,673), WHISKEY (248)

Fields: description, category, proof, price, age, size, item status
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ENDPOINT = "https://data.oregon.gov/resource/vmf2-f83h.json"

WHISKEY_CATEGORIES = [
    "DOMESTIC WHISKEY",
    "SCOTCH",
    "CANADIAN",
    "OTHER IMPORTED WHISKY",
    "IRISH",
    "WHISKEY",
]

# Map OLCC categories to our categories
CATEGORY_MAP = {
    "DOMESTIC WHISKEY": "bourbon",
    "SCOTCH": "scotch",
    "CANADIAN": "canadian",
    "IRISH": "irish",
    "OTHER IMPORTED WHISKY": "world",
    "WHISKEY": "whiskey",
}

# Patterns to strip from product descriptions (bottle sizes, packaging)
STRIP_PATTERNS = [
    r"\s*-\s*\d+ML$",
    r"\s*-\s*\d+(\.\d+)?L$",
    r"\s*\(\w+\)\s*-\s*\d+ML$",   # "(HAL) - 750ML"
    r"\s*\(\w+\)$",                 # trailing "(HAL)"
    r"\s*\d+ML$",
    r"\s*\d+\s*PK$",
]


def _clean_name(desc: str) -> str:
    """Clean OLCC product description into a nice name."""
    name = desc.strip()
    # Remove size/packaging suffixes
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = name.strip(" -")
    # Title case if all-caps
    if name == name.upper() and len(name) > 3:
        name = name.title()
    return name


def _proof_to_abv(proof) -> Optional[float]:
    """Convert proof (number) to ABV."""
    if proof is None:
        return None
    try:
        p = float(proof)
        abv = p / 2.0
        if 20.0 <= abv <= 80.0:
            return abv
    except (ValueError, TypeError):
        pass
    return None


def _parse_age(age_str: Optional[str]) -> Optional[int]:
    """Parse age from strings like '14 YRS', '12', 'NAS'."""
    if not age_str:
        return None
    m = re.search(r"(\d+)", str(age_str))
    if m:
        val = int(m.group(1))
        if 1 <= val <= 60:
            return val
    return None


def _infer_subcategory(name: str, olcc_cat: str) -> str:
    """Infer more specific category from name + OLCC category."""
    name_lower = name.lower()
    if "single malt" in name_lower:
        return "single malt"
    if "bourbon" in name_lower:
        return "bourbon"
    if "rye" in name_lower and "whisky" not in name_lower:
        return "rye"
    if "tennessee" in name_lower:
        return "tennessee"
    if "blended" in name_lower:
        return "blended"
    if "single grain" in name_lower:
        return "single grain"
    if "corn" in name_lower:
        return "corn"
    return CATEGORY_MAP.get(olcc_cat, "whiskey")


def _category_to_region(category: str) -> Optional[str]:
    """Infer region from category."""
    region_map = {
        "bourbon": "Kentucky",
        "tennessee": "Tennessee",
        "rye": "United States",
        "scotch": "Scotland",
        "single malt": "Scotland",
        "canadian": "Canada",
        "irish": "Ireland",
        "world": None,
        "blended": None,
        "whiskey": None,
    }
    return region_map.get(category)


def _extract_distillery(name: str) -> str:
    """Try to extract distillery/brand from the product name."""
    # Common patterns: "BRAND NAME AGE DESCRIPTION"
    # Take the first 2-3 words as brand
    words = name.split()
    if len(words) >= 2:
        # Check for common age patterns to split on
        for i, w in enumerate(words):
            if re.match(r"^\d+YR", w, re.IGNORECASE) or w.upper() in ("YEAR", "YEARS", "YR", "YRS"):
                if i >= 1:
                    return " ".join(words[:i])
        # Take first 2-3 words as brand
        return " ".join(words[:min(3, len(words))])
    return name


def iter_oregon_whiskeys(limit: int = 50000):
    """
    Fetch all whiskey products from Oregon OLCC via SODA API.
    Yields normalized whiskey dicts.
    """
    log.info("Fetching Oregon OLCC whiskey data...")
    seen_names = set()
    total_fetched = 0
    yielded = 0

    cat_filter = " OR ".join(f"category='{c}'" for c in WHISKEY_CATEGORIES)

    with httpx.Client(timeout=30) as client:
        offset = 0
        page_size = 2000

        while offset < limit:
            params = {
                "$where": cat_filter,
                "$limit": page_size,
                "$offset": offset,
                "$order": "itemcode,asofdate DESC",
            }
            try:
                resp = client.get(ENDPOINT, params=params)
                resp.raise_for_status()
                rows = resp.json()
            except Exception as exc:
                log.error("Oregon OLCC API error at offset %d: %s", offset, exc)
                break

            if not rows:
                break

            total_fetched += len(rows)

            for row in rows:
                desc = row.get("description", "").strip()
                if not desc or len(desc) < 3:
                    continue

                name = _clean_name(desc)
                if not name or len(name) < 3:
                    continue

                # Dedup by cleaned name (OLCC has same product at different dates)
                name_key = name.lower()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                olcc_cat = row.get("category", "")
                category = _infer_subcategory(name, olcc_cat)
                abv = _proof_to_abv(row.get("proof"))
                age = _parse_age(row.get("age"))
                price = None
                price_raw = row.get("priceperbottle")
                if price_raw:
                    try:
                        price = float(price_raw)
                    except (ValueError, TypeError):
                        pass

                yield {
                    "name": name,
                    "distillery": _extract_distillery(name),
                    "category": category,
                    "region": _category_to_region(category),
                    "age": age,
                    "abv": abv or 40.0,
                    "price_usd": price,
                    "source": "oregon_olcc",
                }
                yielded += 1

            log.info("  Oregon OLCC: fetched %d rows (offset=%d), %d unique so far",
                     len(rows), offset, len(seen_names))
            offset += page_size
            time.sleep(0.3)

    log.info("Oregon OLCC total: %d fetched, %d unique whiskey products", total_fetched, yielded)
