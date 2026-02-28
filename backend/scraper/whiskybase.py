"""
Whiskybase.com scraper.

Two-phase approach:
  Phase 1 — listing pages (fast, 50 whiskeys per request)
             extracts: name, distillery, country, age, ABV, community rating
  Phase 2 — detail pages (slower, 1 request per whiskey)
             extracts: description, tasting notes / flavor tags

Phase 2 is only run when fetch_details=True (default False for speed).
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from .base import RateLimitedClient

log = logging.getLogger(__name__)

BASE_URL = "https://www.whiskybase.com"
LIST_URL = f"{BASE_URL}/whiskies"


class WhiskybaseScraper:
    """
    Scrapes whiskybase.com for whiskey metadata.

    Usage:
        with WhiskybaseScraper() as scraper:
            for whiskey in scraper.iter_whiskeys(limit=500):
                print(whiskey)
    """

    def __init__(self, fetch_details: bool = False, verbose: bool = False):
        self.fetch_details = fetch_details
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=1.5, max_delay=3.0)

    # ── public API ────────────────────────────────────────────────────────

    def iter_whiskeys(self, limit: int = 10_000, start_offset: int = 0):
        """
        Generator that yields raw whiskey dicts scraped from Whiskybase.
        Stops after `limit` whiskeys or when no more pages exist.
        """
        scraped = 0
        offset = start_offset
        page_size = 50

        while scraped < limit:
            url = f"{LIST_URL}?limit={page_size}&start={offset}"
            if self.verbose:
                log.info("Fetching listing page offset=%d", offset)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.error("Failed to fetch listing page offset=%d: %s", offset, exc)
                break

            items = self._parse_listing(resp.text)
            if not items:
                log.info("No items on page offset=%d — done.", offset)
                break

            for item in items:
                if scraped >= limit:
                    return

                if self.fetch_details and item.get("detail_url"):
                    try:
                        detail = self._fetch_detail(item["detail_url"])
                        item.update(detail)
                    except Exception as exc:
                        log.warning("Detail fetch failed for %s: %s", item.get("name"), exc)

                yield item
                scraped += 1

            offset += page_size

    # ── listing page parser ───────────────────────────────────────────────

    def _parse_listing(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Whiskybase renders a table with class "whiskies" or a grid of items
        # Try table rows first, then fall back to article/div cards
        rows = soup.select("table.whiskies tbody tr")
        if rows:
            for row in rows:
                item = self._parse_listing_row(row)
                if item:
                    results.append(item)
            return results

        # Fallback: card-style listing
        cards = soup.select("li.whisky-item, div.whisky-card, article.whisky")
        for card in cards:
            item = self._parse_listing_card(card)
            if item:
                results.append(item)

        return results

    def _parse_listing_row(self, row) -> Optional[dict]:
        """Parse a <tr> row from the whiskies table."""
        try:
            cells = row.find_all("td")
            if len(cells) < 3:
                return None

            # Link + name
            link_tag = row.find("a", href=re.compile(r"/whiskies/\d+"))
            if not link_tag:
                return None

            name = link_tag.get_text(strip=True)
            detail_url = BASE_URL + link_tag["href"] if link_tag.get("href", "").startswith("/") else link_tag["href"]

            # Extract structured fields from cells
            # Column order varies — use text content + aria labels where possible
            raw = {c.get("data-label", f"col{i}"): c.get_text(strip=True)
                   for i, c in enumerate(cells)}

            return {
                "name": name,
                "detail_url": detail_url,
                "distillery": self._find_cell(raw, ["distillery", "brand", "col1"]),
                "country": self._find_cell(raw, ["country", "col2"]),
                "region": self._find_cell(raw, ["region", "col3"]),
                "age_str": self._find_cell(raw, ["age", "col4"]),
                "abv_str": self._find_cell(raw, ["strength", "abv", "col5"]),
                "rating_str": self._find_cell(raw, ["rating", "score", "col6"]),
                "votes_str": self._find_cell(raw, ["votes", "col7"]),
            }
        except Exception as exc:
            log.debug("Row parse error: %s", exc)
            return None

    def _parse_listing_card(self, card) -> Optional[dict]:
        """Parse a card-style element (fallback for non-table layouts)."""
        try:
            link_tag = card.find("a", href=re.compile(r"/whiskies/\d+"))
            if not link_tag:
                return None

            name_tag = card.find(class_=re.compile(r"name|title")) or link_tag
            distillery_tag = card.find(class_=re.compile(r"distill|brand|producer"))
            country_tag = card.find(class_=re.compile(r"country|origin"))
            abv_tag = card.find(class_=re.compile(r"strength|abv|alcohol"))
            age_tag = card.find(class_=re.compile(r"\bage\b"))
            rating_tag = card.find(class_=re.compile(r"rating|score"))

            detail_url = BASE_URL + link_tag["href"] if link_tag.get("href", "").startswith("/") else link_tag["href"]

            return {
                "name": name_tag.get_text(strip=True) if name_tag else None,
                "detail_url": detail_url,
                "distillery": distillery_tag.get_text(strip=True) if distillery_tag else None,
                "country": country_tag.get_text(strip=True) if country_tag else None,
                "region": None,
                "age_str": age_tag.get_text(strip=True) if age_tag else None,
                "abv_str": abv_tag.get_text(strip=True) if abv_tag else None,
                "rating_str": rating_tag.get_text(strip=True) if rating_tag else None,
                "votes_str": None,
            }
        except Exception as exc:
            log.debug("Card parse error: %s", exc)
            return None

    # ── detail page parser ────────────────────────────────────────────────

    def _fetch_detail(self, url: str) -> dict:
        resp = self._client.get(url)
        return self._parse_detail(resp.text)

    def _parse_detail(self, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        extra = {}

        # Description / about text
        desc_el = soup.find(class_=re.compile(r"description|about|notes|tasting"))
        if desc_el:
            extra["description"] = desc_el.get_text(" ", strip=True)[:1000]

        # Flavor / nose / palate / finish tags
        flavor_tags = []
        for tag_el in soup.select(".flavor-tag, .note-tag, .taste-tag, [data-tag]"):
            t = tag_el.get_text(strip=True).lower()
            if t:
                flavor_tags.append(t)

        # Also look for nose/palate/finish sections and extract keywords
        for section_class in ["nose", "palate", "finish"]:
            el = soup.find(class_=re.compile(section_class, re.I))
            if el:
                text = el.get_text(" ", strip=True)
                # Extract individual flavor words (short, single words)
                words = [w.strip(".,;") for w in text.split() if 3 <= len(w) <= 12]
                flavor_tags.extend(words[:5])  # max 5 words per section

        if flavor_tags:
            extra["flavor_profile"] = ", ".join(dict.fromkeys(flavor_tags))  # deduplicate, preserve order

        # Price (if shown)
        price_el = soup.find(class_=re.compile(r"price|cost"))
        if price_el:
            extra["price_str"] = price_el.get_text(strip=True)

        return extra

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _find_cell(raw: dict, keys: list[str]) -> Optional[str]:
        for k in keys:
            for rk, rv in raw.items():
                if k.lower() in rk.lower() and rv:
                    return rv
        return None

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
