"""
Normalizes raw scraped dicts into kwargs that match app.models.Whiskey.

Raw dicts from WhiskybaseScraper may contain messy strings like:
  abv_str: "46.0%"
  age_str: "12 years"
  rating_str: "84.5 (1,234 votes)"
  country:  "Scotland"
  category from Whiskybase: "Single Malt Scotch Whisky"

This module cleans all of that into typed values our DB model expects.
"""

import re
from typing import Optional

# ── Category mapping ──────────────────────────────────────────────────────
# Maps fragments of Whiskybase category strings → our normalized category
CATEGORY_MAP = [
    # Order matters — more specific first
    ("bourbon",       "bourbon"),
    ("tennessee",     "bourbon"),        # Tennessee whiskey is legally bourbon-adjacent
    ("rye",           "rye"),
    ("wheat",         "bourbon"),        # wheated whiskey
    ("single malt",   "single malt"),
    ("single grain",  "single grain"),
    ("blended malt",  "blended"),
    ("blended scotch","scotch"),
    ("scotch",        "scotch"),
    ("irish",         "irish"),
    ("japanese",      "japanese"),
    ("canadian",      "canadian"),
    ("blended",       "blended"),
    ("american",      "bourbon"),        # catch-all American whiskey
    ("welsh",         "single malt"),
    ("english",       "single malt"),
    ("indian",        "single malt"),
    ("taiwanese",     "single malt"),
]

# Maps country → default category when no explicit category is given
COUNTRY_CATEGORY_MAP = {
    "scotland":       "scotch",
    "united states":  "bourbon",
    "usa":            "bourbon",
    "ireland":        "irish",
    "japan":          "japanese",
    "canada":         "canadian",
}

# ── Currency conversion ───────────────────────────────────────────────────
# Static approximate rates (update periodically if needed)
# Sources that use GBP: masterofmalt, whiskyexchange
# Sources that use NOK: vinmonopolet
_GBP_TO_USD = 1.27
_NOK_TO_USD = 0.091
_EUR_TO_USD = 1.05

_SOURCE_CURRENCY: dict[str, str] = {
    "masterofmalt":   "GBP",
    "whiskyexchange": "GBP",
    "vinmonopolet":   "NOK",
    # all others assumed USD
}

# Keywords in product names that indicate non-whiskey products
# Only flag products that are clearly NOT whiskey.
# Conservative: words like "rum", "wine", "port", "ale", "brandy", "cognac"
# are NOT flagged because they appear in cask finishes and distillery names.
_ALWAYS_REJECT_RE = re.compile(
    r"\b(?:vodka|tequila|mezcal|absinthe|schnapps|sake|soju|baijiu"
    r"|grappa|vermouth|cachaca|liqueur|creme de|cream de"
    r"|fireball|regal apple|barley\s*wine"
    r"|cocktail|margarita|mojito|cola\b.*\bblik"
    r"|new\s*make|new\s*spirit|new[\s-]*malt\s*spirit|poit[ií]n|poteen"
    r"|protein|supplement|powder"
    r"|merlot|cabernet|chardonnay|pinot|zinfandel)\b", re.I
)
# "Gin" needs special care — flag unless whiskey-related words present
_GIN_RE = re.compile(r"\bgin\b", re.I)
_GIN_SAFE_RE = re.compile(r"\b(?:whisk|bourbon|scotch|malt|begin|ginger|engine|origin|virgin)\b", re.I)

# RTD (ready-to-drink) mixed products: "Whiskey & Cola", "Bourbon & Soda", etc.
_RTD_RE = re.compile(r"\b(?:whisky|whiskey|bourbon)\b.*&\s*(?:cola|soda|lemonade|ginger\s*ale)\b", re.I)

# Maps country / region → normalized region label
REGION_MAP = {
    # Scottish sub-regions
    "speyside":    "Speyside",
    "islay":       "Islay",
    "highlands":   "Highlands",
    "highland":    "Highlands",
    "lowlands":    "Lowlands",
    "lowland":     "Lowlands",
    "campbeltown": "Campbeltown",
    "islands":     "Islands",

    # USA sub-regions
    "kentucky":    "Kentucky",
    "tennessee":   "Tennessee",
    "vermont":     "Vermont",
    "indiana":     "Indiana",

    # Countries — English canonical
    "scotland":    "Scotland",
    "ireland":     "Ireland",
    "japan":       "Japan",
    "canada":      "Canada",
    "france":      "France",
    "germany":     "Germany",
    "india":       "India",
    "taiwan":      "Taiwan",
    "australia":   "Australia",
    "england":     "England",
    "wales":       "Wales",
    "usa":         "USA",
    "united states": "USA",
    "norway":      "Norway",
    "sweden":      "Sweden",
    "denmark":     "Denmark",
    "finland":     "Finland",
    "belgium":     "Belgium",
    "netherlands": "Netherlands",
    "switzerland": "Switzerland",
    "italy":       "Italy",
    "spain":       "Spain",
    "new zealand": "New Zealand",
    "south africa": "South Africa",
    "mexico":      "Mexico",

    # Norwegian / Swedish variants
    "skottland":   "Scotland",
    "frankrike":   "France",
    "storbritannia": "United Kingdom",
    "spania":      "Spain",
    "tyskland":    "Germany",
    "danmark":     "Denmark",
    "sverige":     "Sweden",
    "norge":       "Norway",
    "belgia":      "Belgium",

    # German variants
    "deutschland": "Germany",
    "frankreich":  "France",
    "belgien":     "Belgium",
    "australien":  "Australia",
    "irland":      "Ireland",
    "schweiz":     "Switzerland",
    "kanada":      "Canada",

    # French variants
    "australie":   "Australia",
    "belgique":    "Belgium",
    "nederland":   "Netherlands",
    "suisse":      "Switzerland",

    # Spanish / Italian variants
    "francia":     "France",
    "alemania":    "Germany",
    "italia":      "Italy",
    "espana":      "Spain",

    # Irish sub-regions
    "county cork": "County Cork",

    # Two-letter codes (from OpenFoodFacts En: prefix after stripping)
    "fr": "France",
    "de": "Germany",
    "gb": "United Kingdom",
    "us": "USA",
    "au": "Australia",
    "it": "Italy",
    "es": "Spain",
    "ca": "Canada",

    # Norwegian misc
    "s\u00f8r-afrika": "South Africa",
}


def normalize(raw: dict) -> Optional[dict]:
    """
    Convert a raw scraped dict to a Whiskey model kwargs dict.
    Returns None if the entry is too incomplete to be useful.
    """
    name = _clean_str(raw.get("name"))
    if not name:
        return None

    # Reject products that are not actual whiskey based on name keywords
    if _ALWAYS_REJECT_RE.search(name):
        return None
    if _GIN_RE.search(name) and not _GIN_SAFE_RE.search(name):
        return None
    if _RTD_RE.search(name):
        return None

    distillery = _clean_str(raw.get("distillery")) or _clean_str(raw.get("brand")) or "Unknown"
    if distillery.lower() in ("", "unknown", "-", "n/a"):
        distillery = "Unknown"

    abv = _parse_abv(raw.get("abv_str") or raw.get("abv"))
    if abv is None:
        return None  # ABV is required in our schema

    category_raw = _clean_str(raw.get("category") or raw.get("type") or "") or ""
    country = (_clean_str(raw.get("country") or "") or "").lower()
    category = _normalize_category(category_raw, country)

    region_raw = _clean_str(raw.get("region") or country or "") or ""
    region = _normalize_region(region_raw)

    age = _parse_age(raw.get("age_str") or raw.get("age"))
    rating_avg, rating_count = _parse_rating(raw.get("rating_str") or raw.get("rating"))
    source = _clean_str(raw.get("source")) or ""
    price_usd = _parse_price(raw.get("price_str") or raw.get("price_usd"), source)

    description = _clean_str(raw.get("description"))
    flavor_profile = _clean_str(raw.get("flavor_profile"))

    return {
        "name":          name,
        "distillery":    distillery,
        "category":      category,
        "region":        region,
        "age":           age,
        "abv":           abv,
        "price_usd":     price_usd,
        "description":   description[:1000] if description else None,
        "flavor_profile": flavor_profile,
        "rating_avg":    rating_avg,
        "rating_count":  rating_count,
        "upc":           _clean_str(raw.get("upc")),
    }


# ── Parsers ───────────────────────────────────────────────────────────────

def _clean_str(val) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    if s in ("", "-", "N/A", "n/a", "None"):
        return None
    return s


def _parse_abv(val) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace("%", "").replace(",", ".").strip()
    m = re.search(r"(\d+\.?\d*)", s)
    if not m:
        return None
    abv = float(m.group(1))
    if not (25.0 <= abv <= 95.0):
        return None  # Below 25% is certainly not whiskey (beer, wine, cocktail)
    return round(abv, 1)


def _parse_age(val) -> Optional[int]:
    if val is None:
        return None
    s = str(val).lower()
    if "nas" in s or "no age" in s:
        return None
    m = re.search(r"(\d+)", s)
    if not m:
        return None
    age = int(m.group(1))
    if not (1 <= age <= 80):
        return None
    return age


def _parse_rating(val) -> tuple[float, int]:
    """Returns (rating_avg, rating_count). Whiskybase uses 0–100 scale; we store 0–5."""
    if val is None:
        return 0.0, 0
    s = str(val)

    # Extract vote count if present: "84.5 (1,234 votes)"
    count_match = re.search(r"\(?([\d,]+)\s*votes?\)?", s, re.I)
    count = int(count_match.group(1).replace(",", "")) if count_match else 0

    score_match = re.search(r"(\d+\.?\d*)", s)
    if not score_match:
        return 0.0, count

    raw_score = float(score_match.group(1))

    # Whiskybase uses 0–100; convert to 0–5
    if raw_score > 5:
        avg = round((raw_score / 100.0) * 5.0, 2)
    else:
        avg = round(raw_score, 2)

    return min(avg, 5.0), count


def _parse_price(val, source: str = "") -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "")
    m = re.search(r"(\d+\.?\d*)", s)
    if not m:
        return None
    price = float(m.group(1))

    # Convert to USD based on source currency
    currency = _SOURCE_CURRENCY.get(source, "USD")
    if currency == "GBP":
        price *= _GBP_TO_USD
    elif currency == "NOK":
        price *= _NOK_TO_USD
    elif currency == "EUR":
        price *= _EUR_TO_USD

    if not (1.0 <= price <= 50_000.0):
        return None
    return round(price, 2)


def _normalize_category(category_raw: str, country: str) -> str:
    lower = category_raw.lower()
    for fragment, mapped in CATEGORY_MAP:
        if fragment in lower:
            return mapped

    # Fall back to country-based inference
    return COUNTRY_CATEGORY_MAP.get(country, "world")  # 'world' for unknown origin


def _normalize_region(region_raw: str) -> Optional[str]:
    if not region_raw:
        return None
    cleaned = region_raw.strip()
    # Strip OpenFoodFacts "En:", "Nl:", etc. prefixes
    if len(cleaned) > 3 and cleaned[2] == ":" and cleaned[:2].isalpha():
        cleaned = cleaned[3:]
    lower = cleaned.lower().strip()
    for fragment, mapped in REGION_MAP.items():
        if fragment in lower:
            return mapped
    # If it's a short, clean string, keep it as-is (e.g. "Kentucky")
    cleaned = cleaned.strip().title()
    return cleaned if 2 < len(cleaned) < 40 else None
