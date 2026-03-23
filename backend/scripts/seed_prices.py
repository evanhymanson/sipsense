"""
Seed missing price data into the whiskeys table.

Strategy:
  1. Hardcoded MSRP for ~150 well-known bottles (real retail prices in USD)
  2. Formula-based estimation for bottles with no price (category + age)
  3. Never overwrites existing non-null prices

Usage:
    cd backend
    python -m scripts.seed_prices [--dry-run]
"""

import argparse
import random
import sys

sys.path.insert(0, ".")

# ── Known MSRPs (USD, approximate retail) ─────────────────────────────────────

KNOWN_PRICES = {
    # Bourbon — allocated / premium
    "pappy van winkle 23":               2499.99,
    "pappy van winkle 20":               1299.99,
    "pappy van winkle 15":               799.99,
    "william larue weller":              149.99,
    "george t. stagg":                   139.99,
    "george t stagg":                    139.99,
    "eagle rare 17":                     149.99,
    "colonel e.h. taylor barrel proof":  79.99,
    "michter's 25 year":                 799.99,
    "michter's 20 year":                 499.99,
    "michter's 10 year bourbon":         169.99,
    "booker's bourbon":                  99.99,
    "blanton's straight from the barrel": 189.99,
    "old forester birthday bourbon":     99.99,
    "larceny barrel proof":              59.99,
    "elijah craig barrel proof":         59.99,
    "knob creek 18":                     129.99,
    # Bourbon — standard
    "buffalo trace":                     30.99,
    "maker's mark":                      32.99,
    "maker's mark 46":                   45.99,
    "woodford reserve":                  39.99,
    "woodford reserve double oaked":     54.99,
    "four roses single barrel":          54.99,
    "four roses small batch":            39.99,
    "four roses small batch select":     59.99,
    "four roses yellow label":           29.99,
    "blanton's original":                64.99,
    "knob creek 9 year":                 39.99,
    "knob creek 12 year":                54.99,
    "wild turkey 101":                   24.99,
    "wild turkey 81":                    22.99,
    "wild turkey rare breed":            59.99,
    "bulleit bourbon":                   34.99,
    "bulleit 10 year":                   49.99,
    "angel's envy":                      49.99,
    "angel's envy port finish":          49.99,
    "weller special reserve":            24.99,
    "weller antique 107":                29.99,
    "weller 12 year":                    29.99,
    "old forester 1920":                 54.99,
    "old forester 1910":                 44.99,
    "old forester 1897":                 44.99,
    "old forester 86":                   24.99,
    "eagle rare 10":                     34.99,
    "elijah craig small batch":          34.99,
    "elijah craig 18":                   124.99,
    "henry mckenna 10 year":             39.99,
    "old grand-dad 114":                 29.99,
    "michter's small batch bourbon":     44.99,
    "jim beam white":                    19.99,
    "jim beam black":                    24.99,
    "evan williams black":               17.99,
    "evan williams bottled in bond":     22.99,
    "1792 small batch":                  34.99,
    "1792 full proof":                   44.99,
    "heaven hill bottled in bond":       29.99,
    # Scotch — Islay
    "ardbeg 10":                         54.99,
    "ardbeg uigeadail":                  79.99,
    "ardbeg corryvreckan":               89.99,
    "ardbeg an oa":                      54.99,
    "laphroaig 10":                      49.99,
    "laphroaig quarter cask":            54.99,
    "laphroaig triple wood":             64.99,
    "laphroaig lore":                    109.99,
    "laphroaig 15":                      99.99,
    "laphroaig 18":                      159.99,
    "lagavulin 8":                       59.99,
    "lagavulin 16":                      89.99,
    "lagavulin 12":                      149.99,
    "bowmore 12":                        44.99,
    "bowmore 15":                        59.99,
    "bowmore 18":                        89.99,
    "caol ila 12":                       54.99,
    "kilchoman machir bay":              54.99,
    "bruichladdich classic laddie":      44.99,
    "port charlotte 10":                 59.99,
    "octomore":                          229.99,
    # Scotch — Speyside
    "glenfiddich 12":                    44.99,
    "glenfiddich 15":                    59.99,
    "glenfiddich 18":                    89.99,
    "glenfiddich 21":                    179.99,
    "glenlivet 12":                      39.99,
    "glenlivet 15":                      54.99,
    "glenlivet 18":                      79.99,
    "macallan 12 double cask":           69.99,
    "macallan 12 sherry oak":            74.99,
    "macallan 15 double cask":           119.99,
    "macallan 18 sherry oak":            249.99,
    "macallan 18 double cask":           229.99,
    "macallan 25":                       1299.99,
    "balvenie 12 doublewood":            59.99,
    "balvenie 14 caribbean cask":        74.99,
    "balvenie 17 doublewood":            149.99,
    "balvenie 21 portwood":              299.99,
    "aberlour 12":                       44.99,
    "aberlour 16":                       89.99,
    "aberlour a'bunadh":                 79.99,
    "glenfarclas 105":                   64.99,
    "glenfarclas 12":                    49.99,
    "glenfarclas 15":                    69.99,
    "glenfarclas 25":                    249.99,
    "benriach 12":                       44.99,
    "glenallachie 12":                   59.99,
    # Scotch — Highland / Other
    "highland park 12":                  49.99,
    "highland park 18":                  109.99,
    "highland park 25":                  499.99,
    "dalmore 12":                        59.99,
    "dalmore 15":                        89.99,
    "dalmore 18":                        149.99,
    "glenmorangie 10":                   44.99,
    "glenmorangie 12":                   54.99,
    "glenmorangie 18":                   99.99,
    "talisker 10":                       59.99,
    "talisker 18":                       119.99,
    "talisker storm":                    59.99,
    "oban 14":                           64.99,
    "oban 18":                           149.99,
    "springbank 10":                     69.99,
    "springbank 15":                     119.99,
    "springbank 21":                     349.99,
    "glendronach 12":                    54.99,
    "glendronach 15":                    79.99,
    "glendronach 18":                    119.99,
    "monkey shoulder":                   34.99,
    # Irish
    "redbreast 12":                      69.99,
    "redbreast 15":                      99.99,
    "redbreast 21":                      249.99,
    "redbreast 27":                      999.99,
    "green spot":                        49.99,
    "yellow spot":                       79.99,
    "jameson":                           29.99,
    "jameson black barrel":              39.99,
    "jameson caskmates":                 34.99,
    "powers john's lane":                59.99,
    "teeling single malt":              49.99,
    "teeling single grain":              39.99,
    "bushmills 12":                      44.99,
    "bushmills 21":                      149.99,
    # Japanese (updated 2025 — post-Suntory April 2024 price hike)
    "yamazaki 12":                       185.00,
    "yamazaki 18":                       750.00,
    "hakushu 12":                        175.00,
    "hakushu 18":                        650.00,
    "hibiki 21":                         1200.00,
    "hibiki harmony":                    80.00,
    "nikka from the barrel":             70.00,
    "nikka coffey grain":                70.00,
    "nikka coffey malt":                 75.00,
    "suntory toki":                      40.00,
    "yoichi 10":                         150.00,
    # Rye
    "michter's rye":                     44.99,
    "rittenhouse 100":                   29.99,
    "bulleit rye":                       34.99,
    "knob creek rye":                    34.99,
    "pikesville rye":                    49.99,
    "sazerac rye":                       29.99,
    "whistlepig 10":                     79.99,
    "whistlepig 12":                     119.99,
    "whistlepig 15":                     199.99,
    "high west double rye":              44.99,
    "high west rendezvous rye":          64.99,
    "colonel e.h. taylor rye":           54.99,
    "wild turkey rye":                   24.99,
}

# Base price ranges by category (min, typical, max for formula)
CATEGORY_PRICE = {
    "bourbon":     (22, 38, 80),
    "scotch":      (38, 60, 120),
    "irish":       (28, 42, 80),
    "japanese":    (55, 90, 200),
    "rye":         (22, 36, 75),
    "canadian":    (18, 28, 55),
    "blended":     (28, 40, 80),
    "single malt": (40, 65, 130),
}

# Age multipliers applied on top of base
AGE_MULTIPLIERS = [
    (25, 4.5),
    (21, 3.2),
    (18, 2.2),
    (15, 1.6),
    (12, 1.25),
    (10, 1.05),
    (0,  1.0),
]


def estimate_price(w, rng: random.Random) -> float:
    low, mid, _ = CATEGORY_PRICE.get(w.category or "", (30, 50, 100))
    base = rng.uniform(low, mid)

    age = w.age or 0
    for threshold, mult in AGE_MULTIPLIERS:
        if age >= threshold:
            base *= mult
            break

    # Add noise ±15%
    base *= rng.uniform(0.88, 1.15)
    return round(base, 2)


def find_known(name: str) -> float | None:
    name_lower = name.lower().strip()
    for key, price in KNOWN_PRICES.items():
        if key in name_lower or name_lower.startswith(key):
            return price
    return None


def run(dry_run: bool):
    from app.database import SessionLocal
    from app import models

    rng = random.Random(99)
    db = SessionLocal()

    known_matched = 0
    estimated = 0
    skipped = 0

    try:
        whiskeys = db.query(models.Whiskey).all()

        for w in whiskeys:
            if w.price_usd and w.price_usd > 0:
                skipped += 1
                continue

            price = find_known(w.name)
            if price:
                known_matched += 1
            else:
                price = estimate_price(w, rng)
                estimated += 1

            if not dry_run:
                w.price_usd = price

        if not dry_run:
            db.commit()

    finally:
        db.close()

    print("=" * 50)
    print(f"  Known bottles matched : {known_matched}")
    print(f"  Formula estimated     : {estimated}")
    print(f"  Already had prices    : {skipped}")
    if dry_run:
        print("  (DRY RUN — no changes written)")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)