"""
TTB COLA Registry scraper.

The TTB (Alcohol and Tobacco Tax and Trade Bureau) publishes all approved
spirit label certificates as bulk data via their FOIA reading room.
Every whiskey legally sold in the US has a COLA entry — ~100k records.

ABV is NOT in COLA data. We default to 40.0% (legal minimum for spirits).

Usage:
    # Auto-discover and download from TTB FOIA reading room:
    python -m scraper.run --source ttb

    # Use a pre-downloaded ZIP or CSV:
    python -m scraper.run --source ttb --ttb-file /path/to/spirits.zip

How to manually get the file:
    1. Go to https://www.ttb.gov/foia/foia-reading-room.shtml
    2. Download the "Distilled Spirits" COLA ZIP file
    3. Pass the path via --ttb-file
"""

import csv
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

FOIA_URL = "https://www.ttb.gov/foia/foia-reading-room.shtml"
USER_AGENT = "SipSense/1.0 (whiskey database; educational project)"

# Keywords in CLASS/TYPE DESCRIPTION that indicate whiskey
WHISKEY_TYPE_KEYWORDS = [
    "whisky", "whiskey", "bourbon", "scotch", "rye", "malt",
    "tennessee", "irish", "blended", "single malt", "grain whisky",
    "american whiskey", "blended whiskey",
]

# Column name variants in TTB CSV exports (TTB has changed format over the years)
_BRAND_COLS     = ["BRAND NAME", "BRAND_NAME", "BRAND", "BRANDNAME"]
_TYPE_DESC_COLS = ["CLASS/TYPE DESCRIPTION", "CLASS_TYPE_DESCRIPTION",
                   "CLASS_TYPE_DSC", "TYPE DESCRIPTION", "TYPEDESCRIPTION"]
_COMPANY_COLS   = ["COMPANY NAME", "COMPANY_NAME", "COMPANY", "COMPANYNAME"]
_COUNTRY_COLS   = ["ORIGIN COUNTRY", "ORIGIN_COUNTRY", "COUNTRY OF ORIGIN",
                   "COUNTRY", "COUNTRYOFORIGIN"]
_FANCIFUL_COLS  = ["FANCIFUL NAME", "FANCIFUL_NAME", "FANCIFULNAME"]


class TTBScraper:
    """
    Downloads and parses TTB COLA registry data.

    Yields raw whiskey dicts for every whiskey-type approved label.
    Since COLA data lacks ABV, all entries default to 40.0%.
    """

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self._client = httpx.Client(
            timeout=120.0,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def fetch_whiskeys(self) -> list[dict]:
        if self.file_path:
            log.info("Reading TTB data from local file: %s", self.file_path)
            rows = self._parse_file(Path(self.file_path))
        else:
            log.info("Auto-discovering TTB data from FOIA reading room…")
            rows = self._download_and_parse()

        log.info("TTB: parsed %d whiskey entries", len(rows))
        return rows

    # ── download ──────────────────────────────────────────────────────────

    def _download_and_parse(self) -> list[dict]:
        url = self._find_download_url()
        if not url:
            raise RuntimeError(
                "Could not auto-discover TTB data download URL.\n"
                "Manually download the Distilled Spirits COLA file from:\n"
                f"  {FOIA_URL}\n"
                "Then re-run with: python -m scraper.run --source ttb --ttb-file path/to/file.zip"
            )

        log.info("Downloading TTB data from: %s", url)
        resp = self._client.get(url)
        resp.raise_for_status()

        data = resp.content
        log.info("Downloaded %.1f MB", len(data) / 1_048_576)
        return self._parse_bytes(data, url)

    def _find_download_url(self) -> Optional[str]:
        try:
            resp = self._client.get(FOIA_URL)
            resp.raise_for_status()
        except Exception as exc:
            log.warning("Could not fetch FOIA page: %s", exc)
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        for a in soup.find_all("a", href=True):
            href = a["href"]
            href_lower = href.lower()
            text_lower = a.get_text().lower()

            is_data_file = any(
                href_lower.endswith(ext) for ext in [".zip", ".xlsx", ".csv", ".xls"]
            )
            is_spirit = any(
                kw in href_lower or kw in text_lower
                for kw in ["spirit", "cola", "distill"]
            )

            if is_data_file and is_spirit:
                if href.startswith("/"):
                    href = "https://www.ttb.gov" + href
                elif not href.startswith("http"):
                    href = "https://www.ttb.gov/" + href.lstrip("/")
                log.info("Found TTB data link: %s", href)
                return href

        log.warning("No suitable TTB download link found on FOIA page.")
        return None

    # ── parsing ───────────────────────────────────────────────────────────

    def _parse_file(self, path: Path) -> list[dict]:
        data = path.read_bytes()
        return self._parse_bytes(data, str(path))

    def _parse_bytes(self, data: bytes, source_hint: str) -> list[dict]:
        hint = source_hint.lower()
        if hint.endswith(".zip") or data[:4] == b"PK\x03\x04":
            return self._parse_zip(data)
        elif hint.endswith((".xlsx", ".xls")):
            return self._parse_excel(data)
        else:
            return self._parse_csv(data.decode("utf-8", errors="replace"))

    def _parse_zip(self, data: bytes) -> list[dict]:
        results = []
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                log.info("ZIP entry: %s", name)
                file_data = zf.read(name)
                if name.lower().endswith(".csv"):
                    results.extend(
                        self._parse_csv(file_data.decode("utf-8", errors="replace"))
                    )
                elif name.lower().endswith((".xlsx", ".xls")):
                    results.extend(self._parse_excel(file_data))
        return results

    def _parse_csv(self, text: str) -> list[dict]:
        reader = csv.DictReader(io.StringIO(text))
        results = []
        for row in reader:
            normalized_row = {k.strip().upper(): (v or "").strip() for k, v in row.items()}
            parsed = self._parse_row(normalized_row)
            if parsed:
                results.append(parsed)
        return results

    def _parse_excel(self, data: bytes) -> list[dict]:
        try:
            import openpyxl
        except ImportError:
            log.error("openpyxl is required for Excel files: pip install openpyxl")
            return []

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []

            headers = [str(h).strip().upper() if h else "" for h in rows[0]]
            results = []
            for row_data in rows[1:]:
                row = {
                    headers[i]: (str(v).strip() if v is not None else "")
                    for i, v in enumerate(row_data)
                    if i < len(headers)
                }
                parsed = self._parse_row(row)
                if parsed:
                    results.append(parsed)

            wb.close()
            return results
        except Exception as exc:
            log.error("Failed to parse Excel: %s", exc)
            return []

    def _parse_row(self, row: dict) -> Optional[dict]:
        type_desc = _get_col(row, _TYPE_DESC_COLS)
        if not self._is_whiskey(type_desc):
            return None

        brand = _get_col(row, _BRAND_COLS)
        if not brand:
            return None

        fanciful = _get_col(row, _FANCIFUL_COLS)
        # Use fanciful name as the product name if it's distinct from brand
        name = fanciful if fanciful and fanciful.lower() != brand.lower() else brand

        company = _get_col(row, _COMPANY_COLS)
        country = _get_col(row, _COUNTRY_COLS)

        return {
            "name":         name,
            "distillery":   company or brand,
            "category":     _ttb_type_to_category(type_desc),
            "country":      _normalize_country(country),
            "region":       None,
            "age_str":      None,
            "abv_str":      "40.0",   # COLA data has no ABV — use legal minimum
            "rating_str":   None,
            "price_str":    None,
            "description":  None,
            "flavor_profile": None,
            "upc":          None,
            "source":       "ttb",
        }

    def _is_whiskey(self, type_desc: str) -> bool:
        if not type_desc:
            return False
        lower = type_desc.lower()
        return any(kw in lower for kw in WHISKEY_TYPE_KEYWORDS)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── helpers ───────────────────────────────────────────────────────────────

def _get_col(row: dict, candidates: list[str]) -> str:
    """Try multiple column name variants, return first non-empty match."""
    for col in candidates:
        val = row.get(col, "").strip()
        if val and val not in ("-", "N/A", "n/a"):
            return val
    return ""


def _ttb_type_to_category(type_desc: str) -> str:
    t = type_desc.lower()
    if "bourbon" in t:      return "bourbon"
    if "tennessee" in t:    return "bourbon"
    if "rye" in t:          return "rye"
    if "scotch" in t:       return "scotch"
    if "irish" in t:        return "irish"
    if "single malt" in t:  return "single malt"
    if "blended malt" in t: return "scotch"
    if "blended" in t:      return "blended"
    if "grain" in t:        return "scotch"
    if "canadian" in t:     return "canadian"
    if "japanese" in t:     return "japanese"
    return "whiskey"


def _normalize_country(country: str) -> str:
    c = country.lower().strip()
    mapping = {
        "us": "usa", "usa": "usa", "united states": "usa",
        "united states of america": "usa", "u.s.": "usa",
        "gb": "scotland", "uk": "scotland", "united kingdom": "scotland",
        "scotland": "scotland",
        "ie": "ireland", "ireland": "ireland",
        "jp": "japan", "japan": "japan",
        "ca": "canada", "canada": "canada",
    }
    return mapping.get(c, c)
