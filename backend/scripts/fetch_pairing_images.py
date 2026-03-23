"""
Scrape high-quality food images for whiskey pairing items.

Uses Bing image search (no API key needed) to find and download
appetizing food photos, then resizes them to a consistent square format.

Usage:
    cd backend
    python -m scripts.fetch_pairing_images
    python -m scripts.fetch_pairing_images --force   # re-download all
    python -m scripts.fetch_pairing_images --size 400 # custom size
"""

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

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads" / "pairings"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Every unique food item from pairings.py → optimized search query
FOOD_ITEMS = {
    # ── Bourbon ──────────────────────────────────────────────────────────
    "Smoked BBQ Brisket": "smoked bbq brisket plated food photography",
    "Pecan Pie": "pecan pie slice food photography",
    "Aged Cheddar": "aged cheddar cheese wedge food photography",
    "Fried Chicken": "fried chicken crispy plated food photography",
    "Pulled Pork Sliders": "pulled pork sliders bbq food photography",
    "Gouda (Aged)": "aged gouda cheese wedge food photography",
    "Pimento Cheese": "pimento cheese spread crackers food photography",
    "Dark Chocolate": "dark chocolate pieces food photography",
    "Bread Pudding with Caramel Sauce": "bread pudding caramel sauce dessert food photography",
    "Bananas Foster": "bananas foster dessert flambee food photography",
    "Cornbread with Honey Butter": "cornbread honey butter food photography",
    "Glazed Bacon": "glazed bacon strips food photography",
    # ── Scotch ───────────────────────────────────────────────────────────
    "Smoked Salmon": "smoked salmon fillet plated food photography",
    "Haggis": "haggis neeps tatties scottish food photography",
    "Grilled Lamb": "grilled lamb chops plated food photography",
    "Stilton Blue Cheese": "stilton blue cheese wedge food photography",
    "Isle of Mull Cheddar": "scottish farmhouse cheddar cheese food photography",
    "Dark Chocolate with Sea Salt": "dark chocolate sea salt food photography",
    "Sticky Toffee Pudding": "sticky toffee pudding dessert food photography",
    "Cranachan": "cranachan scottish dessert raspberries oats cream food photography",
    "Smoked Oysters": "smoked oysters plated food photography",
    "Venison Steak": "venison steak plated food photography",
    "Sushi (Fatty Tuna)": "otoro fatty tuna sushi food photography",
    "Oatcakes with Honey": "scottish oatcakes honey food photography",
    # ── Irish ────────────────────────────────────────────────────────────
    "Soda Bread with Butter": "irish soda bread butter food photography",
    "Oysters": "fresh oysters half shell food photography",
    "Irish Stew": "irish stew lamb potatoes food photography",
    "Cashel Blue": "cashel blue cheese irish food photography",
    "Aged Coolea": "coolea cheese irish gouda food photography",
    "Apple Tart": "apple tart dessert food photography",
    "Bailey's Cheesecake": "baileys irish cream cheesecake food photography",
    "Smoked Mackerel": "smoked mackerel plated food photography",
    "Colcannon": "colcannon irish mashed potatoes food photography",
    "Honey-Glazed Carrots": "honey glazed roasted carrots food photography",
    "Brown Bread Ice Cream": "brown bread ice cream irish dessert food photography",
    # ── Japanese ─────────────────────────────────────────────────────────
    "Sashimi": "sashimi platter japanese food photography",
    "Wagyu Beef": "wagyu beef steak food photography",
    "Yakitori (Tare-glazed)": "yakitori tare glazed chicken skewers food photography",
    "Brie": "brie cheese wheel food photography",
    "Smoked Mozzarella": "smoked mozzarella cheese food photography",
    "Mochi": "japanese mochi dessert food photography",
    "Matcha Chocolate": "matcha green tea chocolate food photography",
    "Yuzu Tart": "yuzu citrus tart dessert food photography",
    "Dark Miso Soup": "dark miso soup bowl food photography",
    "Tempura (Shrimp)": "shrimp tempura japanese food photography",
    "Unagi (Grilled Eel)": "unagi grilled eel japanese food photography",
    "Pickled Ginger": "pickled ginger gari japanese food photography",
    # ── Rye ──────────────────────────────────────────────────────────────
    "Pastrami on Rye": "pastrami rye sandwich food photography",
    "Corned Beef Hash": "corned beef hash plated food photography",
    "Aged Gruyere": "gruyere cheese wedge food photography",
    "Manchego": "manchego cheese wedge food photography",
    "Charcuterie Board": "charcuterie board food photography",
    "Smoked Duck Breast": "smoked duck breast plated food photography",
    "Rye Bread with Caraway and Mustard": "rye bread caraway mustard food photography",
    "Gingerbread": "gingerbread cookies food photography",
    "Dark Chocolate with Chili": "dark chocolate chili spicy food photography",
    "Pear Tart with Cardamom": "pear tart cardamom dessert food photography",
    "Kimchi": "kimchi korean fermented food photography",
    "Reuben Sandwich": "reuben sandwich pastrami food photography",
    # ── Canadian ─────────────────────────────────────────────────────────
    "Maple Glazed Salmon": "maple glazed salmon plated food photography",
    "Poutine": "poutine fries gravy curds food photography",
    "Tourtiere": "tourtiere quebec meat pie food photography",
    "Smoked Gouda": "smoked gouda cheese food photography",
    "Oka Cheese": "oka cheese quebec food photography",
    "Apple Crumble": "apple crumble dessert food photography",
    "Butter Tarts": "butter tarts canadian dessert food photography",
    "Nanaimo Bars": "nanaimo bars canadian dessert food photography",
    "Peameal Bacon": "peameal bacon canadian food photography",
    "Cedar-Planked Whitefish": "cedar plank whitefish food photography",
    "Wild Blueberry Compote on Brie": "blueberry compote brie cheese food photography",
    "Montreal Smoked Meat": "montreal smoked meat sandwich food photography",
    # ── Wheat ────────────────────────────────────────────────────────────
    "Honeycomb": "honeycomb natural food photography",
    "Brioche French Toast": "brioche french toast maple syrup food photography",
    "Triple-Cream Brie": "triple cream brie cheese food photography",
    "Fresh Burrata": "burrata cheese honey food photography",
    "Creme Brulee": "creme brulee dessert food photography",
    "Lemon Panna Cotta": "lemon panna cotta dessert food photography",
    "Shortbread Cookies": "shortbread cookies food photography",
    "Prosciutto and Melon": "prosciutto melon appetizer food photography",
    "Lobster with Drawn Butter": "lobster drawn butter food photography",
    "Roasted Chicken with Herbs": "roasted chicken herbs food photography",
    "White Peach with Ricotta": "white peach ricotta dessert food photography",
    "Lavender Honey Scones": "lavender honey scones food photography",
    # ── Single Malt ──────────────────────────────────────────────────────
    "Roasted Nuts (Walnut & Almond)": "roasted walnuts almonds food photography",
    "Aged Comte": "comte cheese aged wedge food photography",
    "Roquefort": "roquefort blue cheese food photography",
    "Dark Chocolate Truffles": "dark chocolate truffles food photography",
    "Oat Flapjack with Honey": "oat flapjack honey food photography",
    "Pan-Seared Duck with Cherry Reduction": "pan seared duck cherry sauce food photography",
    "Beef Carpaccio": "beef carpaccio plated food photography",
    "Fig and Walnut Bread": "fig walnut bread food photography",
    # ── Default ──────────────────────────────────────────────────────────
    "Dark Chocolate (70%+ cacao)": "dark chocolate 70 percent cacao food photography",
    "Aged Cheese Board": "aged cheese board assortment food photography",
    "Roasted Nuts (Almonds & Pecans)": "mixed nuts almonds pecans food photography",
    "Charcuterie with Grainy Mustard": "charcuterie meat board grainy mustard food photography",
    "Dried Fruit (Apricots & Figs)": "dried apricots figs food photography",
    # ── Flavor Bonus ─────────────────────────────────────────────────────
    "Grilled Steak": "grilled steak plated food photography",
    "Smoked Almonds": "smoked almonds bowl food photography",
    "Bacon-Wrapped Dates": "bacon wrapped dates appetizer food photography",
    "Dark Chocolate with Smoked Salt": "dark chocolate smoked salt food photography",
    "Baklava": "baklava pastry dessert food photography",
    "Honeycomb with Aged Cheese": "honeycomb aged cheese platter food photography",
    "Glazed Ham": "glazed ham sliced food photography",
    "Caramel Flan": "caramel flan dessert food photography",
    "Candied Pecans": "candied pecans food photography",
    "Fresh Fruit & Cream": "fresh berries cream dessert food photography",
    "Baked Brie with Fig Jam": "baked brie fig jam food photography",
    "Duck a l'Orange": "duck a l orange plated food photography",
    "Ceviche": "ceviche fresh lime food photography",
    "Lemon Tart": "lemon tart dessert food photography",
    "Szechuan Peppercorn Dishes": "szechuan peppercorn dish food photography",
    "Jerk Chicken": "jerk chicken plated food photography",
    "Spiced Dark Chocolate": "spiced dark chocolate chili food photography",
    "Vanilla Bean Panna Cotta": "vanilla bean panna cotta dessert food photography",
    "Buttered Popcorn": "buttered popcorn food photography",
    "Salted Caramel Brownies": "salted caramel brownies food photography",
    "Toffee Apples": "toffee apples food photography",
    "Lavender Shortbread": "lavender shortbread cookies food photography",
    "Goat Cheese with Honey": "goat cheese honey food photography",
    "Rose-Scented Turkish Delight": "turkish delight rose food photography",
    "Roasted Hazelnuts": "roasted hazelnuts food photography",
    "Almond Biscotti": "almond biscotti food photography",
    "Nutella on Toast": "nutella toast food photography",
    "Lobster Bisque": "lobster bisque soup food photography",
    "Tiramisu": "tiramisu dessert food photography",
}


def slugify(name: str) -> str:
    """Convert food name to a filename-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def search_bing_images(query: str, max_results: int = 8) -> list[str]:
    """Scrape Bing image search results for image URLs."""
    search_url = "https://www.bing.com/images/search"
    params = {
        "q": query,
        "first": 1,
        "count": max_results,
        "qft": "+filterui:aspect-square+filterui:photo-photo",  # square photos only
    }

    try:
        resp = httpx.get(search_url, params=params, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []

    # Bing stores image metadata in 'm' attribute of <a> tags
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

    # Fallback: try to find image URLs in img tags
    if not urls:
        for img in soup.select("img.mimg"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and "bing" not in src:
                urls.append(src)

    return urls[:max_results]


def download_and_resize(url: str, output_path: Path, size: int = 300) -> bool:
    """Download image from URL, crop to square, resize, save as JPG."""
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True, headers=HEADERS)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return False

        img = Image.open(BytesIO(resp.content))
        img = img.convert("RGB")

        # Center-crop to square
        w, h = img.size
        if w < 50 or h < 50:  # skip tiny images
            return False

        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

        # Resize
        img = img.resize((size, size), Image.LANCZOS)

        # Save
        img.save(output_path, "JPEG", quality=85)
        return True

    except Exception as e:
        print(f"    Failed for {url[:80]}... — {e}")
        return False


def fetch_all(force: bool = False, size: int = 300):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    items = list(FOOD_ITEMS.items())
    print(f"Fetching images for {len(items)} food pairing items...")
    print(f"Output: {UPLOAD_DIR}")
    print(f"Size: {size}x{size}px | Force: {force}\n")

    success = 0
    skipped = 0
    failed = 0

    for name, query in tqdm(items, desc="Downloading"):
        slug = slugify(name)
        out_path = UPLOAD_DIR / f"{slug}.jpg"

        if out_path.exists() and not force:
            skipped += 1
            continue

        # Search for image URLs
        urls = search_bing_images(query, max_results=8)
        downloaded = False

        for url in urls:
            if download_and_resize(url, out_path, size):
                downloaded = True
                break

        if downloaded:
            success += 1
        else:
            print(f"  FAILED: {name} ({len(urls)} URLs tried)")
            failed += 1

        # Rate-limit to be respectful to Bing
        time.sleep(2.0)

    print(f"\nDone! {success} downloaded, {skipped} skipped, {failed} failed")
    print(f"Images saved to: {UPLOAD_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch food pairing images")
    parser.add_argument("--force", action="store_true", help="Re-download existing images")
    parser.add_argument("--size", type=int, default=300, help="Output image size (square, default 300)")
    args = parser.parse_args()

    fetch_all(force=args.force, size=args.size)
