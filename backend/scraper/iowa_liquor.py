"""
Iowa Liquor Products & Sales importer.

Uses the Iowa Open Data (SODA) API — completely free, no authentication required.
Two datasets:
  1. Products catalog (gckp-fe7r): 3,238 current whiskey products with proof, age, UPC
  2. Sales history (m3tr-qhgy): 4,749+ unique whiskey products including discontinued ones

Combined yield: ~5,000-7,000 unique whiskeys after dedup.
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# Iowa Open Data SODA API endpoints
PRODUCTS_URL = "https://data.iowa.gov/resource/gckp-fe7r.json"
SALES_URL = "https://data.iowa.gov/resource/m3tr-qhgy.json"

# Whiskey category filter (SQL-like WHERE clause for SODA)
WHISKEY_FILTER = (
    "category_name like '%WHISK%' OR "
    "category_name like '%BOURBON%' OR "
    "category_name like '%SCOTCH%' OR "
    "category_name like '%RYE%' OR "
    "category_name like '%MALT%'"
)

# Map Iowa category names to our categories
CATEGORY_MAP = {
    "STRAIGHT BOURBON WHISKIES": "bourbon",
    "BOTTLED IN BOND BOURBON": "bourbon",
    "SINGLE BARREL BOURBON WHISKIES": "bourbon",
    "TENNESSEE WHISKIES": "tennessee",
    "STRAIGHT RYE WHISKIES": "rye",
    "BLENDED WHISKIES": "blended",
    "CANADIAN WHISKIES": "canadian",
    "IRISH WHISKIES": "irish",
    "SCOTCH WHISKIES": "scotch",
    "SINGLE MALT SCOTCH": "single malt",
    "CORN WHISKIES": "corn",
    "WHISKEY LIQUEUR": "whiskey liqueur",
}

# Bottle sizes to strip from names
SIZE_PATTERNS = [
    r"\s*\d+\s*ml\b",
    r"\s*\d+(\.\d+)?\s*l\b",
    r"\s*\d+(\.\d+)?\s*liter\b",
    r"\s*\d+\s*pk\b",
    r"\s*\bpet\b",
    r"\s*\bmini\b$",
    r"\s*\btraveler\b",
    r"\s*\bbag in box\b",
]


def _clean_name(raw: str) -> str:
    """Clean Iowa product name: remove sizes, normalize case."""
    name = raw.strip()
    for pat in SIZE_PATTERNS:
        name = re.sub(pat, "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip()
    # Title case if all-caps
    if name == name.upper() and len(name) > 3:
        name = name.title()
    return name


def _extract_distillery(name: str, vendor: str) -> str:
    """Try to extract distillery from vendor name or product name."""
    vendor = (vendor or "").strip()
    # Common vendor → distillery mappings
    vendor_map = {
        "DIAGEO": "Diageo",
        "BEAM SUNTORY": "Jim Beam",
        "SAZERAC": "Sazerac",
        "JACK DANIEL": "Jack Daniel's",
        "BROWN-FORMAN": "Brown-Forman",
        "HEAVEN HILL": "Heaven Hill",
        "WILD TURKEY": "Wild Turkey",
        "MAKER'S MARK": "Maker's Mark",
        "BUFFALO TRACE": "Buffalo Trace",
        "PERNOD RICARD": "Pernod Ricard",
        "CAMPARI": "Campari Group",
        "BACARDI": "Bacardi",
        "WILLIAM GRANT": "William Grant & Sons",
        "EDRINGTON": "Edrington",
    }
    vendor_upper = vendor.upper()
    for key, val in vendor_map.items():
        if key in vendor_upper:
            return val
    # Use vendor name cleaned up
    if vendor:
        return vendor.title().replace("  ", " ").rstrip(" Inc.").rstrip(" Llc")
    return "Unknown"


def _proof_to_abv(proof_str: Optional[str]) -> Optional[float]:
    """Convert proof (string) to ABV float."""
    if not proof_str:
        return None
    try:
        proof = float(proof_str)
        abv = proof / 2.0
        if 20.0 <= abv <= 80.0:
            return abv
    except (ValueError, TypeError):
        pass
    return None


def _parse_age(age_str: Optional[str]) -> Optional[int]:
    """Parse age field (Iowa stores it as a string number)."""
    if not age_str:
        return None
    try:
        age = int(float(age_str))
        if 1 <= age <= 50:
            return age
    except (ValueError, TypeError):
        pass
    return None


def _category_to_region(category: str) -> Optional[str]:
    """Infer region from category."""
    region_map = {
        "bourbon": "Kentucky",
        "tennessee": "Tennessee",
        "rye": "United States",
        "blended": None,
        "canadian": "Canada",
        "irish": "Ireland",
        "scotch": "Scotland",
        "single malt": "Scotland",
        "corn": "United States",
        "whiskey liqueur": None,
    }
    return region_map.get(category)


def iter_iowa_products(limit: int = 50000) -> list[dict]:
    """
    Fetch whiskey products from the Iowa Products catalog.
    Returns normalized whiskey dicts.
    """
    log.info("Fetching Iowa Liquor Products catalog...")
    products = []
    offset = 0
    page_size = 1000
    seen_names = set()

    with httpx.Client(timeout=30) as client:
        while offset < limit:
            params = {
                "$where": WHISKEY_FILTER,
                "$limit": page_size,
                "$offset": offset,
                "$order": "itemno",
            }
            try:
                resp = client.get(PRODUCTS_URL, params=params)
                resp.raise_for_status()
                rows = resp.json()
            except Exception as exc:
                log.error("Iowa Products API error at offset %d: %s", offset, exc)
                break

            if not rows:
                break

            for row in rows:
                raw_name = row.get("im_desc", "").strip()
                if not raw_name:
                    continue

                name = _clean_name(raw_name)
                if not name or len(name) < 3:
                    continue

                # Dedup by cleaned name within this source
                name_key = name.lower()
                if name_key in seen_names:
                    continue
                seen_names.add(name_key)

                iowa_cat = row.get("category_name", "")
                category = CATEGORY_MAP.get(iowa_cat, "world")
                vendor = row.get("vendor_name", "")
                abv = _proof_to_abv(row.get("proof"))
                age = _parse_age(row.get("age"))
                upc = row.get("upc", "").strip() or None
                price_str = row.get("state_bottle_retail")

                price = None
                if price_str:
                    try:
                        price = float(price_str)
                    except (ValueError, TypeError):
                        pass

                products.append({
                    "name": name,
                    "distillery": _extract_distillery(name, vendor),
                    "category": category,
                    "region": _category_to_region(category),
                    "age": age,
                    "abv": abv or 40.0,
                    "price_usd": price,
                    "upc": upc,
                    "source": "iowa_liquor",
                })

            log.info("  Products: fetched %d rows (offset=%d), %d unique so far",
                     len(rows), offset, len(products))
            offset += page_size
            time.sleep(0.5)  # be polite to government servers

    log.info("Iowa Products catalog: %d unique whiskey products", len(products))
    return products


def iter_iowa_sales_products(limit: int = 50000) -> list[dict]:
    """
    Fetch unique whiskey products from the Iowa Sales dataset.
    This includes discontinued products not in the current catalog.
    """
    log.info("Fetching unique products from Iowa Liquor Sales...")
    products = []
    seen_names = set()

    # Use $select=distinct to get unique products
    # The sales dataset is huge (27M+ rows) so we select distinct product fields
    with httpx.Client(timeout=60) as client:
        params = {
            "$select": "distinct im_desc, category_name, vendor_name, bottle_volume_ml, state_bottle_retail",
            "$where": WHISKEY_FILTER,
            "$limit": 50000,
            "$order": "im_desc",
        }
        try:
            resp = client.get(SALES_URL, params=params)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as exc:
            log.error("Iowa Sales API error: %s", exc)
            return []

        for row in rows:
            raw_name = row.get("im_desc", "").strip()
            if not raw_name:
                continue

            name = _clean_name(raw_name)
            if not name or len(name) < 3:
                continue

            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            iowa_cat = row.get("category_name", "")
            category = CATEGORY_MAP.get(iowa_cat, "world")
            vendor = row.get("vendor_name", "")
            price_str = row.get("state_bottle_retail")

            price = None
            if price_str:
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    pass

            products.append({
                "name": name,
                "distillery": _extract_distillery(name, vendor),
                "category": category,
                "region": _category_to_region(category),
                "abv": 40.0,  # sales data doesn't have proof
                "price_usd": price,
                "source": "iowa_liquor",
            })

    log.info("Iowa Sales: %d unique whiskey products", len(products))
    return products


def iter_iowa_whiskeys(limit: int = 50000):
    """
    Yield all unique whiskey dicts from both Iowa datasets.
    Products catalog first (has better data), then sales for extras.
    """
    seen_names = set()

    # Phase 1: Products catalog (has proof, age, UPC)
    for item in iter_iowa_products(limit):
        name_key = item["name"].lower()
        if name_key not in seen_names:
            seen_names.add(name_key)
            yield item

    # Phase 2: Sales products (fills in discontinued items)
    for item in iter_iowa_sales_products(limit):
        name_key = item["name"].lower()
        if name_key not in seen_names:
            seen_names.add(name_key)
            yield item

    log.info("Iowa total unique whiskeys: %d", len(seen_names))
