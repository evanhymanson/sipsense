"""
The Whisky Exchange scraper.

Scrapes thewhiskyexchange.com product listings. TWE is one of the world's
largest online whisky retailers (~15k+ whisky SKUs) with rich data:
region, tasting notes, age, ABV, price.

Pagination: ?pg=N&psize=24
Category: /c/40/whiskies (all whiskies)

Rate limit: 2-4s between requests. TWE has moderate anti-bot measures.
"""

import logging
import re
from typing import Optional, Generator

from bs4 import BeautifulSoup

from .base import RateLimitedClient

log = logging.getLogger(__name__)

BASE_URL = "https://www.thewhiskyexchange.com"
LIST_URL = f"{BASE_URL}/c/40/whiskies"
PAGE_SIZE = 24


class WhiskyExchangeScraper:
    """
    Scrapes The Whisky Exchange product listings for whisky entries.

    Usage:
        with WhiskyExchangeScraper() as s:
            for raw in s.iter_whiskeys(limit=15000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=2.0, max_delay=4.0)

    def iter_whiskeys(self, limit: int = 15_000, start_page: int = 1) -> Generator[dict, None, None]:
        """Yield raw whiskey dicts from paginated TWE listing pages."""
        scraped = 0
        page = start_page

        while scraped < limit:
            url = f"{LIST_URL}?pg={page}&psize={PAGE_SIZE}"
            if self.verbose:
                log.info("TWE: fetching page %d", page)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.error("TWE: failed to fetch page %d: %s", page, exc)
                break

            items = self._parse_page(resp.text)
            if not items:
                log.info("TWE: no items on page %d — done", page)
                break

            for item in items:
                if scraped >= limit:
                    return
                yield item
                scraped += 1

            if len(items) < PAGE_SIZE:
                break

            page += 1

        log.info("TWE: finished — yielded %d entries", scraped)

    def _parse_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # TWE uses several class patterns depending on page version
        cards = (
            soup.select("li.ProductCard")
            or soup.select("li.product-card")
            or soup.select("div.ProductCard")
            or soup.select("article.product")
            or soup.select("li[class*='product']")
        )

        for card in cards:
            item = self._parse_card(card)
            if item:
                results.append(item)

        if self.verbose:
            log.info("TWE: parsed %d items", len(results))
        return results

    def _parse_card(self, card) -> Optional[dict]:
        try:
            # ── Name ─────────────────────────────────────────────────────
            name_el = (
                card.find(class_=re.compile(r"ProductCard-name|product-name|name", re.I))
                or card.find("p", class_=re.compile(r"name|title", re.I))
                or card.find("h2")
                or card.find("h3")
            )
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                return None

            # ── Detail URL ───────────────────────────────────────────────
            link = card.find("a", href=True)
            detail_url = (BASE_URL + link["href"] if link and link["href"].startswith("/") else None)

            # ── Distillery / producer ────────────────────────────────────
            distillery_el = card.find(class_=re.compile(r"ProductCard-distillery|distillery|producer|brand", re.I))
            distillery = distillery_el.get_text(strip=True) if distillery_el else _extract_distillery(name)

            # ── ABV ──────────────────────────────────────────────────────
            full_text = card.get_text(" ")
            abv_el = card.find(class_=re.compile(r"abv|alcohol|strength", re.I))
            abv_str = abv_el.get_text(strip=True) if abv_el else _grep_abv(full_text)

            # ── Age ──────────────────────────────────────────────────────
            age_str = _extract_age(name)

            # ── Price ────────────────────────────────────────────────────
            price_el = (
                card.find(class_=re.compile(r"ProductCard-price|price|cost", re.I))
                or card.find("span", class_=re.compile(r"price", re.I))
            )
            price_str = price_el.get_text(strip=True) if price_el else None

            # ── Region ───────────────────────────────────────────────────
            region_el = card.find(class_=re.compile(r"region|origin", re.I))
            region_str = region_el.get_text(strip=True) if region_el else None

            # ── Category / country ───────────────────────────────────────
            type_el = card.find(class_=re.compile(r"ProductCard-type|type|category", re.I))
            type_str = type_el.get_text(strip=True) if type_el else ""

            category, country = _infer_category_country(name, type_str, region_str)

            return {
                "name":           name,
                "distillery":     distillery or "Unknown",
                "abv_str":        abv_str,
                "age_str":        age_str,
                "price_str":      price_str,
                "rating_str":     None,
                "category":       category,
                "country":        country,
                "region":         region_str,
                "description":    None,
                "flavor_profile": None,
                "source":         "whiskyexchange",
            }
        except Exception as exc:
            log.debug("TWE: card parse error: %s", exc)
            return None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _grep_abv(text: str) -> Optional[str]:
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:abv|vol)?", text, re.I)
    return m.group(0) if m else None


def _extract_age(name: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})\s*(?:year|yr|yo)", name, re.I)
    return m.group(1) if m else None


def _extract_distillery(name: str) -> str:
    m = re.match(r"^([A-Za-z\s'']+?)(?:\s+\d)", name)
    return m.group(1).strip() if m else name.split()[0]


def _infer_category_country(name: str, type_str: str, region: Optional[str]) -> tuple[str, str]:
    combined = (name + " " + type_str + " " + (region or "")).lower()
    if "bourbon" in combined:           return "bourbon", "usa"
    if "tennessee" in combined:         return "bourbon", "usa"
    if "rye" in combined and "canada" not in combined: return "rye", "usa"
    if "irish" in combined:             return "irish", "ireland"
    if "japanese" in combined or "japan" in combined: return "japanese", "japan"
    if "canadian" in combined:          return "canadian", "canada"
    if "single malt" in combined:       return "single malt", "scotland"
    if "blended" in combined:           return "blended", "scotland"
    if "scotch" in combined:            return "scotch", "scotland"
    # TWE has large scotch inventory — default to scotch
    return "scotch", "scotland"
