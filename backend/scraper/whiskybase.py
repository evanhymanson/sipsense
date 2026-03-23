"""
Whiskybase.com scraper using Playwright browser automation.

Whiskybase has ~220,000+ whisky bottles across ~2,800 distilleries — the
largest whisky database in the world. Protected by Cloudflare, so a real
browser is required.

Strategy:
  1. Fetch the full distillery listing (single page, ~2,800 rows).
  2. Visit each distillery page and parse its whiskytable.
     Each distillery page lists ALL its bottles in one table (no pagination).
  3. Yield normalized whiskey dicts for each row.

Table columns per distillery page:
  [0] image  [1] bottle thumbnail  [2] name (with detail link)
  [3] stated age  [4] strength (ABV)  [5] bottled year
  [6] cask number  [7] rating  [8] listings  [9] shop link

Setup:
  pip install playwright>=1.40.0
  playwright install chromium
"""

import logging
import random
import re
import time
from typing import Optional

from bs4 import BeautifulSoup

from .browser_base import BrowserClient

log = logging.getLogger(__name__)

BASE_URL = "https://www.whiskybase.com"
DISTILLERIES_URL = f"{BASE_URL}/whiskies/distilleries"

# Anti-rate-limit settings
REQUEST_DELAY_MIN = 4.0       # min seconds between requests
REQUEST_DELAY_MAX = 7.0       # max seconds between requests
PAUSE_EVERY_N = 25            # long pause every N distilleries
PAUSE_DURATION_MIN = 20.0     # min long pause (seconds)
PAUSE_DURATION_MAX = 45.0     # max long pause (seconds)
BROWSER_RESTART_EVERY = 100   # restart browser every N distilleries
SOFT_BLOCK_RETRY_DELAY = 30.0 # wait before retrying a soft-blocked page
SOFT_BLOCK_THRESHOLD = 10     # expected bottle count to trigger retry


class WhiskybaseScraper:
    """
    Scrapes whiskybase.com by enumerating all distilleries and their bottles.

    Usage:
        with WhiskybaseScraper() as scraper:
            for whiskey in scraper.iter_whiskeys(limit=500):
                print(whiskey)
    """

    def __init__(self, verbose: bool = False, headless: bool = False, proxy: str = None):
        self.verbose = verbose
        self.headless = headless
        self.proxy = proxy
        self._client = BrowserClient(
            min_delay=REQUEST_DELAY_MIN, max_delay=REQUEST_DELAY_MAX,
            headless=headless, proxy=proxy,
        )
        self._distilleries_since_restart = 0

    # ── public API ────────────────────────────────────────────────────────

    @property
    def last_distillery_index(self) -> int:
        """The distillery index we last processed (for progress tracking)."""
        return self._last_distillery_index

    def iter_whiskeys(self, limit: int = 300_000, start_offset: int = 0):
        """
        Generator that yields raw whiskey dicts from Whiskybase.

        Args:
            limit: Maximum number of whiskeys to yield.
            start_offset: Skip this many distilleries (for resuming).
        """
        self._last_distillery_index = start_offset

        # Phase 1: Get all distillery URLs
        distilleries = self._fetch_distilleries()
        if not distilleries:
            log.error("Failed to fetch distillery listing — aborting.")
            return

        log.info(
            "Found %d distilleries (starting at index %d, limit=%d)",
            len(distilleries), start_offset, limit,
        )

        scraped = 0
        consecutive_failures = 0
        distilleries_processed = 0

        for idx, dist in enumerate(distilleries):
            if idx < start_offset:
                continue
            if scraped >= limit:
                return

            self._last_distillery_index = idx

            dist_name = dist["name"]
            dist_url = dist["url"]
            dist_country = dist["country"]
            dist_count = dist["count"]

            # Periodic long pause to avoid rate limits
            distilleries_processed += 1
            if distilleries_processed > 1 and distilleries_processed % PAUSE_EVERY_N == 0:
                pause = random.uniform(PAUSE_DURATION_MIN, PAUSE_DURATION_MAX)
                log.info(
                    "Pausing %.0fs after %d distilleries to avoid rate limits...",
                    pause, distilleries_processed,
                )
                time.sleep(pause)

            # Restart browser periodically to get fresh fingerprint
            self._distilleries_since_restart += 1
            if self._distilleries_since_restart >= BROWSER_RESTART_EVERY:
                log.info("Restarting browser for fresh session...")
                self._restart_browser()

            if self.verbose:
                log.info(
                    "[%d/%d] Distillery: %s (%s, %d bottles) %s",
                    idx + 1, len(distilleries),
                    dist_name, dist_country, dist_count, dist_url,
                )

            whiskeys = self._fetch_with_retry(
                dist_url, dist_name, dist_country, dist_count,
            )

            if whiskeys is None:
                # Hard failure (exception raised)
                consecutive_failures += 1
                if consecutive_failures >= 10:
                    log.error("10 consecutive distillery failures — stopping.")
                    return
                continue

            consecutive_failures = 0

            for w in whiskeys:
                if scraped >= limit:
                    return
                yield w
                scraped += 1

        log.info("Finished enumerating all distilleries. Scraped %d whiskeys.", scraped)

    def _fetch_with_retry(self, url, name, country, expected_count, max_retries=2):
        """Fetch distillery with retry on soft blocks."""
        for attempt in range(max_retries + 1):
            try:
                whiskeys = self._fetch_distillery_whiskeys(url, name, country)
            except Exception as exc:
                log.warning("Failed to fetch distillery %s: %s", name, exc)
                if attempt < max_retries:
                    wait = SOFT_BLOCK_RETRY_DELAY * (attempt + 1)
                    log.info("Retrying %s in %.0fs (attempt %d/%d)...",
                             name, wait, attempt + 2, max_retries + 1)
                    time.sleep(wait)
                    self._restart_browser()
                    continue
                return None

            # Soft block detection: big distillery returned 0 bottles
            if not whiskeys and expected_count >= SOFT_BLOCK_THRESHOLD:
                if attempt < max_retries:
                    wait = SOFT_BLOCK_RETRY_DELAY * (attempt + 1)
                    log.warning(
                        "Soft block? %s expected %d bottles but got 0. "
                        "Retrying in %.0fs...",
                        name, expected_count, wait,
                    )
                    time.sleep(wait)
                    self._restart_browser()
                    continue
                else:
                    log.warning(
                        "Giving up on %s after %d attempts (expected %d bottles).",
                        name, max_retries + 1, expected_count,
                    )

            return whiskeys

        return []

    def _restart_browser(self):
        """Close and reopen the browser for a fresh session."""
        # Request new Tor circuit if using Tor proxy
        if self.proxy and ("9050" in self.proxy or "9150" in self.proxy):
            self._request_new_tor_circuit()
        self._client.close()
        self._client = BrowserClient(
            min_delay=REQUEST_DELAY_MIN, max_delay=REQUEST_DELAY_MAX,
            headless=self.headless, proxy=self.proxy,
        )
        self._distilleries_since_restart = 0

    @staticmethod
    def _request_new_tor_circuit():
        """Ask Tor for a new exit node (new IP address)."""
        import socket
        # Try standalone tor (9051) first, then Tor Browser (9151)
        for control_port in (9051, 9151):
            try:
                with socket.create_connection(("127.0.0.1", control_port), timeout=5) as s:
                    s.sendall(b'AUTHENTICATE ""\r\n')
                    resp = s.recv(256)
                    if b"250" in resp:
                        s.sendall(b"SIGNAL NEWNYM\r\n")
                        resp = s.recv(256)
                        if b"250" in resp:
                            log.info("Tor: new circuit requested via port %d (new IP).", control_port)
                            time.sleep(5)  # wait for new circuit
                            return
                        else:
                            log.warning("Tor: NEWNYM failed on port %d: %s", control_port, resp)
                    else:
                        log.warning("Tor: auth failed on port %d: %s", control_port, resp)
            except Exception:
                continue
        log.debug("Tor control port unavailable on 9051 and 9151.")

    @property
    def distillery_count(self) -> int:
        """Fetch and return the number of distilleries (for progress bars)."""
        return 2800  # approximate — avoids an extra request

    # ── Phase 1: distillery listing ──────────────────────────────────────

    def _fetch_distilleries(self) -> list[dict]:
        """Fetch all distillery names, URLs, countries, and bottle counts."""
        log.info("Fetching distillery listing from %s", DISTILLERIES_URL)

        try:
            html = self._client.get(DISTILLERIES_URL)
        except Exception as exc:
            log.error("Failed to load distilleries page: %s", exc)
            return []

        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table.whiskytable")
        if not table:
            log.error("No whiskytable found on distilleries page.")
            return []

        distilleries = []
        for row in table.find_all("tr")[1:]:  # skip header
            cells = row.find_all("td")
            if len(cells) < 3:
                continue

            link = row.find("a", href=True)
            if not link:
                continue

            name = link.get_text(strip=True)
            href = link["href"]
            full_url = href if href.startswith("http") else BASE_URL + href

            # The listing URL is like /whiskies/distillery/48/aberlour
            # The bottle listing is at /whiskies/distillery/48/whiskies
            # (replacing the slug with "whiskies")
            # Extract the distillery ID and build the whiskies URL
            id_match = re.search(r"/distillery/(\d+)", full_url)
            if id_match:
                dist_id = id_match.group(1)
                url = f"{BASE_URL}/whiskies/distillery/{dist_id}/whiskies"
            else:
                url = full_url + "/whiskies"

            country = cells[1].get_text(strip=True) if len(cells) > 1 else ""

            count_text = cells[2].get_text(strip=True) if len(cells) > 2 else "0"
            try:
                count = int(count_text.replace(",", ""))
            except ValueError:
                count = 0

            distilleries.append({
                "name": name,
                "url": url,
                "country": country,
                "count": count,
            })

        log.info(
            "Parsed %d distilleries (total bottles: %d)",
            len(distilleries),
            sum(d["count"] for d in distilleries),
        )
        return distilleries

    # ── Phase 2: distillery detail page ──────────────────────────────────

    def _fetch_distillery_whiskeys(
        self,
        distillery_url: str,
        distillery_name: str,
        country: str,
    ) -> list[dict]:
        """Fetch all whiskeys from a single distillery page."""
        html = self._client.get(distillery_url)

        if self._is_blocked(html):
            log.warning("Cloudflare block detected on %s", distillery_url)
            raise RuntimeError("Cloudflare blocked")

        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table.whiskytable")

        if not table:
            return []

        results = []
        for row in table.find_all("tr")[1:]:  # skip header
            # Skip category separator rows (e.g., "Core Range", "Limited Edition")
            if "seperator" in (row.get("class") or []):
                continue
            if any(c.get("colspan") for c in row.find_all("td")):
                continue

            item = self._parse_whiskey_row(row, distillery_name, country)
            if item:
                results.append(item)

        return results

    def _parse_whiskey_row(
        self,
        row,
        distillery_name: str,
        country: str,
    ) -> Optional[dict]:
        """Parse a single <tr> from a distillery's whiskytable."""
        try:
            cells = row.find_all("td")
            if len(cells) < 5:
                return None

            # Find the whiskey name + detail link
            name_link = row.find("a", href=re.compile(r"/whiskies/whisky/\d+"))
            if not name_link:
                return None

            raw_name = name_link.get_text(strip=True)
            if not raw_name or len(raw_name) < 3:
                return None

            # Clean CamelCase gluing from Whiskybase rendering
            name = self._clean_name(raw_name)

            href = name_link["href"]
            detail_url = href if href.startswith("http") else BASE_URL + href

            # Parse cells by position
            # Columns: [0] rank/img [1] bottle img [2] name [3] age [4] ABV
            #          [5] bottled [6] cask# [7] rating [8] listings [9] shop
            age_str = self._get_cell_text(cells, 3)
            abv_str = self._get_cell_text(cells, 4)
            bottled_str = self._get_cell_text(cells, 5)
            cask_str = self._get_cell_text(cells, 6)
            rating_str = self._get_cell_text(cells, 7)

            abv = self._parse_abv(abv_str)
            age = self._parse_age(age_str)
            rating = self._parse_rating(rating_str)
            category = self._infer_category(name, country)
            region = self._country_to_region(country)

            return {
                "name": name,
                "distillery": distillery_name,
                "category": category,
                "region": region,
                "country": country,
                "abv": abv,
                "age": age,
                "rating": rating,
                "source": "whiskybase",
            }
        except Exception as exc:
            log.debug("Row parse error: %s", exc)
            return None

    @staticmethod
    def _clean_name(name: str) -> str:
        """Clean CamelCase gluing and common issues from Whiskybase names."""
        # Split CamelCase: "10-year-oldForest Reserve" → "10-year-old Forest Reserve"
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        # Split digit-letter: "1967RWD" → "1967 RWD"
        name = re.sub(r"(\d)([A-Z][a-z])", r"\1 \2", name)
        # Collapse whitespace
        name = re.sub(r"\s+", " ", name).strip()
        return name

    # ── parsers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_abv(text: Optional[str]) -> Optional[float]:
        """Parse ABV from strings like '57.0 % Vol.', '43%', '46.0'."""
        if not text:
            return None
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m:
            val = float(m.group(1))
            if 20.0 <= val <= 95.0:
                return val
        return None

    @staticmethod
    def _parse_age(text: Optional[str]) -> Optional[int]:
        """Parse age from strings like '15', '12 years', 'NAS'."""
        if not text:
            return None
        text = text.strip()
        if text.upper() in ("NAS", "N/A", "-", ""):
            return None
        m = re.search(r"(\d+)", text)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 80:
                return val
        return None

    @staticmethod
    def _parse_rating(text: Optional[str]) -> Optional[float]:
        """Parse Whiskybase rating (0-100 scale) → 0-5 scale."""
        if not text:
            return None
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if m:
            val = float(m.group(1))
            if 0 < val <= 100:
                return round(val / 20.0, 2)  # 100 → 5.0, 80 → 4.0
        return None

    @staticmethod
    def _infer_category(name: str, country: str) -> str:
        """Infer whiskey category from name and country of origin."""
        name_lower = name.lower()

        if "bourbon" in name_lower:
            return "bourbon"
        if "rye" in name_lower and "whisky" not in name_lower:
            return "rye"
        if "single grain" in name_lower:
            return "single grain"
        if "single malt" in name_lower:
            return "single malt"
        if "blend" in name_lower:
            return "blended"
        if "single pot" in name_lower:
            return "single pot still"
        if "corn whisk" in name_lower:
            return "corn"

        # Infer from country
        country_lower = (country or "").lower()
        if country_lower in ("scotland", "scotland (uk)"):
            return "single malt"  # most scotch on whiskybase is single malt
        if country_lower in ("ireland",):
            return "irish"
        if country_lower in ("united states", "usa", "us"):
            return "bourbon"
        if country_lower in ("japan",):
            return "japanese"
        if country_lower in ("canada",):
            return "canadian"
        if country_lower in ("india",):
            return "indian"
        if country_lower in ("taiwan",):
            return "world"

        return "world"

    @staticmethod
    def _country_to_region(country: str) -> str:
        """Map country to a region string."""
        c = (country or "").lower().strip()
        region_map = {
            "scotland": "Scotland",
            "scotland (uk)": "Scotland",
            "ireland": "Ireland",
            "united states": "United States",
            "usa": "United States",
            "japan": "Japan",
            "canada": "Canada",
            "india": "India",
            "taiwan": "Taiwan",
            "australia": "Australia",
            "england": "England",
            "wales": "Wales",
            "france": "France",
            "germany": "Germany",
            "sweden": "Sweden",
            "finland": "Finland",
            "netherlands": "Netherlands",
            "denmark": "Denmark",
            "switzerland": "Switzerland",
            "belgium": "Belgium",
            "austria": "Austria",
            "italy": "Italy",
            "spain": "Spain",
            "south africa": "South Africa",
            "new zealand": "New Zealand",
            "norway": "Norway",
            "czech republic": "Czech Republic",
        }
        return region_map.get(c, country or "Other")

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_cell_text(cells: list, idx: int) -> Optional[str]:
        """Safely get text from a cell by index."""
        if idx < len(cells):
            text = cells[idx].get_text(strip=True)
            return text if text else None
        return None

    @staticmethod
    def _is_blocked(html: str) -> bool:
        """Check if the page is a Cloudflare block page."""
        lower = html.lower()
        block_signals = [
            "access denied",
            "error 1015",
            "error 1020",
            "you have been blocked",
        ]
        hits = sum(1 for s in block_signals if s in lower)
        return hits >= 2

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
