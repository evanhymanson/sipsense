"""
Imports whiskeys from multiple Kaggle CSV datasets.

Supported datasets (download CSVs into scraper/data/kaggle/):
  - scotch_review.csv     — ~2,200 scotch reviews (koki25ando/22000-scotch-whisky-reviews)
  - whiskey_prices.csv    — whiskey pricing data (shivd24coder/wiskey-price-dataset)
  - meta_critic.csv       — ~356 meta-critic scores (avis02/meta-critic-whisky-database)

This is a fast, zero-rate-limit source — runs locally on CSVs.
"""

import csv
import logging
import re
from pathlib import Path
from typing import Generator, Optional

from .normalizer import normalize

log = logging.getLogger(__name__)


# ── Per-dataset column configurations ─────────────────────────────────────

DATASET_CONFIGS = {
    "scotch_review": {
        "filenames": ["scotch_review.csv", "scotch_reviews.csv", "whisky.csv"],
        "columns": {
            "name": ["name", "Name", "whisky_name", "Whisky"],
            "category": ["category", "Category", "type", "Type"],
            "rating": ["review.point", "ReviewPoint", "rating", "Rating", "score", "Score"],
            "price": ["price", "Price", "cost", "Cost"],
            "description": ["description", "Description", "review", "Review"],
        },
        "default_category": "scotch",
        "default_country": "scotland",
    },
    "whiskey_prices": {
        "filenames": ["whiskey_prices.csv", "wiskey_price.csv", "whisky_prices.csv"],
        "columns": {
            "name": ["name", "Name", "title", "Title", "brand", "Brand"],
            "category": ["category", "Category", "type", "Type"],
            "price": ["price", "Price", "avg_price", "AvgPrice"],
            "rating": ["rating", "Rating", "score", "Score"],
            "description": ["description", "Description"],
            "abv": ["abv", "ABV", "alcohol", "Alcohol"],
            "age": ["age", "Age"],
        },
        "default_category": "bourbon",
        "default_country": "usa",
    },
    "meta_critic": {
        "filenames": ["meta_critic.csv", "metacritic.csv", "whisky_metacritic.csv"],
        "columns": {
            "name": ["name", "Name", "whisky", "Whisky", "Whiskey"],
            "category": ["class", "Class", "category", "Category", "type", "Type"],
            "rating": ["STDEV", "metascore", "MetaScore", "rating", "Rating"],
            "price": ["cost", "Cost", "price", "Price"],
            "description": ["cluster", "Cluster"],
        },
        "default_category": "scotch",
        "default_country": "scotland",
    },
}

# Known distilleries for extraction from name strings
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


def _find_csv(data_dir: Path, filenames: list[str]) -> Optional[Path]:
    """Find the first matching CSV file in the data directory."""
    for fn in filenames:
        path = data_dir / fn
        if path.exists():
            return path
    # Also check case-insensitively
    for f in data_dir.iterdir():
        if f.suffix.lower() == ".csv" and f.stem.lower() in [
            Path(fn).stem.lower() for fn in filenames
        ]:
            return f
    return None


def _resolve_column(row: dict, candidates: list[str]) -> Optional[str]:
    """Find the first matching column name and return its value."""
    for col in candidates:
        if col in row and row[col]:
            return str(row[col]).strip()
    return None


def _extract_distillery(name: str) -> str:
    """Try to extract a known distillery from the whiskey name."""
    name_lower = name.lower()
    for d in KNOWN_DISTILLERIES:
        if d.lower() in name_lower:
            return d
    return "Unknown"


def _extract_abv_from_name(name: str) -> Optional[str]:
    """Try to extract ABV from the whiskey name string."""
    m = re.search(r"(\d{2,3}(?:\.\d+)?)\s*%", name)
    if m:
        return m.group(1)
    return None


def _extract_age_from_name(name: str) -> Optional[str]:
    """Try to extract age from the whiskey name string."""
    m = re.search(r"(\d{1,2})\s*(?:year|yr|yo|y\.o)", name, re.I)
    if m:
        return m.group(1)
    return None


def iter_kaggle_whiskeys(
    data_dir: str | Path,
    dataset_name: Optional[str] = None,
) -> Generator[dict, None, None]:
    """
    Iterate over whiskeys from Kaggle CSV datasets.

    Args:
        data_dir: Path to directory containing downloaded Kaggle CSVs
        dataset_name: Optional specific dataset to import (default: all)
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        log.error("Kaggle data directory not found: %s", data_dir)
        return

    configs = (
        {dataset_name: DATASET_CONFIGS[dataset_name]}
        if dataset_name and dataset_name in DATASET_CONFIGS
        else DATASET_CONFIGS
    )

    for ds_name, config in configs.items():
        csv_path = _find_csv(data_dir, config["filenames"])
        if csv_path is None:
            log.info("Dataset %s: no matching CSV found in %s, skipping", ds_name, data_dir)
            continue

        log.info("Importing dataset %s from %s", ds_name, csv_path)
        count = 0

        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = _resolve_column(row, config["columns"]["name"])
                    if not name or len(name) < 3:
                        continue

                    raw = {
                        "name": name,
                        "distillery": _extract_distillery(name),
                        "category": (
                            _resolve_column(row, config["columns"].get("category", []))
                            or config.get("default_category", "scotch")
                        ),
                        "country": config.get("default_country", ""),
                        "abv_str": (
                            _resolve_column(row, config["columns"].get("abv", []))
                            or _extract_abv_from_name(name)
                            or "40.0"
                        ),
                        "age_str": (
                            _resolve_column(row, config["columns"].get("age", []))
                            or _extract_age_from_name(name)
                        ),
                        "rating_str": _resolve_column(row, config["columns"].get("rating", [])),
                        "price_str": _resolve_column(row, config["columns"].get("price", [])),
                        "description": _resolve_column(row, config["columns"].get("description", [])),
                        "source": "kaggle",
                    }

                    normalized = normalize(raw)
                    if normalized is None:
                        continue

                    normalized["source"] = "kaggle"
                    yield normalized
                    count += 1

        except Exception as exc:
            log.error("Error reading %s: %s", csv_path, exc)
            continue

        log.info("Dataset %s: yielded %d whiskeys", ds_name, count)
