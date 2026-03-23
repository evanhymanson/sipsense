"""
Scrape real retail prices for all whiskeys with bottle images.

Sources:
  1. Iowa Liquor Products Catalog (Socrata API) — US retail prices
  2. The Whisky Exchange (search) — UK retail prices in GBP → USD

Usage:
  cd backend
  caffeinate -s python -m scripts.scrape_prices                     # full run
  caffeinate -s python -m scripts.scrape_prices --resume            # resume
  caffeinate -s python -m scripts.scrape_prices --dry-run --limit 20 # test
  caffeinate -s python -m scripts.scrape_prices --limit 500         # partial
  caffeinate -s python -m scripts.scrape_prices --source iowa       # Iowa only
  caffeinate -s python -m scripts.scrape_prices --source twe        # TWE only
"""

import argparse
import json
import logging
import re
import shutil
import sys
import time
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Allow imports from the backend package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Whiskey, PriceEnrichmentLog

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "sipsense.db"
PROGRESS_FILE = Path(__file__).parent / "scrape_prices_progress.json"
REPORT_FILE = Path(__file__).parent / "scrape_prices_report.json"

GBP_TO_USD = 1.27  # approximate conversion rate

# ── Name normalization (from enrich_prices.py) ────────────────────────

_SUFFIXES = [
    "kentucky straight bourbon whiskey",
    "kentucky straight bourbon",
    "single malt scotch whisky", "single malt scotch whiskey",
    "blended scotch whisky", "blended scotch whiskey",
    "single malt whisky", "single malt whiskey",
    "blended malt whisky", "blended malt whiskey",
    "scotch whisky", "scotch whiskey",
    "irish whiskey", "irish whisky",
    "bourbon whiskey", "bourbon whisky",
    "tennessee whiskey", "tennessee whisky",
    "canadian whisky", "canadian whiskey",
    "japanese whisky", "japanese whiskey",
    "american whiskey", "american whisky",
    "rye whiskey", "rye whisky",
    "corn whiskey", "wheat whiskey",
    "grain whisky", "whisky", "whiskey",
]


def normalize_for_price(name: str) -> str:
    """Aggressively normalize a whiskey name for price matching."""
    s = name.lower().strip()
    if s.startswith("the "):
        s = s[4:]
    s = re.sub(
        r"(\d+)\s*(?:year[s]?\s*old|year[s]?|yr[s]?\s*old|yr[s]?|yo|y\.o\.?)",
        r"\1yo", s, flags=re.I,
    )
    for suffix in _SUFFIXES:
        s = s.replace(suffix, "")
    s = re.sub(r"cask\s*(?:#|no\.?)\s*\d+", "", s)
    s = re.sub(r"batch\s*(?:no\.?)?\s*\d+", "", s)
    s = re.sub(r"\b(19|20)\d{2}\b", "", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", s, flags=re.I)
    s = re.sub(r"\bsmws\s*\d+\.\d+\b", "", s, flags=re.I)
    s = s.replace("'", "").replace("\u2019", "").replace("`", "")
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().strip("-").strip()
    return s


def extract_age(normalized_name: str) -> int | None:
    """Extract age from a normalized name like 'glenfiddich 12yo'."""
    m = re.search(r"(\d+)yo", normalized_name)
    if m:
        return int(m.group(1))
    # Also catch "20th" style references
    m2 = re.search(r"(\d+)(?:th|st|nd|rd)\b", normalized_name)
    return int(m2.group(1)) if m2 else None


def ages_compatible(name_a: str, name_b: str) -> tuple[bool, int]:
    """Check if two normalized names have compatible ages.

    Returns (compatible, penalty):
      - Both have same age: (True, 0)
      - Both have different ages: (False, 30)
      - One has age, other doesn't: (True, 15) — partial penalty
      - Neither has age: (True, 0)
    """
    age_a = extract_age(name_a)
    age_b = extract_age(name_b)
    if age_a is None and age_b is None:
        return True, 0
    if age_a is None or age_b is None:
        # One has age, other doesn't — partial penalty to avoid
        # "Bowmore 22Y" matching generic "bowmore" at base price
        return True, 15
    if age_a == age_b:
        return True, 0
    return False, 30


def build_search_query(w) -> str:
    """Build a clean search query from a whiskey object."""
    parts = []
    dist = (w.distillery or "").strip()
    if dist and dist.lower() != "unknown":
        parts.append(dist)

    name = w.name
    if dist and name.lower().startswith(dist.lower()):
        name = name[len(dist):].strip()
    for suffix in _SUFFIXES:
        name = re.sub(re.escape(suffix), "", name, flags=re.I)
    name = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", name, flags=re.I)
    name = re.sub(r"cask\s*(?:#|no\.?)\s*\d+", "", name, flags=re.I)
    name = re.sub(r"batch\s*(?:no\.?)?\s*\d+", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip().strip("-").strip()
    if name:
        parts.append(name)

    query = " ".join(parts).strip()
    if len(query) > 80:
        query = query[:80].rsplit(" ", 1)[0]
    return query


# ── Progress tracking ─────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {
        "processed_ids": [],
        "found": 0,
        "not_found": 0,
        "errors": 0,
        "iowa_matched": 0,
        "twe_matched": 0,
        "updated_at": None,
    }


def save_progress(progress: dict):
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


# ── Source 1: Iowa Liquor API ─────────────────────────────────────────

def fetch_iowa_prices() -> dict[str, float]:
    """Fetch all whiskey prices from Iowa Liquor Products catalog."""
    log.info("Fetching Iowa Liquor catalog prices...")
    prices = {}
    client = httpx.Client(timeout=30)

    try:
        offset = 0
        batch = 1000
        while True:
            resp = client.get(
                "https://data.iowa.gov/resource/gckp-fe7r.json",
                params={
                    "$limit": str(batch),
                    "$offset": str(offset),
                    "$where": (
                        "upper(category_name) like '%BOURBON%' OR "
                        "upper(category_name) like '%SCOTCH%' OR "
                        "upper(category_name) like '%WHISK%' OR "
                        "upper(category_name) like '%TENNESSEE%' OR "
                        "upper(category_name) like '%RYE%' OR "
                        "upper(category_name) like '%SINGLE MALT%'"
                    ),
                    "$select": "im_desc, state_bottle_retail, bottle_volume_ml",
                },
            )
            if resp.status_code != 200:
                log.warning("Iowa API error: %s", resp.status_code)
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                name = item.get("im_desc", "")
                price_str = item.get("state_bottle_retail")
                vol = item.get("bottle_volume_ml", "750")

                if not name or not price_str:
                    continue
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue
                try:
                    vol_ml = int(vol)
                except (ValueError, TypeError):
                    vol_ml = 750

                if vol_ml < 600 or vol_ml > 900:
                    continue
                if 1.0 <= price <= 50000.0:
                    norm = normalize_for_price(name)
                    if norm:
                        # Keep the lowest price if duplicates
                        if norm not in prices or price < prices[norm]:
                            prices[norm] = price

            offset += batch
            if len(data) < batch:
                break
    finally:
        client.close()

    log.info("Iowa: loaded %d products with prices", len(prices))
    return prices


def fetch_oregon_prices() -> dict[str, float]:
    """Fetch whiskey prices from Oregon OLCC catalog."""
    log.info("Fetching Oregon OLCC catalog prices...")
    prices = {}
    client = httpx.Client(timeout=30)

    try:
        offset = 0
        batch = 1000
        while True:
            resp = client.get(
                "https://data.oregon.gov/resource/vmf2-f83h.json",
                params={
                    "$limit": str(batch),
                    "$offset": str(offset),
                    "$where": (
                        "upper(category) like '%SCOTCH%' OR "
                        "upper(category) like '%BOURBON%' OR "
                        "upper(category) like '%WHISK%' OR "
                        "upper(category) like '%RYE%' OR "
                        "upper(category) like '%SINGLE MALT%' OR "
                        "upper(category) like '%IRISH%' OR "
                        "upper(category) like '%JAPANESE%'"
                    ),
                    "$select": "description, priceperbottle, size",
                },
            )
            if resp.status_code != 200:
                log.warning("Oregon API error: %s", resp.status_code)
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                name = item.get("description", "")
                price_str = item.get("priceperbottle")
                size = item.get("size", "750 ML")

                if not name or not price_str:
                    continue
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                # Filter to 750ml
                if "750" not in size and "700" not in size:
                    continue
                if 1.0 <= price <= 50000.0:
                    norm = normalize_for_price(name)
                    if norm and (norm not in prices or price < prices[norm]):
                        prices[norm] = price

            offset += batch
            if len(data) < batch:
                break
    finally:
        client.close()

    log.info("Oregon: loaded %d products with prices", len(prices))
    return prices


def fetch_montgomery_prices() -> dict[str, float]:
    """Fetch whiskey prices from Montgomery County MD catalog."""
    log.info("Fetching Montgomery County MD catalog prices...")
    prices = {}
    client = httpx.Client(timeout=30)

    try:
        offset = 0
        batch = 1000
        while True:
            resp = client.get(
                "https://data.montgomerycountymd.gov/resource/ib5t-5ncy.json",
                params={
                    "$limit": str(batch),
                    "$offset": str(offset),
                    "$where": (
                        "upper(category) like '%SCOTCH%' OR "
                        "upper(category) like '%BOURBON%' OR "
                        "upper(category) like '%WHISK%' OR "
                        "upper(category) like '%RYE%' OR "
                        "upper(category) like '%SINGLE MALT%' OR "
                        "upper(category) like '%IRISH%' OR "
                        "upper(category) like '%JAPANESE%'"
                    ),
                    "$select": "description, price, size",
                },
            )
            if resp.status_code != 200:
                log.warning("Montgomery API error: %s", resp.status_code)
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                name = item.get("description", "")
                price_str = item.get("price")
                size = item.get("size", "750ML")

                if not name or not price_str:
                    continue
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                # Filter to 750ml
                if "750" not in size and "700" not in size:
                    continue
                if 1.0 <= price <= 50000.0:
                    norm = normalize_for_price(name)
                    if norm and (norm not in prices or price < prices[norm]):
                        prices[norm] = price

            offset += batch
            if len(data) < batch:
                break
    finally:
        client.close()

    log.info("Montgomery: loaded %d products with prices", len(prices))
    return prices


def fetch_lcbo_prices() -> dict[str, float]:
    """Fetch whiskey prices from LCBO (Ontario, Canada) GraphQL API."""
    log.info("Fetching LCBO catalog prices...")
    prices = {}
    CAD_TO_USD = 0.73

    QUERY = """
    query FetchWhiskies($cursor: String, $search: String!) {
      products(
        pagination: { first: 100, after: $cursor }
        filters: { search: $search }
      ) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges {
          node {
            name
            priceInCents
            unitVolumeMl
          }
        }
      }
    }
    """
    client = httpx.Client(timeout=30)
    search_terms = ["whisky", "whiskey", "bourbon", "scotch", "rye whiskey"]
    seen_names = set()

    try:
        for term in search_terms:
            cursor = None
            while True:
                variables = {"search": term, "cursor": cursor}
                resp = client.post(
                    "https://api.lcbo.dev/graphql",
                    json={"query": QUERY, "variables": variables},
                )
                if resp.status_code != 200:
                    log.warning("LCBO API error: %s", resp.status_code)
                    break

                data = resp.json().get("data", {}).get("products", {})
                edges = data.get("edges", [])
                if not edges:
                    break

                for edge in edges:
                    node = edge["node"]
                    name = node.get("name", "")
                    price_cents = node.get("priceInCents")
                    vol = node.get("unitVolumeMl")

                    if not name or not price_cents:
                        continue
                    if name in seen_names:
                        continue
                    seen_names.add(name)

                    # Filter to 700-750ml
                    if vol and (vol < 600 or vol > 900):
                        continue

                    price_usd = round(price_cents / 100.0 * CAD_TO_USD, 2)
                    if 1.0 <= price_usd <= 50000.0:
                        norm = normalize_for_price(name)
                        if norm and (norm not in prices or price_usd < prices[norm]):
                            prices[norm] = price_usd

                page_info = data.get("pageInfo", {})
                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")
                time.sleep(0.5)
    finally:
        client.close()

    log.info("LCBO: loaded %d products with prices", len(prices))
    return prices


def fetch_iowa_sales_prices() -> dict[str, float]:
    """Fetch whiskey prices from Iowa Liquor SALES transactions.

    Different dataset from the products catalog — has 3,381 unique products
    with prices from actual sales. Uses MAX price (most recent) per product.
    """
    log.info("Fetching Iowa Liquor sales transaction prices...")
    prices = {}
    client = httpx.Client(timeout=60)

    try:
        resp = client.get(
            "https://data.iowa.gov/resource/m3tr-qhgy.json",
            params={
                "$select": (
                    "im_desc, MAX(state_bottle_retail) as price"
                ),
                "$where": (
                    "(category_name like '%WHISK%' OR "
                    "category_name like '%Bourbon%' OR "
                    "category_name like '%Scotch%' OR "
                    "category_name like '%Tennessee%' OR "
                    "category_name like '%Single Malt%' OR "
                    "category_name like '%Rye%') AND "
                    "bottle_volume_ml='750'"
                ),
                "$group": "im_desc",
                "$limit": "50000",
            },
        )
        if resp.status_code != 200:
            log.warning("Iowa Sales API error: %s", resp.status_code)
            return prices

        data = resp.json()
        for item in data:
            name = item.get("im_desc", "")
            price_str = item.get("price")
            if not name or not price_str:
                continue
            try:
                price = float(price_str)
            except (ValueError, TypeError):
                continue
            if 1.0 <= price <= 50000.0:
                norm = normalize_for_price(name)
                if norm and (norm not in prices or price < prices[norm]):
                    prices[norm] = price
    finally:
        client.close()

    log.info("Iowa Sales: loaded %d products with prices", len(prices))
    return prices


# ── Source 2: The Whisky Exchange (Playwright) ────────────────────────

class WhiskyExchangeScraper:
    """Search The Whisky Exchange for individual whiskey prices."""

    SEARCH_URL = "https://www.thewhiskyexchange.com/search?q={query}"

    def __init__(self, min_delay: float = 8.0, max_delay: float = 15.0):
        from scraper.browser_base import BrowserClient
        self.client = BrowserClient(
            min_delay=min_delay,
            max_delay=max_delay,
        )
        self._request_count = 0
        self._consecutive_failures = 0

    def search_price(self, name: str, distillery: str = "",
                     category: str = "") -> dict | None:
        """
        Search TWE for a whiskey and return price info.

        Returns dict with keys: price_gbp, price_usd, matched_name, url, stores
        or None if not found.
        """
        # Build search query
        query = name
        # Clean up the query
        for suffix in _SUFFIXES:
            query = re.sub(re.escape(suffix), "", query, flags=re.I)
        query = re.sub(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l)\b", "", query, flags=re.I)
        query = re.sub(r"\s+", " ", query).strip()

        if len(query) > 60:
            query = query[:60].rsplit(" ", 1)[0]

        url = self.SEARCH_URL.format(query=query.replace(" ", "+"))

        try:
            # Restart browser periodically to avoid detection
            self._request_count += 1
            if self._request_count % 150 == 0:
                log.info("TWE: restarting browser (request #%d)", self._request_count)
                self.client.close()
                time.sleep(random.uniform(10, 20))
                from scraper.browser_base import BrowserClient
                self.client = BrowserClient(min_delay=4.0, max_delay=7.0)

            html = self.client.get(url)
            self._consecutive_failures = 0
        except Exception as exc:
            self._consecutive_failures += 1
            log.warning("TWE search failed for '%s': %s", query, exc)
            if self._consecutive_failures >= 5:
                log.error("TWE: 5 consecutive failures — pausing 60s")
                time.sleep(60)
                self._consecutive_failures = 0
            return None

        soup = BeautifulSoup(html, "lxml")

        # Check for "no results"
        no_results = soup.find(string=re.compile(r"no results|no products found", re.I))
        if no_results:
            return None

        # Parse product cards
        products = soup.find_all("li", class_=re.compile(r"product", re.I))
        if not products:
            return None

        best_match = None
        best_score = 0
        norm_query = normalize_for_price(name)

        for prod in products:
            # Get product name
            name_el = prod.find(class_=re.compile(r"product-card__name|product-card__title", re.I))
            if not name_el:
                name_el = prod.find("a", class_=re.compile(r"product-card", re.I))
            if not name_el:
                continue

            prod_name = name_el.get_text(strip=True)

            # Get price
            price_el = prod.find(class_="product-card__price")
            if not price_el:
                continue

            price_text = price_el.get_text(strip=True)
            price_match = re.search(r"£([\d,.]+)", price_text)
            if not price_match:
                continue

            price_gbp = float(price_match.group(1).replace(",", ""))

            # Get volume to filter out miniatures
            meta_el = prod.find(class_=re.compile(r"product-card__meta", re.I))
            meta_text = meta_el.get_text(strip=True) if meta_el else ""
            vol_match = re.search(r"(\d+)\s*cl", meta_text)
            if vol_match:
                vol_cl = int(vol_match.group(1))
                if vol_cl < 50:  # Skip miniatures
                    continue

            # Score match quality
            norm_prod = normalize_for_price(prod_name)
            if HAS_RAPIDFUZZ:
                score = fuzz.token_sort_ratio(norm_query, norm_prod)
            else:
                score = 80 if norm_query in norm_prod or norm_prod in norm_query else 50

            # Penalize age mismatches and generic matches
            _, age_penalty = ages_compatible(norm_query, norm_prod)
            score -= age_penalty

            if score > best_score:
                best_score = score
                best_match = {
                    "price_gbp": price_gbp,
                    "price_usd": round(price_gbp * GBP_TO_USD, 2),
                    "matched_name": prod_name,
                    "score": score,
                    "source": "whisky_exchange",
                }

        # Only return if match quality is good enough
        if best_match and best_match["score"] >= 65:
            return best_match

        return None

    def close(self):
        self.client.close()


# ── Database operations ───────────────────────────────────────────────

def apply_price_update(db: Session, whiskey_id: int, price: float,
                       method: str, confidence: float,
                       source_detail: str, original_price: float | None,
                       dry_run: bool = False):
    """Update a whiskey's price and log the change."""
    if dry_run:
        return

    w = db.query(Whiskey).filter(Whiskey.id == whiskey_id).first()
    if not w:
        return

    w.price_usd = price
    w.price_is_estimated = False  # It's a REAL scraped price

    # Log the enrichment (upsert — table has UNIQUE(whiskey_id))
    existing = db.query(PriceEnrichmentLog).filter(
        PriceEnrichmentLog.whiskey_id == whiskey_id
    ).first()
    if existing:
        existing.method = method
        existing.confidence = confidence
        existing.source_detail = source_detail
        existing.original_price = original_price
        existing.enriched_at = datetime.now(timezone.utc)
    else:
        log_entry = PriceEnrichmentLog(
            whiskey_id=whiskey_id,
            method=method,
            confidence=confidence,
            source_detail=source_detail,
            original_price=original_price,
            enriched_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)


# ── Main scraping loop ────────────────────────────────────────────────

def run_scrape(dry_run: bool = False, limit: int = 0,
               resume: bool = False, source: str = "all"):
    """Main scraping workflow."""

    db = SessionLocal()
    progress = load_progress() if resume else {
        "processed_ids": [], "found": 0, "not_found": 0,
        "errors": 0, "iowa_matched": 0, "twe_matched": 0, "updated_at": None,
    }
    processed_ids = set(progress.get("processed_ids", []))

    # Load whiskeys with images that still have estimated prices
    # (no point re-processing ones that already have real prices)
    whiskeys = db.query(Whiskey).filter(
        and_(
            Whiskey.image_url.isnot(None),
            Whiskey.image_url != "",
            Whiskey.price_is_estimated == True,
        )
    ).order_by(Whiskey.rating_count.desc(), Whiskey.name).all()

    total = len(whiskeys)
    log.info("Loaded %d whiskeys with images + estimated prices", total)

    if resume:
        log.info("Resuming: %d already processed", len(processed_ids))

    # Filter to unprocessed
    to_process = [w for w in whiskeys if w.id not in processed_ids]
    if limit > 0:
        to_process = to_process[:limit]

    log.info("Will process %d whiskeys (limit=%d, resume=%s)",
             len(to_process), limit, resume)

    # ── Phase 1: Aggregate all API price sources ─────────────────
    api_prices = {}
    if source in ("all", "iowa", "api"):
        iowa_prices = fetch_iowa_prices()
        api_prices.update(iowa_prices)

        oregon_prices = fetch_oregon_prices()
        # Only add if not already in (Iowa takes priority)
        for k, v in oregon_prices.items():
            if k not in api_prices:
                api_prices[k] = v

        montgomery_prices = fetch_montgomery_prices()
        for k, v in montgomery_prices.items():
            if k not in api_prices:
                api_prices[k] = v

        # Iowa sales transactions — different dataset, more products
        iowa_sales = fetch_iowa_sales_prices()
        for k, v in iowa_sales.items():
            if k not in api_prices:
                api_prices[k] = v

        # LCBO (Ontario, Canada) — good scotch/whisky selection
        lcbo_prices = fetch_lcbo_prices()
        for k, v in lcbo_prices.items():
            if k not in api_prices:
                api_prices[k] = v

        log.info(
            "Combined API prices: %d entries "
            "(Iowa=%d, Oregon=%d, Montgomery=%d, IowaSales=%d, LCBO=%d)",
            len(api_prices), len(iowa_prices), len(oregon_prices),
            len(montgomery_prices), len(iowa_sales), len(lcbo_prices),
        )

        # Build fuzzy index
        api_names = list(api_prices.keys())

    # ── Phase 2: TWE scraper (for scotch/irish/japanese) ────────────
    twe_scraper = None
    if source in ("all", "twe"):
        try:
            twe_scraper = WhiskyExchangeScraper()
            log.info("TWE scraper initialized")
        except Exception as exc:
            log.warning("Could not initialize TWE scraper: %s", exc)

    # ── Process each whiskey ────────────────────────────────────────
    stats = {
        "iowa_matched": progress.get("iowa_matched", 0),
        "twe_matched": progress.get("twe_matched", 0),
        "found": progress.get("found", 0),
        "not_found": progress.get("not_found", 0),
        "errors": progress.get("errors", 0),
    }
    changes = []
    start_time = time.monotonic()

    for i, w in enumerate(to_process):
        if i > 0 and i % 100 == 0:
            elapsed = time.monotonic() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta_min = (len(to_process) - i) / rate / 60 if rate > 0 else 0
            log.info(
                "Progress: %d/%d (%.1f%%) | found=%d, not_found=%d | "
                "rate=%.1f/s, ETA=%.0f min",
                i, len(to_process), 100 * i / len(to_process),
                stats["found"], stats["not_found"],
                rate, eta_min,
            )

        # Save checkpoint every 50
        if i > 0 and i % 50 == 0:
            progress["processed_ids"] = list(processed_ids)
            progress.update(stats)
            save_progress(progress)

        old_price = w.price_usd
        found = False

        # ── Try Iowa first (instant, no network for individual lookups) ──
        if api_prices and source in ("all", "iowa", "api"):
            norm = normalize_for_price(w.name)
            if norm and norm in api_prices:
                price = api_prices[norm]
                # Price ratio guard: skip extreme mismatches even for exact
                # (can happen when vintage years are stripped: "Balblair 1969" -> "balblair")
                ratio = price / old_price if old_price and old_price > 0 else 1
                if 0.1 <= ratio <= 10.0:
                    if not dry_run:
                        apply_price_update(
                            db, w.id, price, "state_api", 0.92,
                            f"API catalog exact match: '{norm}'",
                            old_price, dry_run,
                        )
                    stats["iowa_matched"] += 1
                    stats["found"] += 1
                    found = True
                    changes.append({
                        "id": w.id, "name": w.name,
                        "old_price": old_price, "new_price": price,
                        "source": "iowa", "method": "exact",
                    })
            elif norm and HAS_RAPIDFUZZ:
                # Fuzzy match against Iowa catalog
                best_score = 0
                best_price = None
                best_name = None
                prefix = norm[:4] if len(norm) >= 4 else norm
                for api_name in api_names:
                    if api_name[:4] == prefix or api_name[:3] == norm[:3]:
                        score = fuzz.token_sort_ratio(norm, api_name)
                        # Penalize age mismatches (12yo vs 21yo) and
                        # partial penalty when one has age and other doesn't
                        _, age_penalty = ages_compatible(norm, api_name)
                        score -= age_penalty
                        if score > best_score:
                            best_score = score
                            best_price = api_prices[api_name]
                            best_name = api_name

                if best_score >= 85 and best_price and best_name:
                    # Reject if best match name is much shorter (generic entry)
                    # e.g. "bowmore" (7 chars) matching "bowmore 22yo" (12 chars)
                    len_ratio = len(best_name) / len(norm) if norm else 0
                    if len_ratio < 0.6:
                        # Generic API entry matching a specific whiskey — skip
                        best_score = 0

                if best_score >= 85 and best_price:
                    # Price ratio guard: reject fuzzy matches with extreme changes
                    ratio = best_price / old_price if old_price and old_price > 0 else 1
                    if 0.2 <= ratio <= 5.0:
                        if not dry_run:
                            apply_price_update(
                                db, w.id, best_price, "iowa_liquor", 0.85,
                                f"API catalog fuzzy {best_score:.0f}%: '{best_name}'",
                                old_price, dry_run,
                            )
                        stats["iowa_matched"] += 1
                        stats["found"] += 1
                        found = True
                        changes.append({
                            "id": w.id, "name": w.name,
                            "old_price": old_price, "new_price": best_price,
                            "source": "iowa", "method": f"fuzzy_{best_score:.0f}",
                        })

        # ── Try TWE for non-bourbon or if Iowa didn't match ──────────
        if not found and twe_scraper and source in ("all", "twe"):
            # Skip categories that TWE won't have
            skip_cats = set()  # TWE actually carries all types
            if w.category not in skip_cats:
                try:
                    result = twe_scraper.search_price(
                        w.name,
                        w.distillery or "",
                        w.category or "",
                    )
                    if result:
                        price = result["price_usd"]
                        if not dry_run:
                            apply_price_update(
                                db, w.id, price, "whisky_exchange",
                                min(0.90, result["score"] / 100),
                                f"TWE search match ({result['score']:.0f}%): "
                                f"'{result['matched_name']}'",
                                old_price, dry_run,
                            )
                        stats["twe_matched"] += 1
                        stats["found"] += 1
                        found = True
                        changes.append({
                            "id": w.id, "name": w.name,
                            "old_price": old_price, "new_price": price,
                            "source": "twe",
                            "method": f"search_{result['score']:.0f}",
                            "matched": result["matched_name"],
                        })
                except Exception as exc:
                    log.warning("TWE error for '%s': %s", w.name, exc)
                    stats["errors"] += 1

        if not found:
            stats["not_found"] += 1

        processed_ids.add(w.id)

        # Commit in batches
        if not dry_run and i > 0 and i % 25 == 0:
            try:
                db.commit()
            except Exception as exc:
                log.error("DB commit error: %s", exc)
                db.rollback()

    # Final commit
    if not dry_run:
        try:
            db.commit()
        except Exception as exc:
            log.error("Final commit error: %s", exc)
            db.rollback()

    # Save final progress
    progress["processed_ids"] = list(processed_ids)
    progress.update(stats)
    save_progress(progress)

    # Close TWE scraper
    if twe_scraper:
        twe_scraper.close()

    # ── Generate report ────────────────────────────────────────────
    elapsed = time.monotonic() - start_time
    report = {
        "run_date": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "source": source,
        "total_with_images": total,
        "processed_this_run": len(to_process),
        "total_processed": len(processed_ids),
        "elapsed_seconds": round(elapsed, 1),
        "stats": stats,
        "top_changes": sorted(
            changes,
            key=lambda c: abs((c.get("new_price") or 0) - (c.get("old_price") or 0)),
            reverse=True,
        )[:100],
    }

    REPORT_FILE.write_text(json.dumps(report, indent=2, default=str))
    log.info("Report saved to %s", REPORT_FILE)

    # Print summary
    print("\n" + "=" * 60)
    print("SCRAPE PRICES SUMMARY")
    print("=" * 60)
    print(f"Whiskeys with estimated prices: {total}")
    print(f"Processed this run:             {len(to_process)}")
    print(f"Total processed (all runs):     {len(processed_ids)}")
    print(f"Found real prices:              {stats['found']}")
    print(f"  - API sources:                {stats['iowa_matched']}")
    print(f"  - Whisky Exchange:            {stats['twe_matched']}")
    print(f"Not found:                      {stats['not_found']}")
    print(f"Errors:                         {stats['errors']}")
    print(f"Elapsed:                        {elapsed/60:.1f} minutes")
    if changes:
        print(f"\nTop 10 price changes:")
        for c in sorted(changes, key=lambda x: abs((x.get("new_price") or 0) - (x.get("old_price") or 0)), reverse=True)[:10]:
            old = c.get("old_price") or 0
            new = c.get("new_price") or 0
            print(f"  ${old:>8.2f} → ${new:>8.2f} | {c['name'][:50]} [{c['source']}]")
    print("=" * 60)

    db.close()


# ── Backup ────────────────────────────────────────────────────────────

def backup_db():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"sipsense.db.backup_scrape_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    log.info("Backup created: %s", backup_path)
    return backup_path


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape real retail prices for whiskeys with images"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without updating DB")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max whiskeys to process (0 = all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last checkpoint")
    parser.add_argument("--source", choices=["all", "iowa", "api", "twe"],
                        default="all",
                        help="Which price source to use (api=Iowa+Oregon+Montgomery)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip database backup")
    args = parser.parse_args()

    if not args.dry_run and not args.no_backup:
        backup_db()

    run_scrape(
        dry_run=args.dry_run,
        limit=args.limit,
        resume=args.resume,
        source=args.source,
    )


if __name__ == "__main__":
    main()
