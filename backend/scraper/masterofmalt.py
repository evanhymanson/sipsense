"""
Master of Malt scraper.

Scrapes the whisky listing pages at masterofmalt.com. Uses the product
grid pages with pagination. Handles two common HTML layouts (grid cards
and list rows) with multiple fallback selectors so it degrades gracefully
if they redesign the site.

Rate limit: 2-4s between requests. MoM has light anti-bot measures;
the existing RateLimitedClient handles backoff on 429.

Notes on price: prices are in GBP (£). The normalizer stores them as a
float — that's fine for relative price comparisons even if not USD.
"""

import logging
import re
from typing import Optional, Generator

from bs4 import BeautifulSoup

from .base import RateLimitedClient

log = logging.getLogger(__name__)

BASE_URL = "https://www.masterofmalt.com"
# Category listing page — whiskies only, 48 items per page
LIST_URL = f"{BASE_URL}/whiskies/"
PAGE_SIZE = 48


class MasterOfMaltScraper:
    """
    Scrapes masterofmalt.com product listings for whisky entries.

    Usage:
        with MasterOfMaltScraper() as s:
            for raw in s.iter_whiskeys(limit=5000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=2.0, max_delay=4.0)

    def iter_whiskeys(self, limit: int = 20_000, start_offset: int = 0) -> Generator[dict, None, None]:
        """Yield raw whiskey dicts from paginated listing pages."""
        scraped = 0
        start = start_offset

        while scraped < limit:
            url = f"{LIST_URL}?start={start}&size={PAGE_SIZE}"
            if self.verbose:
                log.info("MoM: fetching page start=%d", start)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.error("MoM: failed to fetch start=%d: %s", start, exc)
                break

            items = self._parse_page(resp.text)
            if not items:
                log.info("MoM: no items at start=%d — done", start)
                break

            for item in items:
                if scraped >= limit:
                    return
                yield item
                scraped += 1

            # If we got fewer results than page size, we're on the last page
            if len(items) < PAGE_SIZE:
                break

            start += PAGE_SIZE

        log.info("MoM: finished — yielded %d entries", scraped)

    def _parse_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Try product card selectors — MoM has used several layouts
        cards = (
            soup.select("div.productcell")
            or soup.select("div.product-cell")
            or soup.select("li.product-item")
            or soup.select("div.product")
        )

        for card in cards:
            item = self._parse_card(card)
            if item:
                results.append(item)

        if self.verbose:
            log.info("MoM: parsed %d items from page", len(results))
        return results

    def _parse_card(self, card) -> Optional[dict]:
        try:
            # ── Name ─────────────────────────────────────────────────────
            name_el = (
                card.find(class_=re.compile(r"name|title|product-name", re.I))
                or card.find("h2")
                or card.find("h3")
                or card.find("a")
            )
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                return None

            # ── Link / detail URL ─────────────────────────────────────────
            link = card.find("a", href=True)
            detail_url = (BASE_URL + link["href"] if link and link["href"].startswith("/") else None)

            # ── Distillery ───────────────────────────────────────────────
            distillery_el = card.find(class_=re.compile(r"distill|brand|producer|maker", re.I))
            distillery = distillery_el.get_text(strip=True) if distillery_el else _extract_distillery(name)

            # ── ABV ──────────────────────────────────────────────────────
            abv_el = card.find(class_=re.compile(r"abv|alcohol|strength", re.I))
            abv_str = abv_el.get_text(strip=True) if abv_el else _grep_abv(card.get_text(" "))

            # ── Age ──────────────────────────────────────────────────────
            age_str = _extract_age(name)

            # ── Price ────────────────────────────────────────────────────
            price_el = card.find(class_=re.compile(r"price|cost", re.I))
            price_str = price_el.get_text(strip=True) if price_el else None

            # ── Rating ───────────────────────────────────────────────────
            rating_el = card.find(class_=re.compile(r"rating|score|stars", re.I))
            rating_str = rating_el.get_text(strip=True) if rating_el else None

            # ── Category / country inferred from name ────────────────────
            category, country = _infer_category_country(name)

            return {
                "name":         name,
                "distillery":   distillery or "Unknown",
                "abv_str":      abv_str,
                "age_str":      age_str,
                "price_str":    price_str,
                "rating_str":   rating_str,
                "category":     category,
                "country":      country,
                "region":       None,
                "description":  None,
                "flavor_profile": None,
                "source":       "masterofmalt",
            }
        except Exception as exc:
            log.debug("MoM: card parse error: %s", exc)
            return None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _grep_abv(text: str) -> Optional[str]:
    """Extract first XX% pattern from card text."""
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", text)
    return m.group(0) if m else None


def _extract_age(name: str) -> Optional[str]:
    """Pull age out of the product name ('18 Year Old', '12YO', etc.)."""
    m = re.search(r"(\d{1,2})\s*(?:year|yr|yo)", name, re.I)
    return m.group(1) if m else None


def _extract_distillery(name: str) -> str:
    """Best-effort: use the first word(s) before 'XX Year Old' as distillery."""
    m = re.match(r"^([A-Za-z\s']+?)(?:\s+\d)", name)
    return m.group(1).strip() if m else name.split()[0]


def _infer_category_country(name: str) -> tuple[str, str]:
    n = name.lower()
    if "bourbon" in n:        return "bourbon", "usa"
    if "tennessee" in n:      return "bourbon", "usa"
    if "rye" in n:            return "rye", "usa"
    if "irish" in n:          return "irish", "ireland"
    if "japanese" in n or "japan" in n: return "japanese", "japan"
    if "canadian" in n:       return "canadian", "canada"
    if "scotch" in n or "single malt" in n or "blended" in n:
        return "scotch", "scotland"
    return "scotch", "scotland"   # MoM is UK-focused; scotch is the safe default
