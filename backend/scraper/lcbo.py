"""
LCBO.dev GraphQL API importer (Ontario, Canada liquor board).

Free, no authentication required. Updated daily.
Endpoint: https://api.lcbo.dev/graphql

~519 whisky products with ABV, tasting notes, images, UPC, pricing.
Rich hierarchical categories like "Highland Single Malt Scotch Whisky".
"""

import logging
import re
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.lcbo.dev/graphql"

# GraphQL query to fetch whisky products
PRODUCTS_QUERY = """
query FetchWhiskies($cursor: String) {
  products(
    pagination: { first: 100, after: $cursor }
    filters: { search: "whisky" }
  ) {
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        sku
        name
        primaryCategory
        producerName
        origin
        regionName
        priceInCents
        shortDescription
        thumbnailUrl
        upcNumber
        alcoholPercent
        unitVolumeMl
      }
    }
  }
}
"""

# Additional search terms to catch products not found by "whisky"
EXTRA_SEARCHES = ["whiskey", "bourbon", "scotch", "rye whiskey"]

EXTRA_QUERY = """
query FetchExtra($cursor: String, $search: String!) {
  products(
    pagination: { first: 100, after: $cursor }
    filters: { search: $search }
  ) {
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        sku
        name
        primaryCategory
        producerName
        origin
        regionName
        priceInCents
        shortDescription
        thumbnailUrl
        upcNumber
        alcoholPercent
        unitVolumeMl
      }
    }
  }
}
"""


def _infer_category(primary_cat: str, name: str) -> str:
    """Infer category from LCBO hierarchical category string."""
    cat_lower = (primary_cat or "").lower()
    name_lower = (name or "").lower()
    combined = f"{cat_lower} {name_lower}"

    if "bourbon" in combined:
        return "bourbon"
    if "single malt" in combined:
        return "single malt"
    if "scotch" in combined:
        return "scotch"
    if "irish" in combined:
        return "irish"
    if "japanese" in combined:
        return "japanese"
    if "rye" in combined:
        return "rye"
    if "canadian" in combined:
        return "canadian"
    if "blended" in combined:
        return "blended"
    if "tennessee" in combined:
        return "tennessee"
    if "corn" in combined:
        return "corn"
    return "whiskey"


def _category_to_region(category: str, origin: str) -> Optional[str]:
    """Map category/origin to region."""
    if origin:
        return origin
    region_map = {
        "bourbon": "United States",
        "tennessee": "United States",
        "rye": "United States",
        "scotch": "Scotland",
        "single malt": "Scotland",
        "canadian": "Canada",
        "irish": "Ireland",
        "japanese": "Japan",
    }
    return region_map.get(category)


def _parse_age(name: str) -> Optional[int]:
    """Extract age from product name."""
    m = re.search(r"(\d+)\s*(?:year|yr|yo|y\.o\.)", name, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if 1 <= val <= 60:
            return val
    return None


def _is_whiskey(node: dict) -> bool:
    """Check if a product is actually a whiskey."""
    cat = (node.get("primaryCategory") or "").lower()
    name = (node.get("name") or "").lower()
    combined = f"{cat} {name}"

    whiskey_signals = [
        "whisky", "whiskey", "bourbon", "scotch", "rye",
        "single malt", "malt", "tennessee",
    ]
    non_whiskey = [
        "cream", "liqueur", "cocktail", "bitters", "mix",
        "vodka", "gin", "rum", "tequila", "brandy",
    ]

    has_whiskey = any(s in combined for s in whiskey_signals)
    is_non_whiskey = any(s in combined for s in non_whiskey)

    return has_whiskey and not is_non_whiskey


def iter_lcbo_whiskeys():
    """
    Fetch all whisky products from LCBO.dev GraphQL API.
    Yields normalized whiskey dicts.
    """
    log.info("Fetching LCBO whisky products via GraphQL...")
    seen_skus = set()
    seen_names = set()

    with httpx.Client(timeout=30) as client:
        # Search "whisky" first (main results)
        all_searches = [("whisky", PRODUCTS_QUERY, False)] + [
            (term, EXTRA_QUERY, True) for term in EXTRA_SEARCHES
        ]

        for search_term, query, is_extra in all_searches:
            cursor = None
            page = 0
            term_count = 0

            while True:
                variables = {"cursor": cursor}
                if is_extra:
                    variables["search"] = search_term

                try:
                    resp = client.post(
                        GRAPHQL_URL,
                        json={"query": query, "variables": variables},
                        headers={"Content-Type": "application/json"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    log.warning("LCBO API error (term=%s, page=%d): %s",
                                search_term, page, exc)
                    break

                products_data = data.get("data", {}).get("products", {})
                edges = products_data.get("edges", [])
                page_info = products_data.get("pageInfo", {})

                if not edges:
                    break

                for edge in edges:
                    node = edge.get("node", {})
                    sku = node.get("sku", "")
                    name = (node.get("name") or "").strip()

                    if not name or len(name) < 3:
                        continue

                    # Dedup by SKU and name
                    if sku in seen_skus:
                        continue
                    name_key = name.lower()
                    if name_key in seen_names:
                        continue

                    if not _is_whiskey(node):
                        continue

                    seen_skus.add(sku)
                    seen_names.add(name_key)

                    category = _infer_category(
                        node.get("primaryCategory", ""),
                        name,
                    )
                    origin = node.get("origin") or node.get("regionName") or ""
                    abv = node.get("alcoholPercent")
                    price_cents = node.get("priceInCents")
                    price_usd = None
                    if price_cents:
                        # Convert CAD cents to approx USD
                        price_usd = round(price_cents / 100.0 * 0.73, 2)

                    description = node.get("shortDescription")
                    image_url = node.get("thumbnailUrl")
                    upc = node.get("upcNumber")
                    age = _parse_age(name)
                    producer = node.get("producerName") or ""

                    yield {
                        "name": name,
                        "distillery": producer or "Unknown",
                        "category": category,
                        "region": _category_to_region(category, origin),
                        "age": age,
                        "abv": abv if abv and 20.0 <= abv <= 80.0 else 40.0,
                        "price_usd": price_usd,
                        "description": description[:500] if description else None,
                        "image_url": image_url,
                        "upc": upc,
                        "source": "lcbo",
                    }
                    term_count += 1

                page += 1

                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")
                time.sleep(0.3)

            log.info("  LCBO '%s': %d new products", search_term, term_count)

    log.info("LCBO total: %d unique whiskey products", len(seen_names))
