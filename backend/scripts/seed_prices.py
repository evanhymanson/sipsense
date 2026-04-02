"""
Seed missing price data into the whiskeys table.

Strategy:
  1. Hardcoded prices for ~170 well-known bottles (real retail or secondary market)
  2. Formula-based estimation for bottles with no price (category + age)
  3. Never overwrites existing non-null prices

Pricing philosophy:
  - Available bottles → current US retail MSRP
  - Allocated/hard-to-find → secondary market price
  - Discontinued/collector → auction/collector market value

Usage:
    cd backend
    python -m scripts.seed_prices [--dry-run]
"""

import argparse
import random
import sys

sys.path.insert(0, ".")

# ── Known prices (USD) ──────────────────────────────────────────────────────────

KNOWN_PRICES = {
    # Bourbon — allocated / premium (secondary market prices)
    "pappy van winkle 23":               2800.00,
    "pappy van winkle 20":               1800.00,
    "pappy van winkle 15":               1200.00,
    "william larue weller":              1500.00,
    "george t. stagg":                   1800.00,
    "george t stagg":                    1800.00,
    "eagle rare 17":                     400.00,
    "colonel e.h. taylor barrel proof":  200.00,
    "michter's 25 year":                 1500.00,
    "michter's 20 year":                 800.00,
    "michter's 10 year bourbon":         170.00,
    "booker's bourbon":                  100.00,
    "blanton's straight from the barrel": 250.00,
    "old forester birthday bourbon":     200.00,
    "larceny barrel proof":              60.00,
    "elijah craig barrel proof":         75.00,
    "knob creek 18":                     130.00,
    # Bourbon — standard (current US retail)
    "buffalo trace":                     28.00,
    "maker's mark":                      32.00,
    "maker's mark 46":                   40.00,
    "woodford reserve":                  40.00,
    "woodford reserve double oaked":     60.00,
    "four roses single barrel":          50.00,
    "four roses small batch":            35.00,
    "four roses small batch select":     60.00,
    "four roses yellow label":           30.00,
    "blanton's original":                100.00,
    "knob creek 9 year":                 36.00,
    "knob creek 12 year":                65.00,
    "wild turkey 101":                   28.00,
    "wild turkey 81":                    23.00,
    "wild turkey rare breed":            48.00,
    "bulleit bourbon":                   30.00,
    "bulleit 10 year":                   50.00,
    "angel's envy":                      55.00,
    "angel's envy port finish":          55.00,
    "weller special reserve":            40.00,
    "weller antique 107":                100.00,
    "weller 12 year":                    150.00,
    "weller full proof":                 400.00,
    "stagg jr":                          200.00,
    "old forester 1920":                 60.00,
    "old forester 1910":                 45.00,
    "old forester 1897":                 45.00,
    "old forester 86":                   25.00,
    "eagle rare 10":                     45.00,
    "elijah craig small batch":          32.00,
    "elijah craig 18":                   125.00,
    "henry mckenna 10 year":             40.00,
    "old grand-dad 114":                 30.00,
    "michter's small batch bourbon":     47.00,
    "jim beam white":                    18.00,
    "jim beam black":                    25.00,
    "evan williams black":               18.00,
    "evan williams bottled in bond":     23.00,
    "1792 small batch":                  35.00,
    "1792 full proof":                   45.00,
    "heaven hill bottled in bond":       30.00,
    # Scotch — Islay
    "ardbeg 10":                         55.00,
    "ardbeg uigeadail":                  80.00,
    "ardbeg corryvreckan":               90.00,
    "ardbeg an oa":                      55.00,
    "laphroaig 10":                      50.00,
    "laphroaig quarter cask":            60.00,
    "laphroaig triple wood":             65.00,
    "laphroaig lore":                    110.00,
    "laphroaig 15":                      100.00,
    "laphroaig 18":                      160.00,
    "lagavulin 8":                       65.00,
    "lagavulin 16":                      90.00,
    "lagavulin 12":                      150.00,
    "bowmore 12":                        45.00,
    "bowmore 15":                        60.00,
    "bowmore 18":                        90.00,
    "caol ila 12":                       60.00,
    "kilchoman machir bay":              55.00,
    "bruichladdich classic laddie":      50.00,
    "port charlotte 10":                 60.00,
    "octomore":                          230.00,
    # Scotch — Speyside
    "glenfiddich 12":                    55.00,
    "glenfiddich 15":                    60.00,
    "glenfiddich 18":                    85.00,
    "glenfiddich 21":                    210.00,
    "glenlivet 12":                      50.00,
    "glenlivet 15":                      55.00,
    "glenlivet 18":                      100.00,
    "macallan 12 double cask":           65.00,
    "macallan 12 sherry oak":            95.00,
    "macallan 15 double cask":           120.00,
    "macallan 18 sherry oak":            420.00,
    "macallan 18 double cask":           370.00,
    "macallan 25":                       2500.00,
    "balvenie 12 doublewood":            66.00,
    "balvenie 14 caribbean cask":        85.00,
    "balvenie 17 doublewood":            150.00,
    "balvenie 21 portwood":              335.00,
    "aberlour 12":                       50.00,
    "aberlour 16":                       90.00,
    "aberlour a'bunadh":                 90.00,
    "glenfarclas 105":                   65.00,
    "glenfarclas 12":                    50.00,
    "glenfarclas 15":                    70.00,
    "glenfarclas 25":                    250.00,
    "benriach 12":                       45.00,
    "glenallachie 12":                   60.00,
    # Scotch — Highland / Other
    "highland park 12":                  55.00,
    "highland park 18":                  170.00,
    "highland park 25":                  500.00,
    "dalmore 12":                        73.00,
    "dalmore 15":                        145.00,
    "dalmore 18":                        360.00,
    "glenmorangie 10":                   45.00,
    "glenmorangie 12":                   55.00,
    "glenmorangie 18":                   100.00,
    "talisker 10":                       75.00,
    "talisker 18":                       140.00,
    "talisker storm":                    60.00,
    "oban 14":                           90.00,
    "oban 18":                           170.00,
    "springbank 10":                     140.00,
    "springbank 15":                     300.00,
    "springbank 21":                     600.00,
    "glendronach 12":                    55.00,
    "glendronach 15":                    80.00,
    "glendronach 18":                    150.00,
    "monkey shoulder":                   33.00,
    # Blended Scotch
    "johnnie walker blue label":         200.00,
    "johnnie walker black label":        35.00,
    "johnnie walker green label":        55.00,
    "chivas regal 12":                   30.00,
    "chivas regal 18":                   70.00,
    "dewar's 12":                        28.00,
    "dewar's 18":                        55.00,
    "famous grouse":                     22.00,
    "royal salute 21":                   200.00,
    # Irish
    "redbreast 12":                      70.00,
    "redbreast 15":                      130.00,
    "redbreast 21":                      250.00,
    "redbreast 27":                      1000.00,
    "green spot":                        60.00,
    "yellow spot":                       125.00,
    "jameson":                           32.00,
    "jameson black barrel":              40.00,
    "jameson caskmates":                 35.00,
    "powers john's lane":                60.00,
    "teeling single malt":              50.00,
    "teeling single grain":              40.00,
    "bushmills 12":                      45.00,
    "bushmills 21":                      150.00,
    # Japanese (updated 2026 — post-Suntory April 2024 price hike)
    "yamazaki 12":                       190.00,
    "yamazaki 18":                       900.00,
    "hakushu 12":                        195.00,
    "hakushu 18":                        800.00,
    "hibiki 21":                         1000.00,
    "hibiki harmony":                    80.00,
    "nikka from the barrel":             70.00,
    "nikka coffey grain":                70.00,
    "nikka coffey malt":                 75.00,
    "suntory toki":                      35.00,
    "yoichi 10":                         150.00,
    # Rye
    "michter's rye":                     47.00,
    "rittenhouse 100":                   30.00,
    "bulleit rye":                       30.00,
    "knob creek rye":                    35.00,
    "pikesville rye":                    50.00,
    "sazerac rye":                       30.00,
    "whistlepig 10":                     80.00,
    "whistlepig 12":                     140.00,
    "whistlepig 15":                     200.00,
    "high west double rye":              45.00,
    "high west rendezvous rye":          65.00,
    "colonel e.h. taylor rye":           100.00,
    "wild turkey rye":                   25.00,
    # Canadian
    "crown royal":                       28.00,
    "canadian club":                     14.00,
    "lot no. 40":                        35.00,
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
