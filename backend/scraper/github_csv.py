"""
Imports whiskeys from the open-source GitHub ML Whiskey Dataset.
Source: https://github.com/makispl/Machine-Learning-Whiskey-Dataset

2,636 whiskeys (mostly scotch) with: name, category, rating (0-100),
price (USD), description. Age and ABV are embedded in the name string.

This is a fast, zero-rate-limit source — runs in seconds, no scraping.
"""

import csv
import io
import logging
import re

import httpx

from .normalizer import normalize

log = logging.getLogger(__name__)

CSV_URL = (
    "https://raw.githubusercontent.com/makispl/Machine-Learning-Whiskey-Dataset"
    "/main/whiskey_data.csv"
)

# Known distilleries — used to extract distillery from whiskey names
KNOWN_DISTILLERIES = [
    "Glenfiddich", "Macallan", "Laphroaig", "Ardbeg", "Lagavulin",
    "Bowmore", "Balvenie", "Glenlivet", "Highland Park", "Dalmore",
    "Glenfarclas", "GlenDronach", "Springbank", "Bruichladdich",
    "Bunnahabhain", "Caol Ila", "Talisker", "Oban", "Glenmorangie",
    "Dalwhinnie", "Aberfeldy", "Craigellachie", "Mortlach", "Glen Grant",
    "Tomatin", "Auchentoshan", "Deanston", "Tobermory", "Jura",
    "Benriach", "GlenAllachie", "Linkwood", "Strathisla", "Benrinnes",
    "Blair Athol", "Glen Elgin", "Inchgower", "Longmorn", "Mannochmore",
    "Cardhu", "Cragganmore", "Glenlossie", "Tamdhu", "Tamnavulin",
    "Nikka", "Suntory", "Yamazaki", "Hakushu", "Hibiki", "Yoichi",
    "Miyagikyo", "Chichibu", "Buffalo Trace", "Heaven Hill", "Four Roses",
    "Wild Turkey", "Woodford Reserve", "Maker's Mark", "Jim Beam",
    "Knob Creek", "Bulleit", "Elijah Craig", "Evan Williams",
    "WhistlePig", "High West", "Stranahan's", "Westland",
    "Jameson", "Redbreast", "Green Spot", "Teeling", "Midleton",
    "Tullamore", "Bushmills", "Connemara",
]


def fetch_github_whiskeys() -> list[dict]:
    """
    Download the GitHub CSV and return a list of normalized whiskey dicts.
    Ready to write directly to the DB.
    """
    log.info("Fetching GitHub whiskey CSV (%s)…", CSV_URL)
    resp = httpx.get(CSV_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    reader = csv.DictReader(io.StringIO(resp.text))
    raw_rows = list(reader)
    log.info("CSV downloaded: %d rows", len(raw_rows))

    results = []
    for row in raw_rows:
        raw = _csv_row_to_raw(row)
        if raw is None:
            continue
        normalized = normalize(raw)
        if normalized:
            results.append(normalized)

    log.info("Successfully normalized %d / %d rows", len(results), len(raw_rows))
    return results


def _csv_row_to_raw(row: dict) -> dict | None:
    """Convert a CSV row to the raw dict format the normalizer expects."""
    name = (row.get("name") or "").strip()
    if not name:
        return None

    # Parse ABV and age from the name string
    # e.g. "Black Bowmore 42 year old 1964 vintage, 40.5%"
    abv_str = None
    age_str = None

    abv_match = re.search(r"(\d+\.?\d*)\s*%", name)
    if abv_match:
        abv_str = abv_match.group(1)
        # Clean ABV from name for cleaner display
        name = re.sub(r",?\s*\d+\.?\d*\s*%", "", name).strip()

    age_match = re.search(r"(\d+)\s*[Yy]ear", name)
    if age_match:
        age_str = age_match.group(1)

    # Extract distillery from the name
    distillery = _extract_distillery(name)

    # Build category from the CSV "category" field
    category_raw = (row.get("category") or "").strip()

    # Price — CSV has separate price + currency columns
    price_str = None
    price = row.get("price", "").strip()
    currency = row.get("currency", "").strip()
    if price and currency == "$":
        price_str = price

    # Rating is on 0-100 scale — normalizer handles conversion
    rating_str = row.get("rating", "").strip()

    return {
        "name": name,
        "distillery": distillery,
        "category": category_raw,
        "country": _country_from_category(category_raw),
        "region": None,
        "age_str": age_str,
        "abv_str": abv_str or "40",  # default 40% if not parseable
        "rating_str": rating_str,
        "price_str": price_str,
        "description": (row.get("description") or "").strip()[:1000] or None,
    }


def _extract_distillery(name: str) -> str:
    """Try to extract the distillery name from the whiskey name."""
    name_lower = name.lower()
    for distillery in KNOWN_DISTILLERIES:
        if distillery.lower() in name_lower:
            return distillery
    # Fall back to first 1-2 words of the name
    words = name.split()
    if len(words) >= 2:
        return " ".join(words[:2])
    return words[0] if words else "Unknown"


def _country_from_category(category: str) -> str:
    cat = category.lower()
    if "scotch" in cat or "scotland" in cat:
        return "scotland"
    if "bourbon" in cat or "american" in cat:
        return "usa"
    if "irish" in cat:
        return "ireland"
    if "japanese" in cat or "japan" in cat:
        return "japan"
    if "canadian" in cat:
        return "canada"
    return "scotland"  # most entries in this CSV are scotch
