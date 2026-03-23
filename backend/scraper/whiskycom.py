"""
Whisky.com database scraper.

Source: https://www.whisky.com/whisky-database/bottle-search.html
Data: 41,136 bottles with name, ABV, rating, rating count, description.

Strategy:
  1. Paginate listing pages (16 bottles per page, ~2,571 pages)
  2. Parse bottle cards from HTML
  3. Optionally fetch detail pages for enhanced metadata

Rate limit: 2.0-3.5s per request (polite crawling).
Full listing scrape: ~2 hours. Detail pages: ~28 hours (optional).
"""

import logging
import re
from typing import Generator, Optional

from bs4 import BeautifulSoup

from .base import RateLimitedClient
from .normalizer import normalize

log = logging.getLogger(__name__)

# Patterns to clean from whisky.com names (German site, messy formatting)
_CLEAN_PATTERNS = [
    # Retailer names: "Whisky.de GmbH & Co. KG", "Whisky.de Clubflasche"
    re.compile(r"\s*Whisky\.de\b.*$", re.I),
    # Bottle sizes: "0.7l", "700ml", "70cl", "1l", "1.0l"
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ml|cl|l|liter|litre)\b", re.I),
    # ABV already in name: "46%", "- 46% -", "46.0%"
    re.compile(r"-?\s*\d{2,3}(?:\.\d+)?\s*%\s*(?:vol\.?)?\s*-?", re.I),
    # Bottling metadata: "Original bottling 4.0", "Other bottler 4.1", etc.
    re.compile(r"\s*(?:Original bottling|Other bottler|Distillery bottling)\s*\d*\.?\d*\s*$", re.I),
    # German phrases with "mit/with": "mit zwei Gläsern", "with Tasse + Grußkarte"
    re.compile(r"\s*-?\s*(?:mit|with)\s+.+$", re.I),
    # German phrases: "neues Design", "neue Ausstattung", "inkl. Golden Ticket"
    re.compile(r"\s*-?\s*neues?\s+\w+.*$", re.I),
    re.compile(r"\s*-?\s*neue\s+\w+.*$", re.I),
    re.compile(r"\s*-?\s*inkl\.?\s+.*$", re.I),
    # English metadata: "new Casing", "Traditionally Peated", "specially ..."
    re.compile(r"\s*-?\s*new\s+\w+\s*-?\s*", re.I),
    re.compile(r"\s*-?\s*(?:Traditionally|specially)\s+\w+\s*-?\s*", re.I),
    # Stray year prefixes: "/ 2019", "- 2020"
    re.compile(r"\s*[/\-]\s*(?:19|20)\d{2}\s*", re.I),
    # Bare trailing year: "2019" at end
    re.compile(r"\s+(?:19|20)\d{2}\s*$"),
    # Trailing rating/score: "4.0", "4.1", bare "0" at end
    re.compile(r"\s+\d\.\d\s*$"),
    re.compile(r"\s+0\s*$"),
    # Clean up multiple dashes: "- -", " - "
    re.compile(r"\s*-\s*-\s*"),
    # Trailing/leading dashes and slashes
    re.compile(r"^\s*[-/]\s*|\s*[-/]\s*$"),
]


def _clean_whiskycom_name(name: str) -> str:
    """Clean German-format whisky.com names into standard English form."""
    # Strip leading dates: "26. Feb 2026 Bowmore..." → "Bowmore..."
    name = re.sub(
        r"^\d{1,2}\.\s*(?:Jan|Feb|Mär|Mar|Apr|Mai|May|Jun|Jul|Aug|Sep|Okt|Oct|Nov|Dez|Dec)\s*\d{4}\s*",
        "", name, flags=re.I
    )
    # Strip parenthetical junk: "( box)", "(Gift Set)", "(3x 5cl)"
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    # Split camelCase gluing from scraper: "TaliskerPort" → "Talisker Port"
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Insert space around slash-glued words: "Glendronach/2019" → "Glendronach / 2019"
    name = re.sub(r"(\w)/(\w)", r"\1 / \2", name)

    for pat in _CLEAN_PATTERNS:
        name = pat.sub(" ", name)

    # Insert space before age markers: "Lomond12Y" → "Lomond 12Y"
    # And after: "21YParliament" → "21Y Parliament", "25Y0" → "25Y 0"
    name = re.sub(r"([a-zA-Z])(\d{1,2}Y)", r"\1 \2", name)
    name = re.sub(r"(\d{1,2}Y)([A-Za-z0-9])", r"\1 \2", name)

    # Second pass: clean trailing junk exposed by age splitting
    name = re.sub(r"\s+0\s*$", "", name)
    name = re.sub(r"\s+\d\.\d\s*$", "", name)

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    # Strip trailing punctuation
    name = name.strip("- ,./")
    return name


BASE_URL = "https://www.whisky.com"
SEARCH_URL = f"{BASE_URL}/whisky-database/bottle-search.html"
PAGE_PARAM = "tx_datamintsflaschendb_pi4[curPage]"
BOTTLES_PER_PAGE = 16


class WhiskyComScraper:
    """
    Scrapes whiskey data from whisky.com's bottle database.

    Usage:
        with WhiskyComScraper() as scraper:
            for raw in scraper.iter_whiskeys(limit=5000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=2.0, max_delay=3.5)

    def iter_whiskeys(
        self,
        limit: int = 50_000,
        start_page: int = 1,
    ) -> Generator[dict, None, None]:
        """
        Yields normalized whiskey dicts from whisky.com listing pages.

        Args:
            limit: Maximum number of whiskeys to yield
            start_page: Page number to start from (for resumability)
        """
        page = start_page
        yielded = 0
        empty_pages = 0

        while yielded < limit:
            url = f"{SEARCH_URL}?{PAGE_PARAM}={page}"

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

            bottles = self._parse_listing_page(resp.text)

            if not bottles:
                empty_pages += 1
                if empty_pages >= 3:
                    log.info("3 consecutive empty pages — reached end of database.")
                    break
                page += 1
                continue

            empty_pages = 0

            for raw in bottles:
                if yielded >= limit:
                    return

                normalized = normalize(raw)
                if normalized is None:
                    continue

                normalized["source"] = "whiskycom"
                yield normalized
                yielded += 1

            page += 1

        log.info("Whisky.com: yielded %d whiskeys from %d pages", yielded, page - start_page)

    @property
    def current_page(self) -> int:
        """For progress tracking."""
        return getattr(self, "_last_page", 0)

    def _parse_listing_page(self, html: str) -> list[dict]:
        """Parse bottle cards from a listing page."""
        soup = BeautifulSoup(html, "lxml")
        bottles = []

        # Try multiple selectors for bottle cards
        cards = (
            soup.select("div.bottle-card")
            or soup.select("div.product-card")
            or soup.select("div.whisky-item")
            or soup.select("article.bottle")
            or soup.select("div.search-result-item")
            or soup.select("div.result-item")
            or soup.select("table.result-table tr")
        )

        if not cards:
            # Fallback: look for structured data in the page
            cards = self._find_bottle_elements(soup)

        for card in cards:
            raw = self._parse_bottle_card(card)
            if raw and raw.get("name"):
                bottles.append(raw)

        return bottles

    def _find_bottle_elements(self, soup: BeautifulSoup) -> list:
        """Fallback bottle element finder using generic patterns."""
        # Look for repeated structures with whiskey-like content
        candidates = []

        # Try div elements with links that look like bottle details
        for div in soup.find_all("div"):
            text = div.get_text(" ", strip=True)
            # A bottle entry typically has ABV (%) and might have age
            if "%" in text and len(text) > 10 and len(text) < 500:
                # Check it's not a navigation/header element
                if div.find("a") and not div.find("nav"):
                    candidates.append(div)

        return candidates

    def _parse_bottle_card(self, card) -> Optional[dict]:
        """Extract whiskey data from a single bottle card element."""
        text = card.get_text(" ", strip=True)
        if not text or len(text) < 5:
            return None

        # Extract name from heading or link
        name = None
        for tag in ["h2", "h3", "h4", "a", "span.name", "strong"]:
            el = card.select_one(tag) if "." in tag else card.find(tag)
            if el:
                candidate = el.get_text(strip=True)
                if candidate and len(candidate) > 3:
                    name = candidate
                    break

        if not name:
            # Try first significant text node
            name = text.split("\n")[0].strip()[:200]

        if not name or len(name) < 3:
            return None

        # Extract ABV BEFORE cleaning name (name may contain ABV)
        abv_str = None
        abv_match = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%\s*(?:vol|abv)?", text, re.I)
        if abv_match:
            abv_str = abv_match.group(1)

        # Extract age from raw name (before cleaning strips it)
        age_str = None
        age_match = re.search(r"(\d{1,2})\s*(?:year|yr|yo|y\.o|Y\b)", name)
        if age_match:
            age_str = age_match.group(1)

        # Clean the name (strip bottle size, ABV, German text)
        name = _clean_whiskycom_name(name)
        if not name or len(name) < 3:
            return None

        # Extract rating
        rating_str = None
        rating_el = card.select_one("span.rating, div.rating, span.score")
        if rating_el:
            rating_str = rating_el.get_text(strip=True)
        else:
            # Try pattern like "87/100" or "4.2/5"
            rating_match = re.search(r"(\d+\.?\d*)\s*/\s*(?:100|5)", text)
            if rating_match:
                rating_str = rating_match.group(1)

        # Extract volume/size to exclude from name
        size_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ml|cl|l)\b", text, re.I)

        # Extract distillery
        distillery = None
        dist_el = card.select_one("span.distillery, div.distillery, span.brand")
        if dist_el:
            distillery = dist_el.get_text(strip=True)

        # Extract description
        desc = None
        desc_el = card.select_one("p, span.description, div.description")
        if desc_el and desc_el != card:
            desc = desc_el.get_text(" ", strip=True)[:500]

        # Infer category from name
        category = _infer_category(name, text)
        country = _infer_country(name, text)

        return {
            "name": name,
            "distillery": distillery,
            "category": category,
            "country": country,
            "abv_str": abv_str or "40.0",
            "age_str": age_str,
            "rating_str": rating_str,
            "description": desc,
            "source": "whiskycom",
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _infer_category(name: str, text: str = "") -> str:
    """Infer whiskey category from name and page text."""
    combined = f"{name} {text}".lower()
    if "bourbon" in combined:
        return "bourbon"
    if "rye" in combined and "whiskey" in combined:
        return "rye"
    if "irish" in combined:
        return "irish"
    if "japanese" in combined or "japan" in combined:
        return "japanese"
    if "canadian" in combined:
        return "canadian"
    if "tennessee" in combined:
        return "bourbon"
    if "scotch" in combined or "scotland" in combined:
        return "scotch"
    if "single malt" in combined:
        return "single malt"
    if "blended" in combined:
        return "blended"
    return "scotch"  # default for whisky.com (German site, mostly scotch)


def _infer_country(name: str, text: str = "") -> str:
    """Infer country from name and text."""
    combined = f"{name} {text}".lower()
    if "bourbon" in combined or "tennessee" in combined:
        return "usa"
    if "irish" in combined or "ireland" in combined:
        return "ireland"
    if "japanese" in combined or "japan" in combined:
        return "japan"
    if "canadian" in combined or "canada" in combined:
        return "canada"
    return "scotland"
