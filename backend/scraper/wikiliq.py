"""
Wikiliq dataset importer.

Kaggle dataset: limtis/wikiliq-dataset (6.5 MB zip, 3 CSV files)
The "liquors" CSV contains thousands of spirits entries including whiskey.

Download:
  kaggle datasets download -d limtis/wikiliq-dataset -p scraper/data/wikiliq --unzip

Expected columns: Name, Brand, Country, Categories, ABV, Rating, Rate count,
                  Price, Volume, Description
"""

import csv
import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Whiskey-related keywords in the Categories column
WHISKEY_KEYWORDS = [
    "whisky", "whiskey", "bourbon", "scotch", "rye",
    "single malt", "irish", "tennessee", "japanese whisky",
    "corn whiskey", "malt", "blended",
]

# Non-whiskey keywords to exclude
EXCLUDE_KEYWORDS = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "sake", "liqueur", "absinthe", "schnapps",
    "vermouth", "bitters", "grappa", "aguardiente",
]


def _is_whiskey(categories: str, name: str) -> bool:
    """Check if a product is a whiskey based on categories and name."""
    text = f"{categories} {name}".lower()
    # Must have at least one whiskey keyword
    if not any(kw in text for kw in WHISKEY_KEYWORDS):
        return False
    # Exclude non-whiskey spirits that might mention whiskey tangentially
    cat_lower = categories.lower()
    if any(kw in cat_lower for kw in EXCLUDE_KEYWORDS):
        # Only exclude if whiskey isn't the PRIMARY category
        if not any(kw in cat_lower.split(",")[0].lower() for kw in WHISKEY_KEYWORDS):
            return False
    return True


def _infer_category(categories: str, name: str) -> str:
    """Infer whiskey category from Wikiliq categories and name."""
    text = f"{categories} {name}".lower()
    if "bourbon" in text:
        return "bourbon"
    if "scotch" in text or "single malt" in text:
        return "single malt" if "single malt" in text else "scotch"
    if "irish" in text:
        return "irish"
    if "japanese" in text:
        return "japanese"
    if "rye" in text:
        return "rye"
    if "canadian" in text:
        return "canadian"
    if "tennessee" in text:
        return "tennessee"
    if "corn" in text:
        return "corn"
    if "blended" in text:
        return "blended"
    return "whiskey"


def _parse_abv(abv_str: Optional[str]) -> Optional[float]:
    """Parse ABV from string like '40%', '43.0', etc."""
    if not abv_str:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", abv_str.replace(",", "."))
    if m:
        val = float(m.group(1))
        if 20.0 <= val <= 80.0:
            return val
    return None


def _parse_rating(rating_str: Optional[str]) -> Optional[float]:
    """Parse rating (already 0-5 scale on Wikiliq)."""
    if not rating_str:
        return None
    try:
        val = float(rating_str.replace(",", "."))
        if 0 < val <= 5.0:
            return round(val, 2)
    except (ValueError, TypeError):
        pass
    return None


def _parse_price(price_str: Optional[str]) -> Optional[float]:
    """Parse price from string."""
    if not price_str:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", price_str.replace(",", "."))
    if m:
        val = float(m.group(1))
        if 1.0 <= val <= 50000.0:
            return val
    return None


def _country_to_region(country: str) -> Optional[str]:
    """Map country to region."""
    c = (country or "").lower().strip()
    if c in ("scotland", "uk", "united kingdom"):
        return "Scotland"
    if c in ("usa", "united states", "us", "america"):
        return "United States"
    if c in ("ireland",):
        return "Ireland"
    if c in ("japan",):
        return "Japan"
    if c in ("canada",):
        return "Canada"
    return country.title() if country else None


def iter_wikiliq_whiskeys(data_dir: str) -> list[dict]:
    """
    Read the Wikiliq liquors CSV and yield whiskey dicts.

    Args:
        data_dir: Path to directory containing the unzipped Wikiliq CSVs.
                  Looks for 'liquors.csv' or similar.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        log.warning("Wikiliq data directory not found: %s", data_dir)
        return []

    # Find the liquors CSV (could be named differently)
    csv_file = None
    for candidate in ["liquors.csv", "Liquors.csv", "wikiliq_liquors.csv"]:
        path = data_path / candidate
        if path.exists():
            csv_file = path
            break

    # Also check for any CSV file in the directory
    if csv_file is None:
        csvs = list(data_path.glob("*.csv"))
        for c in csvs:
            if "liquor" in c.name.lower() or "spirit" in c.name.lower():
                csv_file = c
                break
        # If still none, try the first CSV
        if csv_file is None and csvs:
            csv_file = csvs[0]
            log.info("No 'liquors.csv' found, trying %s", csv_file.name)

    if csv_file is None:
        log.warning("No CSV files found in %s", data_dir)
        return []

    log.info("Reading Wikiliq data from %s", csv_file)

    results = []
    seen_names = set()

    with open(csv_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Flexible column name resolution
            name = (row.get("Name") or row.get("name") or "").strip()
            categories = (row.get("Categories") or row.get("categories") or "").strip()
            brand = (row.get("Brand") or row.get("brand") or "").strip()
            country = (row.get("Country") or row.get("country") or "").strip()
            abv_str = (row.get("ABV") or row.get("abv") or row.get("Alcohol") or "").strip()
            rating_str = (row.get("Rating") or row.get("rating") or "").strip()
            rate_count_str = (row.get("Rate Count") or row.get("rate_count") or "").strip()
            price_str = (row.get("Price") or row.get("price") or "").strip()
            description = (row.get("Description") or row.get("description") or "").strip()

            if not name or len(name) < 3:
                continue

            if not _is_whiskey(categories, name):
                continue

            # Dedup by name
            name_key = name.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            category = _infer_category(categories, name)
            abv = _parse_abv(abv_str)
            # Only trust ratings that have real user reviews behind them
            try:
                rate_count = int(rate_count_str) if rate_count_str else 0
            except (ValueError, TypeError):
                rate_count = 0
            rating = _parse_rating(rating_str) if rate_count > 0 else None
            price = _parse_price(price_str)
            region = _country_to_region(country)

            results.append({
                "name": name,
                "distillery": brand or "Unknown",
                "category": category,
                "region": region,
                "abv": abv or 40.0,
                "price_usd": price,
                "rating_avg": rating or 0.0,
                "description": description[:500] if description else None,
                "source": "wikiliq",
            })

    log.info("Wikiliq: %d whiskey products from %s", len(results), csv_file.name)
    return results
