"""
Deduplication engine for whiskey entries.

Provides multi-layer duplicate detection:
  1. Name normalization (strip suffixes, normalize age, remove sizes)
  2. Exact match on normalized name
  3. Fuzzy match via rapidfuzz for near-duplicates

Usage:
    index = DedupIndex()
    index.load_from_db(db)
    if index.is_duplicate("The Macallan 12 Year Old Single Malt Scotch Whisky"):
        print("duplicate!")
"""

import re
import logging
from typing import Optional

log = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    log.warning(
        "rapidfuzz not installed — fuzzy dedup disabled. "
        "Install with: pip install rapidfuzz>=3.0.0"
    )

# ── Name normalization ────────────────────────────────────────────────────

# Common suffixes to strip (order: longer/more-specific first)
_SUFFIXES_TO_STRIP = [
    "kentucky straight bourbon whiskey",
    "kentucky straight bourbon",
    "single malt scotch whisky",
    "single malt scotch whiskey",
    "blended scotch whisky",
    "blended scotch whiskey",
    "single malt whisky",
    "single malt whiskey",
    "blended malt whisky",
    "blended malt whiskey",
    "scotch whisky",
    "scotch whiskey",
    "irish whiskey",
    "irish whisky",
    "bourbon whiskey",
    "bourbon whisky",
    "tennessee whiskey",
    "tennessee whisky",
    "canadian whisky",
    "canadian whiskey",
    "japanese whisky",
    "japanese whiskey",
    "american whiskey",
    "american whisky",
    "rye whiskey",
    "rye whisky",
    "corn whiskey",
    "wheat whiskey",
    "grain whisky",
    "whisky",
    "whiskey",
]

# Bottle sizes to strip
_SIZE_PATTERNS = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*(?:ml|cl|l|liter|litre|oz|fl\s*oz))\b",
    re.IGNORECASE,
)

# Age normalization: "12 year old", "12 years", "12yr", "12 yo" → "12yo"
_AGE_PATTERNS = [
    re.compile(r"(\d+)\s*(?:year[s]?\s*old|year[s]?|yr[s]?\s*old|yr[s]?|yo|y\.o\.?)", re.I),
]


def normalize_name_for_dedup(name: str) -> str:
    """
    Normalize a whiskey name for deduplication comparison.

    Examples:
        "The Macallan 12 Year Old Single Malt Scotch Whisky" → "macallan 12yo"
        "Macallan 12 Year"  → "macallan 12yo"
        "Macallan 12yr"     → "macallan 12yo"
        "Jack Daniel's Old No. 7 Tennessee Whiskey 750ml" → "jack daniels old no 7"
    """
    s = name.lower().strip()

    # Strip leading "the "
    if s.startswith("the "):
        s = s[4:]

    # Normalize age expressions to compact form
    for pat in _AGE_PATTERNS:
        s = pat.sub(r"\1yo", s)

    # Strip common whiskey-type suffixes
    for suffix in _SUFFIXES_TO_STRIP:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
        # Also check with trailing whitespace
        padded = " " + suffix
        if padded in s:
            s = s.replace(padded, "")

    # Strip bottle sizes
    s = _SIZE_PATTERNS.sub("", s)

    # Normalize punctuation
    s = s.replace("'", "").replace("'", "").replace("`", "")
    s = s.replace("–", "-").replace("—", "-")

    # Remove trailing/leading punctuation and collapse whitespace
    s = re.sub(r"[^\w\s-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip("-").strip()

    return s


# ── Dedup Index ───────────────────────────────────────────────────────────

class DedupIndex:
    """
    In-memory index for fast duplicate detection.

    Supports:
      - Exact match on normalized names (fast, O(1))
      - Fuzzy match for near-duplicates (slower, only when exact fails)
    """

    # Fuzzy match threshold (0-100). 92+ with same first chars = duplicate.
    FUZZY_THRESHOLD = 92

    def __init__(self, enable_fuzzy: bool = True):
        self._normalized: set[str] = set()
        self._raw_to_normalized: dict[str, str] = {}
        self._enable_fuzzy = enable_fuzzy and HAS_RAPIDFUZZ
        # For fuzzy matching, group by first 4 chars to avoid O(n^2)
        self._buckets: dict[str, list[str]] = {}

    def add(self, name: str, distillery: Optional[str] = None):
        """Add a whiskey name to the index."""
        norm = normalize_name_for_dedup(name)
        if not norm:
            return
        self._normalized.add(norm)
        self._raw_to_normalized[name.lower()] = norm

        if self._enable_fuzzy:
            bucket_key = norm[:4] if len(norm) >= 4 else norm
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = []
            self._buckets[bucket_key].append(norm)

    def is_duplicate(self, name: str, distillery: Optional[str] = None) -> bool:
        """
        Check if a whiskey name is a duplicate of an existing entry.

        Layer 1: Exact match on normalized name (fast)
        Layer 2: Fuzzy match within same bucket (slower, if enabled)
        """
        norm = normalize_name_for_dedup(name)
        if not norm:
            return False

        # Layer 1: exact match on normalized name
        if norm in self._normalized:
            return True

        # Layer 2: fuzzy match (only if rapidfuzz is available)
        if self._enable_fuzzy:
            bucket_key = norm[:4] if len(norm) >= 4 else norm
            candidates = self._buckets.get(bucket_key, [])
            for existing in candidates:
                score = fuzz.token_sort_ratio(norm, existing)
                if score >= self.FUZZY_THRESHOLD:
                    log.debug(
                        "Fuzzy match (%.0f%%): %r ≈ %r",
                        score, norm, existing,
                    )
                    return True

        return False

    def __len__(self) -> int:
        return len(self._normalized)

    def __contains__(self, name: str) -> bool:
        return self.is_duplicate(name)
