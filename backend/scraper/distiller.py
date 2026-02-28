"""
Distiller.com scraper.

Strategy:
  1. Fetch sitemap.xml once → extract all ~14k spirit slugs
  2. Filter to whiskey-relevant slugs using keyword matching
  3. Scrape each detail page for metadata:
       - og:title      → name
       - og:brand      → distillery
       - og:review     → rating (0–5)
       - og:description → description
       - <ul> <li>     → age, ABV
       - div.secondary-details → category / style

Distiller is respectful of crawlers (their sitemap is public) but we still
rate-limit to 1.5–2.5s per request.
"""

import logging
import re
from typing import Generator, Optional

from bs4 import BeautifulSoup

from .base import RateLimitedClient

log = logging.getLogger(__name__)

SITEMAP_URL = "https://distiller.com/sitemap.xml"
BASE_URL = "https://distiller.com"

# Slug keywords that indicate a whiskey (not rum/gin/vodka/etc.)
WHISKEY_KEYWORDS = [
    "whiskey", "whisky", "bourbon", "scotch", "rye", "irish",
    "japanese", "single-malt", "blended", "tennessee", "canadian",
    "year", "cask", "malt", "grain", "distill",
]

# These slugs are clearly non-whiskey — skip even if a keyword matches
NON_WHISKEY_KEYWORDS = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "armagnac", "calvados", "absinthe", "liqueur",
    "vermouth", "amaro", "schnapps", "sake",
]

# Category strings from Distiller that we accept as whiskey
WHISKEY_CATEGORIES = {
    "bourbon", "scotch", "rye", "irish whiskey", "irish", "japanese",
    "japanese whisky", "single malt", "blended", "canadian",
    "american whiskey", "tennessee whiskey", "wheat whiskey",
    "single grain", "blended malt", "world whisky", "whiskey", "whisky",
}


class DistillerScraper:
    """
    Scrapes whiskey metadata from distiller.com.

    Usage:
        with DistillerScraper() as scraper:
            for raw in scraper.iter_whiskeys(limit=5000):
                print(raw)
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._client = RateLimitedClient(min_delay=1.5, max_delay=2.5)
        self._slugs: list[str] = []

    # ── public API ────────────────────────────────────────────────────────

    def iter_whiskeys(
        self,
        limit: int = 10_000,
        start_index: int = 0,
    ) -> Generator[dict, None, None]:
        """
        Yields raw whiskey dicts from Distiller detail pages.
        Only yields entries whose page category is whiskey-type.
        """
        if not self._slugs:
            self._slugs = self._fetch_whiskey_slugs()

        slugs_to_scrape = self._slugs[start_index:]
        yielded = 0

        for slug in slugs_to_scrape:
            if yielded >= limit:
                return

            url = f"{BASE_URL}/spirits/{slug}"
            if self.verbose:
                log.info("Scraping: %s", url)

            try:
                resp = self._client.get(url)
            except Exception as exc:
                log.warning("Failed to fetch %s: %s", url, exc)
                continue

            raw = self._parse_detail(resp.text, slug)
            if raw is None:
                continue  # not a whiskey or parse failed

            yield raw
            yielded += 1

    def slug_count(self) -> int:
        """Return how many whiskey-filtered slugs are available."""
        if not self._slugs:
            self._slugs = self._fetch_whiskey_slugs()
        return len(self._slugs)

    # ── sitemap ───────────────────────────────────────────────────────────

    def _fetch_whiskey_slugs(self) -> list[str]:
        log.info("Fetching sitemap from %s…", SITEMAP_URL)
        try:
            resp = self._client.get(SITEMAP_URL)
        except Exception as exc:
            log.error("Failed to fetch sitemap: %s", exc)
            return []

        all_slugs = re.findall(
            r"distiller\.com/spirits/([a-z0-9\-]+)", resp.text
        )
        log.info("Sitemap: %d total spirit slugs", len(all_slugs))

        filtered = [
            s for s in all_slugs
            if _is_likely_whiskey_slug(s)
        ]
        log.info("After keyword filter: %d likely-whiskey slugs", len(filtered))
        return filtered

    # ── detail page parser ────────────────────────────────────────────────

    def _parse_detail(self, html: str, slug: str) -> Optional[dict]:
        soup = BeautifulSoup(html, "lxml")

        # ── meta tags (fast, reliable) ──
        metas = {
            (m.get("property") or m.get("name", "")): m.get("content", "")
            for m in soup.find_all("meta")
            if m.get("property") or m.get("name")
        }

        name = metas.get("og:title", "").strip()
        if not name:
            return None

        distillery = metas.get("og:brand", "").strip() or None
        description = metas.get("og:description", "").strip()[:1000] or None
        rating_str = metas.get("og:review", "").strip() or None  # already 0–5

        # ── category from secondary-details div ──
        category_raw = ""
        sec = soup.find("div", class_="secondary-details")
        if sec:
            category_raw = sec.get_text(" ", strip=True)

        # Validate it's actually a whiskey category
        cat_lower = category_raw.lower().strip()
        if cat_lower and not any(wc in cat_lower for wc in WHISKEY_CATEGORIES):
            # Page exists but isn't whiskey (rum, gin, etc. can pass slug filter)
            if self.verbose:
                log.debug("Skipping non-whiskey category: %r (%s)", category_raw, slug)
            return None

        # ── age + ABV from <ul><li> block ──
        age_str = None
        abv_str = None
        for ul in soup.find_all("ul"):
            text = ul.get_text(" ", strip=True).lower()
            if "abv" in text and ("age" in text or "year" in text):
                for li in ul.find_all("li"):
                    li_text = li.get_text(" ", strip=True)
                    if "age" in li_text.lower() or "year" in li_text.lower():
                        age_str = li_text
                    elif "abv" in li_text.lower():
                        abv_str = li_text
                break  # found the right ul

        # ── region from slug heuristic ──
        region = _region_from_slug(slug)

        return {
            "name":        name,
            "distillery":  distillery,
            "category":    category_raw,
            "country":     _country_from_category(category_raw),
            "region":      region,
            "age_str":     age_str,
            "abv_str":     abv_str,
            "rating_str":  rating_str,
            "price_str":   None,  # Distiller hides prices behind Pro
            "description": description,
            "flavor_profile": None,
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── module-level helpers ──────────────────────────────────────────────────

def _is_likely_whiskey_slug(slug: str) -> bool:
    if any(kw in slug for kw in NON_WHISKEY_KEYWORDS):
        return False
    return any(kw in slug for kw in WHISKEY_KEYWORDS)


def _country_from_category(cat: str) -> str:
    c = cat.lower()
    if "scotch" in c:       return "scotland"
    if "bourbon" in c or "tennessee" in c or "american" in c: return "usa"
    if "irish" in c:        return "ireland"
    if "japanese" in c:     return "japan"
    if "canadian" in c:     return "canada"
    return ""


def _region_from_slug(slug: str) -> Optional[str]:
    REGION_HINTS = {
        "islay": "Islay", "speyside": "Speyside", "highland": "Highlands",
        "lowland": "Lowlands", "campbeltown": "Campbeltown", "island": "Islands",
        "kentucky": "Kentucky", "tennessee": "Tennessee",
    }
    for hint, region in REGION_HINTS.items():
        if hint in slug:
            return region
    return None
