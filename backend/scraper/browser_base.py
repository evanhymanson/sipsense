"""
Browser automation base for scraping Cloudflare/Vercel-protected sites.

Uses Playwright for headless Chromium to bypass bot protection.
Required for: Whiskybase, Master of Malt, The Whisky Exchange.

Setup:
  pip install playwright>=1.40.0
  playwright install chromium
"""

import logging
import random
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    log.debug("playwright not installed — browser automation unavailable")

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    log.debug("playwright-stealth not installed — stealth mode unavailable")


class BrowserClient:
    """
    Headless browser client for scraping JS-rendered and bot-protected sites.

    Provides a rate-limited, session-persistent browser interface that can
    bypass Cloudflare and Vercel bot protection.

    Usage:
        with BrowserClient() as client:
            html = client.get("https://www.whiskybase.com/whiskies")
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 4.0,
        headless: bool = True,
        proxy: Optional[str] = None,
    ):
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(
                "playwright is not installed. Install with:\n"
                "  pip install playwright>=1.40.0\n"
                "  playwright install chromium"
            )

        self.min_delay = min_delay
        self.max_delay = max_delay
        self.headless = headless
        self.proxy = proxy
        self._last_request = 0.0
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._request_count = 0

    def _ensure_browser(self):
        """Lazily initialize the browser."""
        if self._page is not None:
            return

        self._playwright = sync_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]

        # Proxy support (e.g., Tor SOCKS5)
        launch_kwargs = {
            "headless": self.headless,
            "args": launch_args,
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}
            log.info("Using proxy: %s", self.proxy)

        self._browser = self._playwright.chromium.launch(**launch_kwargs)

        # Create a context with realistic browser fingerprint
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )

        self._page = context.new_page()

        # Apply playwright-stealth (hides automation signals from Cloudflare)
        if HAS_STEALTH:
            stealth_sync(self._page)
            log.info("Stealth mode applied to browser page.")
        else:
            # Fallback: manual webdriver masking
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

    def get(self, url: str, wait_for: str = "domcontentloaded", retries: int = 3) -> str:
        """
        Navigate to URL and return the page HTML.

        Uses 'domcontentloaded' by default (not 'networkidle') because
        Cloudflare challenge pages keep making background requests that
        prevent networkidle from ever triggering.

        Args:
            url: URL to fetch
            wait_for: Playwright wait condition ('networkidle', 'load', 'domcontentloaded')
            retries: Number of retry attempts on failure

        Returns:
            The page HTML content
        """
        self._ensure_browser()
        self._wait()

        last_exc = None
        for attempt in range(retries):
            try:
                self._page.goto(url, wait_until=wait_for, timeout=30000)
                self._last_request = time.monotonic()
                self._request_count += 1

                # Wait for Cloudflare challenge to resolve (if present)
                self._handle_cloudflare()

                # Give the page a moment to render JS content
                time.sleep(1.5)

                return self._page.content()

            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    backoff = (2 ** attempt) + random.uniform(1, 3)
                    log.warning(
                        "Browser fetch failed for %s (attempt %d/%d): %s — retrying in %.1fs",
                        url, attempt + 1, retries, exc, backoff,
                    )
                    time.sleep(backoff)
                else:
                    log.error("Browser fetch failed for %s after %d attempts: %s", url, retries, exc)

        raise last_exc

    def scroll_to_bottom(self, pause: float = 1.0):
        """Scroll page to bottom to trigger lazy-loaded content."""
        self._ensure_browser()
        self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)

    def get_page(self) -> "Page":
        """Get the underlying Playwright Page for advanced interactions."""
        self._ensure_browser()
        return self._page

    @property
    def request_count(self) -> int:
        return self._request_count

    def _handle_cloudflare(self):
        """Wait for Cloudflare challenge to resolve if present."""
        page_text = self._page.text_content("body") or ""
        text_lower = page_text.lower()

        cf_triggers = [
            "checking your browser",
            "just a moment",
            "enable javascript and cookies",
            "attention required",
            "verify you are human",
        ]

        cf_triggers.extend([
            "security verification",
            "performing security",
            "please wait",
        ])

        if any(t in text_lower for t in cf_triggers):
            log.info("Cloudflare challenge detected — click through in the browser window! Waiting up to 60s...")
            for _ in range(120):  # up to 60s
                time.sleep(0.5)
                page_text = self._page.text_content("body") or ""
                text_lower = page_text.lower()
                if not any(t in text_lower for t in cf_triggers):
                    log.info("Cloudflare challenge passed.")
                    return
            log.warning("Cloudflare challenge did not resolve within 60s.")

    def _wait(self):
        """Rate limiting between requests."""
        elapsed = time.monotonic() - self._last_request
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)

    def close(self):
        """Clean up browser resources."""
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._browser = None
        self._playwright = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
