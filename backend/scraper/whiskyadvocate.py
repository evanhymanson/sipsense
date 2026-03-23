"""
Whisky Advocate reviews scraper.

Source: https://whiskyadvocate.com/ratings-reviews/
Data: 7,000+ expert-reviewed whiskeys with scores, prices, and styles.

Strategy:
  1. Paginate through the ratings/reviews listing pages
  2. Parse review cards with name, score, price, style, brand
  3. Normalize and yield

Rate limit: 2.0-4.0s per request.
"""

import logging
import re
from typing import Generator, Optional

from bs4 import BeautifulSoup

from .base import RateLimitedClient
from .normalizer import normalize

log = logging.getLogger(__name__)

BASE_URL = "https://whiskyadvocate.com"
REVIEWS_URL = f"{BASE_URL}/ratings-reviews/"


class WhiskyAdvocateScraper:
    """
    Scrapes whiskey reviews from Whisky Advocate.

    Usage:
        with WhiskyAdvocateScraper() as scraper:
            for raw in scraper.iter_whiskeys(limit=10000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=2.0, max_delay=4.0)

    def iter_whiskeys(
        self,
        limit: int = 10_000,
        start_page: int = 1,
    ) -> Generator[dict, None, None]:
        """
        Yields normalized whiskey dicts from Whisky Advocate reviews.

        Args:
            limit: Maximum number of whiskeys to yield
            start_page: Page number to start from (for resumability)
        """
        page = start_page
        yielded = 0
        empty_pages = 0

        while yielded < limit:
            url = f"{REVIEWS_URL}?page={page}" if page > 1 else REVIEWS_URL

            if self.verbose:
                log.info("Fetching page %d: %s", page, url)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.warning("Failed to fetch page %d: %s", page, exc)
                empty_pages += 1
                if empty_pages >= 3:
                    log.info("3 consecutive failures — stopping.")
                    break
                page += 1
                continue

            reviews = self._parse_reviews_page(resp.text)

            if not reviews:
                empty_pages += 1
                if empty_pages >= 3:
                    log.info("3 consecutive empty pages — reached end.")
                    break
                page += 1
                continue

            empty_pages = 0

            for raw in reviews:
                if yielded >= limit:
                    return

                normalized = normalize(raw)
                if normalized is None:
                    continue

                normalized["source"] = "whiskyadvocate"
                yield normalized
                yielded += 1

            page += 1

        log.info(
            "Whisky Advocate: yielded %d whiskeys from %d pages",
            yielded, page - start_page,
        )

    def _parse_reviews_page(self, html: str) -> list[dict]:
        """Parse review cards from a reviews listing page."""
        soup = BeautifulSoup(html, "lxml")
        reviews = []

        # Try multiple selectors for review cards
        cards = (
            soup.select("div.review-card")
            or soup.select("article.review")
            or soup.select("div.rating-card")
            or soup.select("div.review-item")
            or soup.select("div.result-item")
            or soup.select("li.review")
        )

        if not cards:
            # Fallback: look for structured review data
            cards = self._find_review_elements(soup)

        for card in cards:
            raw = self._parse_review_card(card)
            if raw and raw.get("name"):
                reviews.append(raw)

        return reviews

    def _find_review_elements(self, soup: BeautifulSoup) -> list:
        """Fallback: find elements that look like whiskey reviews."""
        candidates = []
        for div in soup.find_all(["div", "article", "li"]):
            text = div.get_text(" ", strip=True)
            # Reviews typically have a score (number) and a price ($)
            if (
                re.search(r"\b\d{2,3}\b", text)
                and len(text) > 20
                and len(text) < 1000
            ):
                # Check for whiskey-like content
                lower = text.lower()
                if any(
                    kw in lower
                    for kw in ["whiskey", "whisky", "bourbon", "scotch", "rye", "malt"]
                ):
                    candidates.append(div)
        return candidates[:200]  # cap to avoid processing entire page

    def _parse_review_card(self, card) -> Optional[dict]:
        """Extract review data from a single review card."""
        text = card.get_text(" ", strip=True)
        if not text or len(text) < 10:
            return None

        # Extract name
        name = None
        for tag in ["h2", "h3", "h4", "a.review-title", "strong", "a"]:
            el = card.select_one(tag) if "." in tag else card.find(tag)
            if el:
                candidate = el.get_text(strip=True)
                if candidate and len(candidate) > 3:
                    name = candidate
                    break

        if not name:
            return None

        # Extract score (typically 2-3 digit number)
        score_str = None
        score_el = card.select_one("span.score, div.score, span.rating, div.points")
        if score_el:
            score_str = score_el.get_text(strip=True)
        else:
            score_match = re.search(r"\b(\d{2,3})\s*(?:points?|pts?)?\b", text)
            if score_match:
                val = int(score_match.group(1))
                if 50 <= val <= 100:  # WA uses ~50-100 scale
                    score_str = str(val)

        # Extract price
        price_str = None
        price_el = card.select_one("span.price, div.price")
        if price_el:
            price_str = price_el.get_text(strip=True)
        else:
            price_match = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", text)
            if price_match:
                price_str = price_match.group(1)

        # Extract style/category
        category = ""
        style_el = card.select_one("span.style, div.style, span.category, div.type")
        if style_el:
            category = style_el.get_text(strip=True)

        # Extract ABV from name or text
        abv_str = None
        abv_match = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", text)
        if abv_match:
            abv_str = abv_match.group(1)

        # Extract age
        age_str = None
        age_match = re.search(r"(\d{1,2})\s*(?:year|yr|yo|y\.o)", name, re.I)
        if age_match:
            age_str = age_match.group(1)

        # Infer country
        country = _infer_country_from_review(name, category, text)

        return {
            "name": name,
            "category": category,
            "country": country,
            "abv_str": abv_str or "40.0",
            "age_str": age_str,
            "rating_str": score_str,
            "price_str": price_str,
            "source": "whiskyadvocate",
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _infer_country_from_review(name: str, category: str, text: str) -> str:
    """Infer country from review context."""
    combined = f"{name} {category} {text}".lower()
    if "scotch" in combined or "scotland" in combined:
        return "scotland"
    if "bourbon" in combined or "tennessee" in combined:
        return "usa"
    if "irish" in combined or "ireland" in combined:
        return "ireland"
    if "japanese" in combined or "japan" in combined:
        return "japan"
    if "canadian" in combined or "canada" in combined:
        return "canada"
    if "american" in combined:
        return "usa"
    return ""
