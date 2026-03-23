"""
Seed UPC/EAN barcodes for whiskeys in the database.

Chains five free lookup sources in order of whiskey coverage quality:
  1. Whiskybase scraper        (largest whiskey DB, barcode on product pages)
  2. The Whisky Exchange       (EAN codes on all product pages, global coverage)
  3. Total Wine scraper        (large US spirits catalog, UPC in JSON-LD)
  4. ReserveBar scraper        (premium US spirits, UPC in structured data)
  5. Open Food Facts           (broad fallback, thin spirits coverage)

All sources are completely free — no API keys required.

Usage:
    cd backend
    python -m scripts.seed_upc_codes              # process all missing
    python -m scripts.seed_upc_codes --limit 50   # first 50 only
    python -m scripts.seed_upc_codes --dry-run     # preview, no DB writes
    python -m scripts.seed_upc_codes --source whiskybase,whisky_exchange
    python -m scripts.seed_upc_codes --overwrite  # re-check already-filled rows
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app import models


# ── HTTP helpers ───────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str, extra_headers: dict = None, timeout: int = 12) -> str | None:
    try:
        h = {**HEADERS, **(extra_headers or {})}
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _get_json(url: str, extra_headers: dict = None, timeout: int = 12) -> dict | None:
    body = _get(url, extra_headers=extra_headers, timeout=timeout)
    if not body:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def _name_similarity(a: str, b: str) -> float:
    """Word-overlap score 0–1. Strips common filler words."""
    stop = {"the", "a", "an", "of", "and", "&", "single", "barrel",
            "batch", "edition", "year", "old", "cask", "strength", "distillery"}
    a_words = set(a.lower().split()) - stop
    b_words = set(b.lower().split()) - stop
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / max(len(a_words), len(b_words))


def _extract_json_ld(html: str) -> list[dict]:
    results = []
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL
    ):
        try:
            results.append(json.loads(m.group(1)))
        except Exception:
            pass
    return results


def _clean_upc(code: str) -> str | None:
    """Strip non-digits, validate length (8, 12, or 13 digits)."""
    digits = re.sub(r"\D", "", code)
    return digits if len(digits) in (8, 12, 13) else None


# ── Source 1: Whiskybase ──────────────────────────────────────────────────

def lookup_whiskybase(name: str) -> str | None:
    """
    Whiskybase is the largest whiskey-specific database.
    Product pages include an EAN/barcode field for most bottles.
    """
    q = urllib.parse.quote_plus(name)
    search_url = f"https://www.whiskybase.com/search?q={q}"
    html = _get(search_url)
    if not html:
        return None

    # Extract product links from search results
    paths = re.findall(r'href="(/whiskies/\d+/[^"?#]+)"', html)
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen and len(unique) < 4:
            seen.add(p)
            unique.append(p)

    for path in unique:
        product_html = _get(f"https://www.whiskybase.com{path}")
        if not product_html:
            continue

        # Whiskybase shows: <dt>Barcode</dt><dd>XXXXXXXX</dd>
        barcode_match = re.search(
            r'<dt[^>]*>[^<]*[Bb]arcode[^<]*</dt>\s*<dd[^>]*>(\d[\d\s]+)</dd>',
            product_html
        )
        if barcode_match:
            candidate = _clean_upc(barcode_match.group(1))
            if candidate:
                # Verify name match from page title
                title_match = re.search(r'<h1[^>]*>([^<]{3,80})</h1>', product_html)
                page_name = title_match.group(1).strip() if title_match else ""
                if _name_similarity(name, page_name) >= 0.4:
                    return candidate

        time.sleep(0.4)

    return None


# ── Source 2: The Whisky Exchange ─────────────────────────────────────────

def lookup_whisky_exchange(name: str) -> str | None:
    """
    The Whisky Exchange lists EAN codes on every product page.
    Excellent global coverage for Scotch, Irish, Japanese, and world whisky.
    """
    q = urllib.parse.quote_plus(name)
    search_url = f"https://www.thewhiskyexchange.com/search?q={q}"
    html = _get(search_url)
    if not html:
        return None

    # Product links look like /p/12345/name-of-whisky
    paths = re.findall(r'href="(/p/\d+/[^"?#]+)"', html)
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen and len(unique) < 4:
            seen.add(p)
            unique.append(p)

    for path in unique:
        product_html = _get(f"https://www.thewhiskyexchange.com{path}")
        if not product_html:
            continue

        # TWE shows EAN in product details table
        ean_match = re.search(
            r'(?:EAN|Barcode|GTIN)[^\d]*(\d{8}|\d{12}|\d{13})',
            product_html, re.IGNORECASE
        )
        if ean_match:
            candidate = _clean_upc(ean_match.group(1))
            if candidate:
                title_match = re.search(r'<h1[^>]*>([^<]{3,80})</h1>', product_html)
                page_name = title_match.group(1).strip() if title_match else ""
                if _name_similarity(name, page_name) >= 0.4:
                    return candidate

        # Also check JSON-LD
        for ld in _extract_json_ld(product_html):
            product_name = ld.get("name", "")
            gtin = ld.get("gtin13") or ld.get("gtin12") or ld.get("gtin") or ""
            if gtin:
                candidate = _clean_upc(gtin)
                if candidate and _name_similarity(name, product_name) >= 0.4:
                    return candidate

        time.sleep(0.4)

    return None


# ── Source 3: Total Wine ──────────────────────────────────────────────────

def lookup_total_wine(name: str) -> str | None:
    """
    Total Wine product pages embed UPC in JSON-LD structured data.
    Best for American whiskey / bourbon.
    """
    q = urllib.parse.quote_plus(name)
    html = _get(f"https://www.totalwine.com/search/all?text={q}&tab=fullcatalog")
    if not html:
        return None

    paths = re.findall(r'href="(/spirits/[^"?#]+)"', html)
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen and len(unique) < 3:
            seen.add(p)
            unique.append(p)

    for path in unique:
        product_html = _get(f"https://www.totalwine.com{path}")
        if not product_html:
            continue

        for ld in _extract_json_ld(product_html):
            product_name = ld.get("name", "")
            gtin = ld.get("gtin13") or ld.get("gtin12") or ld.get("gtin") or ld.get("mpn", "")
            if gtin:
                candidate = _clean_upc(gtin)
                if candidate and _name_similarity(name, product_name) >= 0.4:
                    return candidate

        upc_match = re.search(r'"upc"\s*:\s*"(\d{10,14})"', product_html)
        if upc_match:
            candidate = _clean_upc(upc_match.group(1))
            if candidate:
                name_match = re.search(r'"name"\s*:\s*"([^"]{5,80})"', product_html)
                page_name = name_match.group(1) if name_match else ""
                if _name_similarity(name, page_name) >= 0.4:
                    return candidate

        time.sleep(0.5)

    return None


# ── Source 4: ReserveBar ──────────────────────────────────────────────────

def lookup_reservebar(name: str) -> str | None:
    """
    ReserveBar product pages include structured data with UPC codes.
    Good for premium and gift-tier bottles.
    """
    q = urllib.parse.quote_plus(name)
    html = _get(f"https://www.reservebar.com/search?q={q}")
    if not html:
        return None

    paths = re.findall(r'href="(/products/[^"?#]+)"', html)
    seen: set[str] = set()
    unique: list[str] = []
    for p in paths:
        if p not in seen and len(unique) < 3:
            seen.add(p)
            unique.append(p)

    for path in unique:
        product_html = _get(f"https://www.reservebar.com{path}")
        if not product_html:
            continue

        for ld in _extract_json_ld(product_html):
            product_name = ld.get("name", "")
            gtin = ld.get("gtin13") or ld.get("gtin12") or ld.get("gtin") or ""
            if gtin:
                candidate = _clean_upc(gtin)
                if candidate and _name_similarity(name, product_name) >= 0.4:
                    return candidate

        barcode_match = re.search(r'"barcode"\s*:\s*"(\d{10,14})"', product_html)
        if barcode_match:
            candidate = _clean_upc(barcode_match.group(1))
            if candidate:
                title_match = re.search(r'"title"\s*:\s*"([^"]{5,80})"', product_html)
                page_name = title_match.group(1) if title_match else ""
                if _name_similarity(name, page_name) >= 0.4:
                    return candidate

        time.sleep(0.5)

    return None


# ── Source 5: Open Food Facts ─────────────────────────────────────────────

def lookup_open_food_facts(name: str) -> str | None:
    q = urllib.parse.quote_plus(name)
    data = _get_json(
        f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={q}&json=1&page_size=5"
    )
    if not data:
        return None
    for product in data.get("products", []):
        product_name = product.get("product_name", "")
        code = product.get("code", "")
        if code and _name_similarity(name, product_name) >= 0.5:
            return _clean_upc(code)
    return None


# ── Chain all sources ─────────────────────────────────────────────────────

ALL_SOURCES = ["whiskybase", "whisky_exchange", "total_wine", "reservebar", "open_food_facts"]

SOURCE_FN = {
    "whiskybase":       lookup_whiskybase,
    "whisky_exchange":  lookup_whisky_exchange,
    "total_wine":       lookup_total_wine,
    "reservebar":       lookup_reservebar,
    "open_food_facts":  lookup_open_food_facts,
}

SOURCE_LABEL = {
    "whiskybase":       "Whiskybase",
    "whisky_exchange":  "WhiskyExchange",
    "total_wine":       "TotalWine",
    "reservebar":       "ReserveBar",
    "open_food_facts":  "OpenFoodFacts",
}


def lookup_all(name: str, only_source: str | None = None) -> tuple[str | None, str]:
    sources = only_source.split(",") if only_source else ALL_SOURCES
    for src in sources:
        fn = SOURCE_FN.get(src.strip())
        if not fn:
            print(f"  Unknown source '{src}' — skipping")
            continue
        try:
            upc = fn(name)
            if upc:
                return upc, SOURCE_LABEL[src.strip()]
        except Exception as e:
            print(f"  [{src}] error: {e}")
        time.sleep(0.3)
    return None, ""


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed UPC codes for whiskeys (all free sources)")
    parser.add_argument("--limit", type=int, default=None, help="Max whiskeys to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--source", default=None,
                        help=f"Comma-separated sources: {', '.join(ALL_SOURCES)}")
    parser.add_argument("--overwrite", action="store_true",
                        help="Re-process whiskeys that already have a UPC")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(models.Whiskey)
        if not args.overwrite:
            query = query.filter(
                (models.Whiskey.upc == None) | (models.Whiskey.upc == "")
            )
        if args.limit:
            query = query.limit(args.limit)

        whiskeys = query.all()
        print(f"Processing {len(whiskeys)} whiskeys...\n")
        print(f"Sources: {args.source or ', '.join(ALL_SOURCES)}\n")

        found = 0
        source_counts: dict[str, int] = {}

        for i, w in enumerate(whiskeys, 1):
            print(f"[{i}/{len(whiskeys)}] {w.name}", end=" ... ", flush=True)
            upc, source = lookup_all(w.name, args.source)

            if upc:
                print(f"FOUND ({source}): {upc}")
                source_counts[source] = source_counts.get(source, 0) + 1
                if not args.dry_run:
                    w.upc = upc
                    db.commit()
                found += 1
            else:
                print("not found")

        total = len(whiskeys)
        print(f"\n{'='*50}")
        print(f"Done. Found: {found}/{total}  ({100*found//max(total,1)}%)")
        if source_counts:
            print("By source: " + "  ".join(f"{s}={c}" for s, c in sorted(source_counts.items())))
        if args.dry_run:
            print("(Dry run — no changes saved)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
