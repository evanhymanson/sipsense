"""
Rate-limited HTTP client for polite web scraping.

Handles:
  - Randomized delays between requests
  - Exponential backoff on 429/503
  - Realistic browser headers
  - Per-domain robots.txt check (best-effort)
"""

import time
import random
import logging
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

# Realistic browser User-Agent strings — rotate to avoid trivial blocks
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

RETRY_STATUSES = {429, 503, 502, 504}
MAX_RETRIES = 3


class RateLimitedClient:
    """
    Thin wrapper around httpx that enforces polite crawling.

    Args:
        min_delay: minimum seconds between requests (default 1.5)
        max_delay: maximum seconds between requests (default 3.0)
        timeout:   per-request timeout in seconds
    """

    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 3.0,
        timeout: float = 15.0,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_request: float = 0.0
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
        )
        self._robots_cache: dict[str, RobotFileParser] = {}

    # ── public API ────────────────────────────────────────────────────────

    def get(self, url: str, **kwargs) -> httpx.Response:
        """Fetch a URL, respecting rate limits and retrying on transient errors."""
        self._wait()
        headers = {**self._base_headers(), **kwargs.pop("headers", {})}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._client.get(url, headers=headers, **kwargs)
                self._last_request = time.monotonic()

                if resp.status_code in RETRY_STATUSES:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    log.warning(
                        "Got %s for %s — backing off %.1fs (attempt %d/%d)",
                        resp.status_code, url, wait, attempt, MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp

            except httpx.HTTPStatusError:
                raise
            except httpx.RequestError as exc:
                if attempt == MAX_RETRIES:
                    raise
                wait = 2 ** attempt
                log.warning("Request error on %s: %s — retrying in %ss", url, exc, wait)
                time.sleep(wait)

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    def is_allowed(self, url: str) -> bool:
        """Best-effort robots.txt check. Returns True if scraping is allowed."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if base not in self._robots_cache:
            rp = RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                # If we can't fetch robots.txt, assume allowed
                return True
            self._robots_cache[base] = rp

        return self._robots_cache[base].can_fetch("*", url)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── internals ─────────────────────────────────────────────────────────

    def _wait(self):
        elapsed = time.monotonic() - self._last_request
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)

    @staticmethod
    def _base_headers() -> dict:
        # Note: do NOT include Accept-Encoding — httpx handles decompression
        # automatically and overriding the header breaks it.
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
