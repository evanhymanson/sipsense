"""
TTB COLA Online Registry scraper.

Source: https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do
Data: Every spirit label approved for sale in the US since ~1999.

Strategy:
  1. Use Playwright browser to bypass JS bot challenge
  2. Fill and submit search form with product name keyword + date range
  3. Parse HTML result tables (20 results per page, max 1000 navigable)
  4. Click "Next >" for pagination

Conservative rate limiting (2-4s) to be respectful to a government site.
"""

import logging
import random
import re
import time
from typing import Generator

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from .normalizer import normalize

log = logging.getLogger(__name__)

SEARCH_URL = "https://www.ttbonline.gov/colasonline/publicSearchColasBasic.do"

# Product name search terms for whiskey
WHISKEY_SEARCH_TERMS = [
    "%BOURBON%",
    "%WHISKEY%",
    "%WHISKY%",
    "%SCOTCH%",
    "%RYE WHISK%",
    "%SINGLE MALT%",
    "%TENNESSEE WHISK%",
    "%MOONSHINE%",
    "%CORN WHISK%",
    "%WHEAT WHISK%",
    "%GRAIN WHISK%",
    "%CANADIAN WHISK%",
    "%IRISH WHISK%",
    "%MALT WHISK%",
    "%BLENDED WHISK%",
]

# Non-whiskey class types to exclude from results
NON_WHISKEY_CLASSES = [
    "ale", "lager", "stout", "beer", "malt beverages", "wine",
    "mead", "cider", "porter", "ipa", "pilsner", "saison",
]

# Whiskey class types to include
WHISKEY_CLASSES = [
    "whisky", "whiskey", "bourbon", "scotch", "rye", "malt whisk",
    "tennessee", "corn whisk", "wheat whisk", "grain whisk", "canadian",
    "blended", "single malt", "light whisk", "spirit whisk", "irish whisk",
]


class TTBOnlineScraper:
    """Scrapes the TTB COLA online registry via Playwright browser automation."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        self._min_delay = 2.0
        self._max_delay = 4.0

    def _wait(self):
        time.sleep(random.uniform(self._min_delay, self._max_delay))

    def iter_whiskeys(
        self,
        limit: int = 100_000,
        start_type_index: int = 0,
    ) -> Generator[dict, None, None]:
        """Search TTB for each whiskey keyword and yield results."""
        yielded = 0
        seen_ids: set[str] = set()
        seen_keys: set[str] = set()

        # Use multiple date ranges to get around the 1000-result limit
        date_ranges = [
            ("01/01/2024", "03/04/2026"),
            ("01/01/2022", "12/31/2023"),
            ("01/01/2020", "12/31/2021"),
            ("01/01/2017", "12/31/2019"),
            ("01/01/2013", "12/31/2016"),
            ("01/01/2009", "12/31/2012"),
            ("01/01/2005", "12/31/2008"),
            ("01/01/2000", "12/31/2004"),
        ]

        for term_idx, term in enumerate(WHISKEY_SEARCH_TERMS[start_type_index:],
                                         start=start_type_index):
            if yielded >= limit:
                return

            log.info("TTB Online: searching type %d/%d: %s",
                     term_idx + 1, len(WHISKEY_SEARCH_TERMS), term)

            for date_from, date_to in date_ranges:
                if yielded >= limit:
                    return

                try:
                    results = self._search(term, date_from, date_to)
                except Exception as exc:
                    log.warning("Search failed for %s (%s-%s): %s",
                                term, date_from, date_to, exc)
                    continue

                for raw in results:
                    if yielded >= limit:
                        return

                    # Dedup by TTB ID
                    ttb_id = raw.get("ttb_id", "")
                    if ttb_id and ttb_id in seen_ids:
                        continue
                    if ttb_id:
                        seen_ids.add(ttb_id)

                    # Filter by class/type (exclude beer, wine, etc.)
                    class_desc = (raw.get("category") or "").lower()
                    if any(nw in class_desc for nw in NON_WHISKEY_CLASSES):
                        continue
                    if not any(wk in class_desc for wk in WHISKEY_CLASSES):
                        name_lower = (raw.get("name") or "").lower()
                        if not any(wk in name_lower for wk in
                                   ["whisk", "bourbon", "scotch", "rye",
                                    "moonshine", "corn whisk"]):
                            continue

                    # Dedup by name (lowered)
                    name = (raw.get("name", "") or "").lower()
                    dedup_key = name
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)

                    normalized = normalize(raw)
                    if normalized is None:
                        continue

                    normalized["source"] = "ttb"
                    yield normalized
                    yielded += 1

        log.info(
            "TTB Online: total yielded=%d, unique IDs=%d, unique keys=%d",
            yielded, len(seen_ids), len(seen_keys),
        )

    def _search(self, product_name: str, date_from: str, date_to: str) -> list[dict]:
        """Execute a single search query and parse all result pages."""
        results = []

        # Navigate to search page
        try:
            self._page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
        except Exception as exc:
            log.warning("Failed to load search page: %s", exc)
            return results

        self._wait()

        # Fill and submit the search form
        try:
            self._page.fill("#datecompletedfrom", date_from)
            self._page.fill("#datecompletedto", date_to)
            self._page.fill("#productname", product_name)
            self._page.click('input[type=submit][value="Search"]')
            # Wait for JS bot challenge to resolve + page to load
            time.sleep(5)
            self._page.wait_for_load_state("domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as exc:
            log.warning("Search submit failed for %s: %s", product_name, exc)
            return results

        # Parse first result page
        html = self._page.content()
        page_results, total_records = self._parse_results_page(html)
        results.extend(page_results)

        log.info("  %s (%s-%s): page 1 got %d results (total matching: %s)",
                 product_name, date_from, date_to, len(page_results),
                 total_records or "?")

        # Follow pagination (max 50 pages = 1000 results)
        page_num = 1
        max_pages = 50
        while page_num < max_pages and len(results) < min(total_records or 0, 1000):
            # Click "Next >" link
            next_link = self._page.query_selector('a:has-text("Next >")')
            if not next_link:
                break

            page_num += 1

            try:
                next_link.click()
                # Wait for JS bot challenge to resolve after navigation
                time.sleep(5)
                self._page.wait_for_load_state("domcontentloaded", timeout=30000)
                time.sleep(2)
                html = self._page.content()
                page_results, _ = self._parse_results_page(html)
                if not page_results:
                    break
                results.extend(page_results)
                if self.verbose:
                    log.info("    Page %d: +%d results (total: %d)",
                             page_num, len(page_results), len(results))
            except Exception as exc:
                log.warning("Pagination failed at page %d: %s", page_num, exc)
                break

        log.info("  %s: %d results across %d pages", product_name, len(results), page_num)
        return results

    def _parse_results_page(self, html: str) -> tuple[list[dict], int]:
        """Parse TTB result table from HTML. Returns (results, total_records)."""
        soup = BeautifulSoup(html, "lxml")
        results = []
        total_records = 0

        # Extract total matching records
        text = soup.get_text()
        m = re.search(r"Total Matching Records:\s*([\d,]+)", text)
        if m:
            total_records = int(m.group(1).replace(",", ""))

        # Find the INNERMOST data table — the one with properly separated cells.
        # There are multiple nested layout tables that all match headers;
        # we want the LAST one (innermost) that has valid data rows.
        best_table = None
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if "Brand Name" not in headers or "TTB ID" not in headers:
                continue

            # Check that this table has proper individual cells
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 8:
                    first_cell = cells[0].get_text(strip=True)
                    # TTB IDs are 13-17 digit strings
                    if first_cell and len(first_cell) < 20 and first_cell[0].isdigit():
                        best_table = table  # Keep overwriting — last match wins
                        break

        if not best_table:
            return results, total_records

        # Build header index from the found table
        headers = [th.get_text(strip=True) for th in best_table.find_all("th")]
        h_idx = {h: i for i, h in enumerate(headers)}

        for row in best_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 6:
                continue

            def cell(name: str) -> str:
                idx = h_idx.get(name, -1)
                if 0 <= idx < len(cells):
                    return cells[idx].get_text(strip=True)
                return ""

            ttb_id = cell("TTB ID")

            # Skip garbage rows — real TTB IDs are 13-17 digits
            if not ttb_id or len(ttb_id) > 20 or not ttb_id[0].isdigit():
                continue

            brand = cell("Brand Name")
            fanciful = cell("Fanciful Name")
            origin_desc = cell("Origin Desc")
            class_desc = cell("Class/Type Desc")

            if not brand or len(brand) < 2:
                continue

            # Build name from brand + fanciful name
            if fanciful and fanciful.lower() != brand.lower():
                if brand.lower() in fanciful.lower():
                    name = fanciful
                else:
                    name = f"{brand} {fanciful}"
            else:
                name = brand

            # Extract age from name
            age_str = None
            age_match = re.search(
                r"(\d{1,2})\s*(?:year|yr|yo|y\.o)", name, re.I
            )
            if age_match:
                age_str = age_match.group(1)

            # Map origin codes to countries
            country = origin_desc or "USA"
            if country.isupper() and len(country) <= 3:
                country = "USA"

            results.append({
                "name": name,
                "distillery": "Unknown",
                "category": class_desc,
                "country": country,
                "abv_str": "40.0",
                "age_str": age_str,
                "ttb_id": ttb_id,
                "source": "ttb",
            })

        return results, total_records

    def close(self):
        try:
            self._page.close()
        except Exception:
            pass
        try:
            self._browser.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
