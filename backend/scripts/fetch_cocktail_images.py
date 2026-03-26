"""
Scrape high-quality cocktail images for whiskey cocktail suggestion cards.

Uses Bing image search to find beautiful cocktail photos,
then resizes them to a consistent square format.

Usage:
    cd backend
    python -m scripts.fetch_cocktail_images
    python -m scripts.fetch_cocktail_images --force   # re-download all
    python -m scripts.fetch_cocktail_images --size 400 # custom size
"""

import os
import sys
import argparse
import json
import re
import time
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from tqdm import tqdm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.storage import upload_bytes, list_files

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Every unique cocktail from pairings.py → optimized search query
COCKTAIL_ITEMS = {
    # ── Bourbon ──────────────────────────────────────────────────────────
    "Old Fashioned": "old fashioned cocktail bourbon drink photography",
    "Mint Julep": "mint julep bourbon cocktail drink photography",
    "Whiskey Sour": "whiskey sour cocktail drink photography",
    "Kentucky Mule": "kentucky mule bourbon ginger beer cocktail photography",
    "Brown Derby": "brown derby cocktail grapefruit bourbon photography",
    "Paper Plane": "paper plane cocktail aperol amaro photography",
    "Gold Rush": "gold rush cocktail honey bourbon photography",
    "Bourbon Smash": "bourbon smash cocktail mint lemon photography",
    "Hot Toddy": "hot toddy whiskey cocktail warm drink photography",
    "New York Sour": "new york sour cocktail red wine float photography",
    # ── Scotch ───────────────────────────────────────────────────────────
    "Rob Roy": "rob roy scotch cocktail drink photography",
    "Penicillin": "penicillin cocktail scotch drink photography",
    "Blood & Sand": "blood and sand cocktail drink photography",
    "Rusty Nail": "rusty nail scotch drambuie cocktail photography",
    "Bobby Burns": "bobby burns scotch cocktail benedictine photography",
    "Scotch Highball": "scotch highball cocktail soda water photography",
    "Godfather": "godfather cocktail scotch amaretto photography",
    "Morning Glory Fizz": "morning glory fizz cocktail scotch egg white photography",
    # ── Irish ────────────────────────────────────────────────────────────
    "Irish Coffee": "irish coffee cocktail whipped cream photography",
    "Tipperary": "tipperary cocktail green chartreuse drink photography",
    "Irish Maid": "irish maid cocktail elderflower cucumber photography",
    "Emerald": "emerald cocktail irish whiskey vermouth photography",
    "Irish Buck": "irish buck cocktail ginger ale whiskey photography",
    "Blackthorn": "blackthorn cocktail irish whiskey vermouth photography",
    "Celtic Smash": "celtic smash cocktail irish whiskey mint photography",
    "Paddy Cocktail": "paddy cocktail irish whiskey drink photography",
    # ── Japanese ─────────────────────────────────────────────────────────
    "Japanese Highball": "japanese whisky highball cocktail drink photography",
    "Mizuwari": "mizuwari japanese whisky water cocktail photography",
    "Whisky Sour Tokyo Style": "japanese whisky sour cocktail cherry blossom photography",
    "Oyuwari": "oyuwari japanese whisky hot water serve photography",
    "Japanese Cocktail": "japanese cocktail orgeat whisky photography",
    "Bamboo": "bamboo cocktail vermouth whisky photography",
    "Sakura Spritz": "sakura spritz cocktail cherry blossom pink photography",
    "Umami Old Fashioned": "umami old fashioned cocktail japanese whisky shiso photography",
    # ── Rye ──────────────────────────────────────────────────────────────
    "Manhattan": "manhattan cocktail rye whiskey cherry photography",
    "Sazerac": "sazerac cocktail rye drink photography",
    "Boulevardier": "boulevardier cocktail campari drink photography",
    "Vieux Carre": "vieux carre cocktail new orleans rye cognac photography",
    "Toronto": "toronto cocktail fernet branca rye photography",
    "De La Louisiane": "de la louisiane cocktail rye benedictine photography",
    "Algonquin": "algonquin cocktail rye pineapple photography",
    "Rye Witch": "rye witch cocktail strega herbal photography",
    # ── Canadian ─────────────────────────────────────────────────────────
    "Canadian Cocktail": "canadian cocktail whisky cointreau drink photography",
    "Whisky Ginger": "whisky ginger ale cocktail drink photography",
    "Canadian Old Fashioned": "canadian old fashioned maple syrup cocktail photography",
    "Caribou": "caribou cocktail quebec whisky red wine photography",
    "Canadian Sour": "canadian sour cocktail maple whisky photography",
    "Norseman": "norseman cocktail whisky vermouth photography",
    "Calgary Red Eye": "calgary red eye cocktail tomato whisky beer photography",
    "Nor'Easter": "nor easter cocktail ginger beer maple whisky photography",
    # ── Wheat ────────────────────────────────────────────────────────────
    "Wheat Old Fashioned": "wheat whiskey old fashioned honey cocktail photography",
    "Honeyed Sour": "honey lavender whiskey sour cocktail photography",
    "Wheat Smash": "whiskey basil smash cocktail photography",
    "Amber Harvest": "apple cider whiskey cocktail autumn photography",
    "Gentle Manhattan": "manhattan cocktail wheat whiskey photography",
    "Golden Mile": "aperol whiskey cocktail thyme photography",
    "Bread Basket": "frangelico cream whiskey cocktail photography",
    "Prairie Fizz": "whiskey sparkling wine fizz cocktail photography",
    # ── Single Malt ──────────────────────────────────────────────────────
    "Single Malt Highball": "single malt scotch highball cocktail photography",
    "Smoky Cokey": "scotch and cola peated whisky cocktail photography",
    "Scotch Sour": "scotch sour cocktail honey lemon photography",
    "Affinity": "affinity cocktail scotch vermouth photography",
    "Laphroaig Project": "peated scotch last word cocktail chartreuse photography",
}


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def search_bing_images(query: str, max_results: int = 8) -> list[str]:
    search_url = "https://www.bing.com/images/search"
    params = {
        "q": query,
        "first": 1,
        "count": max_results,
        "qft": "+filterui:photo-photo",
    }

    try:
        resp = httpx.get(search_url, params=params, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []

    for a_tag in soup.select("a.iusc"):
        m = a_tag.get("m")
        if not m:
            continue
        try:
            data = json.loads(m)
            media_url = data.get("murl")
            if media_url and media_url.startswith("http"):
                urls.append(media_url)
        except (json.JSONDecodeError, KeyError):
            continue

    if not urls:
        for img in soup.select("img.mimg"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and "bing" not in src:
                urls.append(src)

    return urls[:max_results]


def download_and_resize(url: str, s3_key: str, size: int = 300) -> bool:
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers=HEADERS)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return False

        img = Image.open(BytesIO(resp.content))
        img = img.convert("RGB")

        w, h = img.size
        if w < 50 or h < 50:
            return False

        # Center-crop to square
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        img = img.resize((size, size), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, "JPEG", quality=85)
        upload_bytes(buf.getvalue(), s3_key, content_type="image/jpeg")
        return True

    except Exception as e:
        print(f"    Failed for {url[:80]}... — {e}")
        return False


def fetch_all(force: bool = False, size: int = 300):
    existing = list_files("cocktails") if not force else set()

    items = list(COCKTAIL_ITEMS.items())
    print(f"Fetching images for {len(items)} cocktail items...")
    print(f"Output: S3 cocktails/")
    print(f"Size: {size}x{size}px | Force: {force}\n")

    success = 0
    skipped = 0
    failed = 0

    for name, query in tqdm(items, desc="Downloading"):
        slug = slugify(name)
        filename = f"{slug}.jpg"

        if filename in existing:
            skipped += 1
            continue

        urls = search_bing_images(query, max_results=8)
        downloaded = False

        for url in urls:
            if download_and_resize(url, f"cocktails/{filename}", size):
                downloaded = True
                break

        if downloaded:
            success += 1
        else:
            print(f"  FAILED: {name} ({len(urls)} URLs tried)")
            failed += 1

        time.sleep(2.0)

    print(f"\nDone! {success} downloaded, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch cocktail images")
    parser.add_argument("--force", action="store_true", help="Re-download existing images")
    parser.add_argument("--size", type=int, default=300, help="Output image size (square, default 300)")
    args = parser.parse_args()

    fetch_all(force=args.force, size=args.size)
