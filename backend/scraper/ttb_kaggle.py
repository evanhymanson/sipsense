"""
Imports whiskeys from the COLA Cloud TTB Kaggle demo dataset.

Source: https://www.kaggle.com/datasets/colacloud/ttb-colas-demo
Data: 2018 label approvals from TTB COLA Registry, enriched with OCR-extracted ABV.

Download the dataset ZIP, extract the CSV, and place it in scraper/data/ or
pass the path via --ttb-file.

Expected ~15K-30K raw spirit entries; after filtering to whiskey-only and
deduplication of size variants, yields ~5K-10K unique whiskeys.
"""

import csv
import logging
import re
from pathlib import Path
from typing import Generator, Optional

from .normalizer import normalize

log = logging.getLogger(__name__)

# TTB class/type descriptions that indicate whiskey
WHISKEY_TYPE_KEYWORDS = [
    "whisky", "whiskey", "bourbon", "scotch", "rye",
    "malt", "tennessee", "irish", "blended", "single malt",
    "corn whiskey", "wheat whiskey", "light whiskey",
    "spirit whiskey", "american whiskey", "canadian",
    "grain whisky", "grain whiskey",
]

# Non-whiskey spirit types to explicitly exclude
NON_WHISKEY_TYPES = [
    "vodka", "gin", "rum", "tequila", "mezcal", "brandy",
    "cognac", "armagnac", "liqueur", "cordial", "schnapps",
    "absinthe", "sake", "soju", "baijiu", "grappa",
    "vermouth", "bitters", "amaro", "cachaca",
]

# Possible column name variants in COLA Cloud data
COLUMN_VARIANTS = {
    "ttb_id": ["ttb_id", "TTB_ID", "cola_id", "COLA_ID", "id", "ID"],
    "brand_name": ["brand_name", "BRAND_NAME", "brand", "BRAND"],
    "fanciful_name": ["fanciful_name", "FANCIFUL_NAME", "fanciful", "FANCIFUL",
                      "product_name", "PRODUCT_NAME"],
    # CLASS_NAME must come before PRODUCT_TYPE — CLASS_NAME has whiskey type
    # (e.g. "straight bourbon whisky"), PRODUCT_TYPE is generic ("distilled spirits")
    "class_type": ["CLASS_NAME", "class_name", "class_type_description",
                   "CLASS_TYPE_DESCRIPTION", "class_type", "CLASS_TYPE",
                   "type", "TYPE", "product_type", "PRODUCT_TYPE"],
    "product_type": ["PRODUCT_TYPE", "product_type"],
    "origin": ["ORIGIN_NAME", "origin_name", "origin_country", "ORIGIN_COUNTRY",
               "origin", "ORIGIN", "country", "COUNTRY"],
    "company": ["APPLICANT_NAME", "applicant_name", "company_name", "COMPANY_NAME",
                "applicant", "APPLICANT", "permit_holder", "PERMIT_HOLDER"],
    "abv": ["OCR_ABV", "ocr_abv", "abv", "ABV", "alcohol_content",
            "ALCOHOL_CONTENT"],
    "status": ["APPLICATION_STATUS", "application_status", "status", "STATUS",
               "cola_status", "COLA_STATUS"],
    "description": ["LLM_TASTING_NOTES", "LLM_PRODUCT_DESCRIPTION"],
    "age_llm": ["LLM_LIQUOR_AGED_YEARS"],
    "category_path": ["LLM_CATEGORY_PATH"],
    "barcode": ["BARCODE_VALUE"],
}


def _resolve(row: dict, key: str) -> Optional[str]:
    """Find the first matching column name variant and return its value."""
    for col in COLUMN_VARIANTS.get(key, []):
        if col in row and row[col]:
            val = str(row[col]).strip()
            if val and val not in ("", "-", "N/A", "None"):
                return val
    return None


def _is_whiskey_type(class_type: str) -> bool:
    """Check if the class/type description indicates a whiskey product."""
    lower = class_type.lower()
    # Exclude non-whiskey first
    if any(nw in lower for nw in NON_WHISKEY_TYPES):
        return False
    return any(kw in lower for kw in WHISKEY_TYPE_KEYWORDS)


def _build_name(brand: str, fanciful: Optional[str]) -> str:
    """Build a whiskey name from brand and fanciful name fields."""
    if fanciful and fanciful.lower() != brand.lower():
        # Check if fanciful already contains brand
        if brand.lower() in fanciful.lower():
            return fanciful
        return f"{brand} {fanciful}"
    return brand


def _parse_abv(val: Optional[str]) -> Optional[str]:
    """Parse ABV from OCR-extracted or raw string."""
    if not val:
        return None
    # Extract numeric value
    m = re.search(r"(\d+\.?\d*)", str(val))
    if m:
        abv = float(m.group(1))
        if 25.0 <= abv <= 95.0:
            return str(abv)
    return None


def _country_to_category(country: str) -> str:
    """Infer category from country of origin."""
    lower = country.lower()
    if "scotland" in lower or "uk" in lower or "united kingdom" in lower:
        return "scotch"
    if "ireland" in lower:
        return "irish"
    if "japan" in lower:
        return "japanese"
    if "canada" in lower:
        return "canadian"
    if "us" in lower or "america" in lower:
        return "bourbon"
    return "blended"


def _extract_age(name: str) -> Optional[str]:
    """Try to extract age from the product name."""
    m = re.search(r"(\d{1,2})\s*(?:year|yr|yo|y\.o)", name, re.I)
    if m:
        return m.group(1)
    return None


def iter_ttb_whiskeys(file_path: str | Path) -> Generator[dict, None, None]:
    """
    Iterate over whiskeys from a TTB COLA CSV file.

    Args:
        file_path: Path to the COLA Cloud CSV file
    """
    file_path = Path(file_path)
    if not file_path.exists():
        log.error("TTB file not found: %s", file_path)
        return

    log.info("Loading TTB COLA data from %s", file_path)

    # Track seen (brand, fanciful, type) combos to collapse size variants
    seen_keys: set[str] = set()
    total = 0
    filtered = 0
    deduped = 0

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total += 1

                # Pre-filter: if PRODUCT_TYPE exists, must be distilled spirits
                product_type = _resolve(row, "product_type")
                if product_type and "spirit" not in product_type.lower():
                    filtered += 1
                    continue

                # Filter by status (only approved labels)
                status = _resolve(row, "status")
                if status and "approv" not in status.lower():
                    continue

                # Filter by class/type (CLASS_NAME in colas_2017.csv)
                class_type = _resolve(row, "class_type") or ""
                if not _is_whiskey_type(class_type):
                    # Fallback: check LLM_CATEGORY_PATH for whiskey classification
                    cat_path = _resolve(row, "category_path") or ""
                    if not any(kw in cat_path.lower() for kw in WHISKEY_TYPE_KEYWORDS):
                        filtered += 1
                        continue

                brand = _resolve(row, "brand_name")
                if not brand or len(brand) < 2:
                    continue

                fanciful = _resolve(row, "fanciful_name")
                name = _build_name(brand, fanciful)

                if len(name) < 3:
                    continue

                # Dedup by (brand, fanciful, class) to collapse size variants
                dedup_key = f"{brand.lower()}|{(fanciful or '').lower()}|{class_type.lower()}"
                if dedup_key in seen_keys:
                    deduped += 1
                    continue
                seen_keys.add(dedup_key)

                # Parse fields
                origin = _resolve(row, "origin") or ""
                abv_str = _parse_abv(_resolve(row, "abv")) or "40.0"
                category_from_type = ""
                for kw in WHISKEY_TYPE_KEYWORDS:
                    if kw in class_type.lower():
                        category_from_type = kw
                        break

                # Use LLM age if available, else extract from name
                age_str = _resolve(row, "age_llm") or _extract_age(name)

                # Use LLM tasting notes as description
                description = _resolve(row, "description")

                # Get UPC barcode
                upc = _resolve(row, "barcode")

                raw = {
                    "name": name,
                    "distillery": _resolve(row, "company") or "Unknown",
                    "category": category_from_type or class_type,
                    "country": origin,
                    "abv_str": abv_str,
                    "age_str": age_str,
                    "description": description,
                    "source": "ttb",
                }

                normalized = normalize(raw)
                if normalized is None:
                    continue

                normalized["source"] = "ttb"
                if upc:
                    normalized["upc"] = upc
                yield normalized

    except Exception as exc:
        log.error("Error reading TTB file %s: %s", file_path, exc)

    log.info(
        "TTB COLA: total=%d  filtered(non-whiskey)=%d  deduped(size variants)=%d  "
        "unique keys=%d",
        total, filtered, deduped, len(seen_keys),
    )
