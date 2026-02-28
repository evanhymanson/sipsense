"""
Vinmonopolet (Norwegian state alcohol monopoly) scraper.

Vinmonopolet is Norway's government-owned alcohol retailer. They expose a
public JSON search API used by their own website — no API key required.

Endpoint: https://www.vinmonopolet.no/vmpws/v2/vmp/products/search
Returns structured product data for all spirits including whiskies.

Data quality: excellent — structured JSON with name, ABV, age, country,
category, and price (in NOK). ~1,000–1,200 whisky entries.

Price note: prices are in NOK. The normalizer converts NOK → USD.
"""

import logging
import time
from typing import Optional, Generator

import httpx

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.vinmonopolet.no/vmpws/v2/vmp/products/search"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PAGE_SIZE = 100
REQUEST_DELAY = 1.0  # seconds between pages — be polite

# Single broad term — the API returns all whisky subcategory products
# from the main brennevin (spirits) category. Multiple terms cause duplicates.
SEARCH_TERMS = ["whisky", "whiskey", "bourbon", "scotch"]


class VinmonopoletScraper:
    """
    Fetches whisky products from the Vinmonopolet public search API.

    Usage:
        with VinmonopoletScraper() as s:
            for raw in s.iter_whiskeys(limit=3000):
                print(raw)
    """

    def __init__(self):
        self._client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Referer": "https://www.vinmonopolet.no/",
            },
            follow_redirects=True,
        )
        self._seen_ids: set[str] = set()

    def iter_whiskeys(self, limit: int = 3_000) -> Generator[dict, None, None]:
        """Yield raw whiskey dicts from Vinmonopolet search API."""
        scraped = 0

        for term in SEARCH_TERMS:
            if scraped >= limit:
                break
            log.info("Vinmonopolet: searching '%s'…", term)
            term_count = 0
            page = 0

            while scraped < limit:
                try:
                    resp = self._client.get(
                        SEARCH_URL,
                        params={
                            "fields":      "FULL",
                            "currentPage": str(page),
                            "pageSize":    str(PAGE_SIZE),
                            "q":           term,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    log.warning("Vinmonopolet error (term=%s page=%d): %s", term, page, exc)
                    break

                # Response: {"products": [...], "pagination": {...}, ...}
                products = data.get("products") or []
                if not products:
                    break

                for product in products:
                    raw = self._parse_product(product)
                    if raw:
                        yield raw
                        scraped += 1
                        term_count += 1
                        if scraped >= limit:
                            break

                # Pagination
                pagination = data.get("pagination") or {}
                total_pages = pagination.get("totalPages", 1)
                if page >= total_pages - 1:
                    break

                page += 1
                time.sleep(REQUEST_DELAY)

            log.info("  → %d entries from '%s'", term_count, term)

        log.info("Vinmonopolet: finished — %d unique entries", scraped)

    def _parse_product(self, product: dict) -> Optional[dict]:
        # Deduplicate by product code
        code = product.get("code") or ""
        if code:
            if code in self._seen_ids:
                return None
            self._seen_ids.add(code)

        name = (product.get("name") or "").strip()
        if not name or len(name) < 2:
            return None

        # Filter non-whisky products using main_sub_category code
        # e.g. "brennevin_whisky" — skip beer, wine, etc.
        main_sub = (product.get("main_sub_category") or {}).get("code", "").lower()
        if not any(w in main_sub for w in ["whisky", "whiskey", "bourbon", "malt"]):
            if not any(w in name.lower() for w in ["whisky", "whiskey", "bourbon", "scotch", "rye"]):
                return None

        combined_type = main_sub  # used for category inference

        # ABV — new field: {"value": 48.0, "formattedValue": "48%", ...}
        abv_obj = product.get("alcohol") or {}
        abv_val = abv_obj.get("value")
        if abv_val is None:
            return None
        try:
            abv_float = float(abv_val)
        except (ValueError, TypeError):
            return None
        if not (10.0 <= abv_float <= 95.0):
            return None
        abv_str = str(round(abv_float, 1))

        # Distillery / producer (not provided by the API — infer from name)
        distillery = "Unknown"

        # Country
        country_raw = (product.get("main_country") or {}).get("name", "") or ""
        country = _normalize_country(country_raw)

        # Age (not in API response — try to infer from name)
        age_str = None

        # Price — {"value": 799.0, "formattedValue": "Kr 799,00", ...}
        price_str = None
        price_obj = product.get("price") or {}
        price_val = price_obj.get("value")
        if price_val:
            price_str = str(price_val)

        # Category
        category = _infer_category(name, combined_type, country)

        # Description not available in listing — left None for Claude to fill
        description = None

        return {
            "name":           name,
            "distillery":     distillery,
            "abv_str":        abv_str,
            "age_str":        age_str,
            "price_str":      price_str,
            "rating_str":     None,
            "category":       category,
            "country":        country,
            "region":         None,
            "description":    description,
            "flavor_profile": None,
            "source":         "vinmonopolet",
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_country(country: str) -> str:
    c = country.lower().strip()
    if "scotland" in c or "united kingdom" in c:  return "scotland"
    if "united states" in c or "usa" in c:        return "usa"
    if "ireland" in c:                            return "ireland"
    if "japan" in c:                              return "japan"
    if "canada" in c:                             return "canada"
    if "norway" in c:                             return "norway"
    return c or "unknown"


def _infer_category(name: str, type_str: str, country: str) -> str:
    combined = (name + " " + type_str).lower()
    if "bourbon" in combined:         return "bourbon"
    if "tennessee" in combined:       return "bourbon"
    if "rye" in combined:             return "rye"
    if "irish" in combined:           return "irish"
    if "japanese" in combined:        return "japanese"
    if "canadian" in combined:        return "canadian"
    if "singlemalt" in combined.replace(" ", "") or "single malt" in combined:
        return "single malt"
    if "blended" in combined:         return "blended"
    if "scotch" in combined:          return "scotch"
    # Fall back to country
    if country == "scotland":         return "scotch"
    if country == "usa":              return "bourbon"
    if country == "ireland":          return "irish"
    if country == "japan":            return "japanese"
    if country == "canada":           return "canadian"
    return "whisky"
