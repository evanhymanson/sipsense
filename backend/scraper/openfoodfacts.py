"""
OpenFoodFacts whiskey scraper.

OpenFoodFacts is a community-maintained food/drink database with
Creative Commons data. Their spirits subset has ~10-20k whiskeys with
barcodes (UPC) — great for the future label-scanning feature.

Uses the search.pl CGI endpoint (more reliable than category pages).
Searches multiple whiskey terms and deduplicates by barcode.

Key bonus: UPC/EAN barcodes power the Phase 3 label-scan feature.
"""

import logging
import time
from typing import Generator, Optional

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "SipSense/1.0 (whiskey recommendation app; educational project)"
SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
PAGE_SIZE = 100
REQUEST_DELAY = 1.0  # seconds between pages

# Search terms to run (each returns a separate paginated result set)
SEARCH_TERMS = [
    "whisky",
    "whiskey",
    "bourbon",
    "scotch whisky",
    "irish whiskey",
    "japanese whisky",
    "single malt",
    "rye whiskey",
    "blended whisky",
]

# Category tags that confirm it's an actual whiskey product
WHISKEY_CATEGORY_HINTS = [
    "whisky", "whiskey", "bourbon", "scotch", "spirits",
    "distilled", "single-malt", "malt", "rye",
]

# Category tags that indicate it's NOT a whiskey (flavored food with whisky etc.)
NON_SPIRIT_HINTS = [
    "biscuit", "chocolate", "cake", "sauce", "cream", "candy",
    "coffee", "tea", "marmalade", "cheese", "sardine", "flavor",
    "flavour", "truffle",
]

FIELDS = ",".join([
    "product_name", "brands", "code", "countries",
    "categories_tags", "nutriments", "quantity",
])


class OpenFoodFactsScraper:
    """
    Searches OpenFoodFacts for whiskey products via the search.pl API.

    Deduplicates by barcode (UPC/EAN) and product name.
    """

    def __init__(self):
        self._client = httpx.Client(
            timeout=90.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._seen_barcodes: set[str] = set()
        self._seen_names: set[str] = set()

    def fetch_whiskeys(self) -> list[dict]:
        results = []
        for raw in self.iter_whiskeys():
            results.append(raw)
        log.info("OpenFoodFacts total: %d whiskey entries", len(results))
        return results

    def iter_whiskeys(self) -> Generator[dict, None, None]:
        for term in SEARCH_TERMS:
            log.info("OpenFoodFacts: searching '%s'…", term)
            term_count = 0
            page = 1

            while True:
                try:
                    resp = self._client.get(
                        SEARCH_URL,
                        params={
                            "search_terms": term,
                            "search_simple": "1",
                            "action": "process",
                            "json": "1",
                            "page_size": str(PAGE_SIZE),
                            "page": str(page),
                            "fields": FIELDS,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    log.warning("OpenFoodFacts error (term=%s page=%d): %s", term, page, exc)
                    break

                products = data.get("products", [])
                if not products:
                    break

                for product in products:
                    raw = self._parse_product(product)
                    if raw:
                        term_count += 1
                        yield raw

                # Check if we've reached the last page
                total = int(data.get("count", 0))
                if page * PAGE_SIZE >= total or not products:
                    break

                page += 1
                time.sleep(REQUEST_DELAY)

            log.info("  → %d new products from '%s'", term_count, term)

    def _parse_product(self, product: dict) -> Optional[dict]:
        name = (product.get("product_name") or "").strip()
        if not name or len(name) < 2:
            return None

        categories_tags = product.get("categories_tags") or []
        categories_str = " ".join(categories_tags).lower()

        # Skip products that are clearly food flavored with whisky (not actual spirits)
        if any(hint in categories_str for hint in NON_SPIRIT_HINTS):
            return None
        if any(hint in name.lower() for hint in NON_SPIRIT_HINTS):
            return None

        # Require some whiskey category signal
        has_whiskey_category = any(hint in categories_str for hint in WHISKEY_CATEGORY_HINTS)
        # OR validate by ABV (spirits must be >15%)
        abv_val = (product.get("nutriments") or {}).get("alcohol")
        abv_float = None
        if abv_val:
            try:
                abv_float = float(abv_val)
            except (ValueError, TypeError):
                pass

        is_spirit_by_abv = abv_float and abv_float >= 15.0

        if not has_whiskey_category and not is_spirit_by_abv:
            return None

        # Deduplicate by barcode first, then name
        barcode = (product.get("code") or "").strip()
        if barcode:
            if barcode in self._seen_barcodes:
                return None
            self._seen_barcodes.add(barcode)
        else:
            name_lower = name.lower()
            if name_lower in self._seen_names:
                return None
            self._seen_names.add(name_lower)

        brand = _first(product.get("brands") or "")
        country_raw = _first(product.get("countries") or "")
        quantity = (product.get("quantity") or "").strip()

        abv_str = str(round(abv_float, 1)) if abv_float and 10.0 <= abv_float <= 95.0 else "40.0"

        return {
            "name":         name,
            "distillery":   brand or "Unknown",
            "category":     _infer_category_from_tags(categories_tags, name),
            "country":      _normalize_country(country_raw),
            "region":       None,
            "age_str":      _extract_age(name),
            "abv_str":      abv_str,
            "rating_str":   None,
            "price_str":    None,
            "description":  f"By {brand}. {quantity}".strip(". ") if brand else None,
            "flavor_profile": None,
            "upc":          barcode or None,
            "source":       "openfoodfacts",
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── helpers ───────────────────────────────────────────────────────────────

def _first(value: str) -> str:
    return value.split(",")[0].strip() if value else ""


def _extract_age(name: str) -> Optional[str]:
    import re
    m = re.search(r"(\d+)\s*[Yy]ear", name)
    return m.group(1) if m else None


def _infer_category_from_tags(tags: list, name: str) -> str:
    s = " ".join(tags).lower()
    n = name.lower()
    if "bourbon" in s or "bourbon" in n:        return "bourbon"
    if "scotch" in s or "scotch" in n:          return "scotch"
    if "irish" in s or "irish" in n:            return "irish"
    if "japanese" in s or "japanese" in n:      return "japanese"
    if "rye" in s or "rye" in n:                return "rye"
    if "canadian" in s or "canadian" in n:      return "canadian"
    if "single-malt" in s or "single malt" in n: return "single malt"
    if "blended" in s or "blended" in n:        return "blended"
    return "whiskey"


def _normalize_country(country: str) -> str:
    c = country.lower().strip()
    if any(x in c for x in ["united states", "usa", "u.s."]):  return "usa"
    if any(x in c for x in ["scotland", "united kingdom"]):     return "scotland"
    if "ireland" in c:  return "ireland"
    if "japan" in c:    return "japan"
    if "canada" in c:   return "canada"
    return c
