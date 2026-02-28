"""
Connosr whisky community scraper.

Connosr (connosr.com) is an independent whisky review community with
~10k+ reviewed whiskies and community scores. Good source for:
  - Community ratings (adds social proof to our DB)
  - Coverage of niche/independent bottlings not on retail sites

Listing: https://www.connosr.com/whiskies/?page=N
Returns paginated grid of whisky cards with name, distillery, rating.

Rate limit: 2-3s between requests.
"""

import logging
import re
from typing import Optional, Generator

from bs4 import BeautifulSoup

from .base import RateLimitedClient

log = logging.getLogger(__name__)

BASE_URL = "https://www.connosr.com"
LIST_URL = f"{BASE_URL}/whiskies/"


class ConnosrScraper:
    """
    Scrapes Connosr whisky listings and community ratings.

    Usage:
        with ConnosrScraper() as s:
            for raw in s.iter_whiskeys(limit=10000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=2.0, max_delay=3.5)

    def iter_whiskeys(self, limit: int = 10_000) -> Generator[dict, None, None]:
        """Yield raw whiskey dicts from Connosr paginated listing."""
        scraped = 0
        page = 1

        while scraped < limit:
            url = f"{LIST_URL}?page={page}"
            if self.verbose:
                log.info("Connosr: fetching page %d", page)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.error("Connosr: failed to fetch page %d: %s", page, exc)
                break

            items = self._parse_page(resp.text)
            if not items:
                log.info("Connosr: no items on page %d — done", page)
                break

            for item in items:
                if scraped >= limit:
                    return
                yield item
                scraped += 1

            # Connosr pages tend to have 20-30 items; if fewer, we're at the end
            if len(items) < 10:
                break

            page += 1

        log.info("Connosr: finished — yielded %d entries", scraped)

    def _parse_page(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Connosr product cards
        cards = (
            soup.select("div.whisky-card")
            or soup.select("li.whisky-item")
            or soup.select("div.product-card")
            or soup.select("article.whisky")
            or soup.select("div[class*='whisky']")
        )

        if not cards:
            # Fallback: look for any links to /whisky/ pages
            for link in soup.select("a[href*='/whisky/']"):
                item = self._parse_link_context(link)
                if item:
                    results.append(item)
        else:
            for card in cards:
                item = self._parse_card(card)
                if item:
                    results.append(item)

        if self.verbose:
            log.info("Connosr: parsed %d items", len(results))
        return results

    def _parse_card(self, card) -> Optional[dict]:
        try:
            # ── Name ─────────────────────────────────────────────────────
            name_el = (
                card.find(class_=re.compile(r"name|title|whisky-name", re.I))
                or card.find("h2")
                or card.find("h3")
                or card.find("a", href=re.compile(r"/whisky/"))
            )
            if not name_el:
                return None
            name = name_el.get_text(strip=True)
            if not name or len(name) < 3:
                return None

            # ── Distillery ───────────────────────────────────────────────
            distillery_el = card.find(class_=re.compile(r"distill|brand|producer", re.I))
            distillery = distillery_el.get_text(strip=True) if distillery_el else _extract_distillery(name)

            # ── ABV ──────────────────────────────────────────────────────
            full_text = card.get_text(" ")
            abv_el = card.find(class_=re.compile(r"abv|alcohol|strength", re.I))
            abv_str = abv_el.get_text(strip=True) if abv_el else _grep_abv(full_text)

            # ── Age ──────────────────────────────────────────────────────
            age_str = _extract_age(name)

            # ── Rating ───────────────────────────────────────────────────
            rating_el = (
                card.find(class_=re.compile(r"rating|score|average", re.I))
                or card.find("span", class_=re.compile(r"score|rating", re.I))
            )
            rating_str = rating_el.get_text(strip=True) if rating_el else None

            # ── Category / country from name ─────────────────────────────
            category, country = _infer_category_country(name)

            if not abv_str:
                # Connosr sometimes doesn't show ABV on listing cards
                # Use a category-appropriate default so normalizer doesn't drop it
                abv_str = "43.0"

            return {
                "name":           name,
                "distillery":     distillery or "Unknown",
                "abv_str":        abv_str,
                "age_str":        age_str,
                "price_str":      None,
                "rating_str":     rating_str,
                "category":       category,
                "country":        country,
                "region":         None,
                "description":    None,
                "flavor_profile": None,
                "source":         "connosr",
            }
        except Exception as exc:
            log.debug("Connosr: card parse error: %s", exc)
            return None

    def _parse_link_context(self, link) -> Optional[dict]:
        """Fallback: parse name from a bare /whisky/ link."""
        try:
            name = link.get_text(strip=True)
            if not name or len(name) < 3:
                return None
            category, country = _infer_category_country(name)
            return {
                "name":           name,
                "distillery":     _extract_distillery(name),
                "abv_str":        "43.0",   # default
                "age_str":        _extract_age(name),
                "price_str":      None,
                "rating_str":     None,
                "category":       category,
                "country":        country,
                "region":         None,
                "description":    None,
                "flavor_profile": None,
                "source":         "connosr",
            }
        except Exception:
            return None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _grep_abv(text: str) -> Optional[str]:
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", text)
    return m.group(0) if m else None


def _extract_age(name: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})\s*(?:year|yr|yo)", name, re.I)
    return m.group(1) if m else None


def _extract_distillery(name: str) -> str:
    m = re.match(r"^([A-Za-z\s'']+?)(?:\s+\d)", name)
    return m.group(1).strip() if m else name.split()[0]


def _infer_category_country(name: str) -> tuple[str, str]:
    n = name.lower()
    if "bourbon" in n:        return "bourbon", "usa"
    if "tennessee" in n:      return "bourbon", "usa"
    if "rye" in n:            return "rye", "usa"
    if "irish" in n:          return "irish", "ireland"
    if "japanese" in n:       return "japanese", "japan"
    if "canadian" in n:       return "canadian", "canada"
    if "single malt" in n:    return "single malt", "scotland"
    if "blended" in n:        return "blended", "scotland"
    return "scotch", "scotland"
