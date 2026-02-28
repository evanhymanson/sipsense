"""
Run once to populate the database with whiskey data.
  cd backend
  python seed_data.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

WHISKEYS = [
    # ── Bourbon ───────────────────────────────────────────────────────────
    {"name": "Buffalo Trace", "distillery": "Buffalo Trace Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 45.0, "price_usd": 30.0,
     "description": "A classic Kentucky straight bourbon with a mash bill of corn, rye, and malted barley.",
     "flavor_profile": "vanilla, caramel, sweet, oak, spicy"},
    {"name": "Maker's Mark", "distillery": "Maker's Mark Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 45.0, "price_usd": 32.0,
     "description": "Wheated bourbon known for its smooth, approachable sweetness.",
     "flavor_profile": "vanilla, honey, caramel, sweet, fruity"},
    {"name": "Woodford Reserve", "distillery": "Woodford Reserve Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 45.2, "price_usd": 40.0,
     "description": "Small-batch bourbon triple distilled in pot stills.",
     "flavor_profile": "chocolate, caramel, spicy, oak, citrus, grain"},
    {"name": "Four Roses Single Barrel", "distillery": "Four Roses Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 50.0, "price_usd": 55.0,
     "description": "Single barrel expression with a high-rye mash bill delivering bold spice.",
     "flavor_profile": "spicy, fruity, caramel, vanilla, herbal"},
    {"name": "Blanton's Original", "distillery": "Buffalo Trace Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 46.5, "price_usd": 65.0,
     "description": "The original single barrel bourbon, bottled one barrel at a time.",
     "flavor_profile": "citrus, honey, vanilla, oak, spicy"},
    {"name": "Pappy Van Winkle 15 Year", "distillery": "Buffalo Trace Distillery", "category": "bourbon",
     "region": "Kentucky", "age": 15, "abv": 53.5, "price_usd": 900.0,
     "description": "Legendary wheated bourbon aged 15 years. Extremely rare.",
     "flavor_profile": "vanilla, caramel, honey, oak, sweet, nutty"},
    {"name": "Wild Turkey 101", "distillery": "Wild Turkey Distillery", "category": "bourbon",
     "region": "Kentucky", "age": None, "abv": 50.5, "price_usd": 28.0,
     "description": "High-proof, high-rye bourbon that punches above its price.",
     "flavor_profile": "spicy, caramel, vanilla, oak, grain"},
    # ── Rye ──────────────────────────────────────────────────────────────
    {"name": "Rittenhouse Rye", "distillery": "Heaven Hill Distilleries", "category": "rye",
     "region": "Kentucky", "age": None, "abv": 50.0, "price_usd": 27.0,
     "description": "Bottled-in-bond straight rye, a bartender's staple.",
     "flavor_profile": "spicy, herbal, grain, caramel, oak"},
    {"name": "Sazerac Rye 6 Year", "distillery": "Buffalo Trace Distillery", "category": "rye",
     "region": "Kentucky", "age": 6, "abv": 45.0, "price_usd": 32.0,
     "description": "Named for the classic New Orleans cocktail. Light, floral, spicy.",
     "flavor_profile": "spicy, floral, herbal, vanilla, grain"},
    {"name": "WhistlePig 10 Year", "distillery": "WhistlePig Farm", "category": "rye",
     "region": "Vermont", "age": 10, "abv": 50.0, "price_usd": 80.0,
     "description": "100% rye mash bill aged 10 years on a Vermont farm.",
     "flavor_profile": "spicy, fruity, oak, caramel, leather"},
    # ── Scotch – Speyside ─────────────────────────────────────────────────
    {"name": "Glenfiddich 12 Year", "distillery": "Glenfiddich", "category": "scotch",
     "region": "Speyside", "age": 12, "abv": 40.0, "price_usd": 45.0,
     "description": "The world's best-selling single malt. Light, fruity, and approachable.",
     "flavor_profile": "fruity, floral, honey, vanilla, oak"},
    {"name": "The Macallan 12 Year Sherry Oak", "distillery": "The Macallan", "category": "scotch",
     "region": "Speyside", "age": 12, "abv": 40.0, "price_usd": 70.0,
     "description": "Matured exclusively in hand-picked sherry oak casks from Jerez.",
     "flavor_profile": "fruity, chocolate, caramel, spicy, oak, sweet"},
    {"name": "Balvenie DoubleWood 12 Year", "distillery": "The Balvenie", "category": "scotch",
     "region": "Speyside", "age": 12, "abv": 40.0, "price_usd": 60.0,
     "description": "Matured in traditional oak casks then finished in first-fill sherry casks.",
     "flavor_profile": "honey, vanilla, nutty, spicy, oak, sweet"},
    # ── Scotch – Islay ────────────────────────────────────────────────────
    {"name": "Laphroaig 10 Year", "distillery": "Laphroaig Distillery", "category": "scotch",
     "region": "Islay", "age": 10, "abv": 43.0, "price_usd": 55.0,
     "description": "Intensely peated and medicinal. Love it or hate it.",
     "flavor_profile": "smoky, peaty, salty, oak, herbal"},
    {"name": "Ardbeg 10 Year", "distillery": "Ardbeg Distillery", "category": "scotch",
     "region": "Islay", "age": 10, "abv": 46.0, "price_usd": 60.0,
     "description": "Heavy peat smoke with a surprising sweetness underneath.",
     "flavor_profile": "smoky, peaty, citrus, vanilla, salty, spicy"},
    {"name": "Lagavulin 16 Year", "distillery": "Lagavulin Distillery", "category": "scotch",
     "region": "Islay", "age": 16, "abv": 43.0, "price_usd": 90.0,
     "description": "Deep, complex, and magnificently peated. A benchmark Islay.",
     "flavor_profile": "smoky, peaty, sweet, oak, leather, herbal"},
    # ── Scotch – Highlands ────────────────────────────────────────────────
    {"name": "Glenmorangie Original 10 Year", "distillery": "Glenmorangie", "category": "scotch",
     "region": "Highlands", "age": 10, "abv": 40.0, "price_usd": 40.0,
     "description": "Light, floral, and honeyed. Matured in ex-bourbon casks.",
     "flavor_profile": "honey, floral, vanilla, citrus, fruity"},
    {"name": "Dalmore 12 Year", "distillery": "The Dalmore", "category": "scotch",
     "region": "Highlands", "age": 12, "abv": 40.0, "price_usd": 55.0,
     "description": "Rich and fruity Highland single malt with sherry and bourbon cask influence.",
     "flavor_profile": "citrus, chocolate, caramel, oak, sweet, fruity"},
    # ── Irish ─────────────────────────────────────────────────────────────
    {"name": "Jameson Irish Whiskey", "distillery": "Midleton Distillery", "category": "irish",
     "region": "County Cork", "age": None, "abv": 40.0, "price_usd": 30.0,
     "description": "Triple-distilled blended Irish whiskey. Smooth and accessible.",
     "flavor_profile": "sweet, grain, floral, vanilla, honey"},
    {"name": "Redbreast 12 Year", "distillery": "Midleton Distillery", "category": "irish",
     "region": "County Cork", "age": 12, "abv": 40.0, "price_usd": 65.0,
     "description": "Single pot still Irish whiskey. Rich, complex, and spicy.",
     "flavor_profile": "fruity, spicy, caramel, oak, nutty, sweet"},
    {"name": "Green Spot", "distillery": "Midleton Distillery", "category": "irish",
     "region": "County Cork", "age": None, "abv": 40.0, "price_usd": 55.0,
     "description": "Single pot still Irish whiskey with a bright, fruity, and spicy character.",
     "flavor_profile": "fruity, spicy, herbal, honey, grain"},
    # ── Japanese ─────────────────────────────────────────────────────────
    {"name": "Suntory Toki", "distillery": "Suntory", "category": "japanese",
     "region": "Japan", "age": None, "abv": 43.0, "price_usd": 40.0,
     "description": "Blended Japanese whisky designed for highballs. Delicate and refreshing.",
     "flavor_profile": "floral, honey, vanilla, grain, citrus"},
    {"name": "Nikka From The Barrel", "distillery": "Nikka", "category": "japanese",
     "region": "Japan", "age": None, "abv": 51.4, "price_usd": 60.0,
     "description": "A blended whisky of remarkable depth and complexity at high proof.",
     "flavor_profile": "sweet, spicy, vanilla, caramel, oak, chocolate"},
    {"name": "Hibiki Japanese Harmony", "distillery": "Suntory", "category": "japanese",
     "region": "Japan", "age": None, "abv": 43.0, "price_usd": 85.0,
     "description": "Suntory's flagship blended Japanese whisky. Floral and honey-sweet.",
     "flavor_profile": "floral, honey, caramel, fruity, oak, vanilla"},
    {"name": "Yamazaki 12 Year", "distillery": "Suntory", "category": "japanese",
     "region": "Japan", "age": 12, "abv": 43.0, "price_usd": 160.0,
     "description": "Japan's first single malt. Delicate, fruity, and elegant.",
     "flavor_profile": "fruity, floral, honey, vanilla, oak, sweet"},
]


def seed():
    db = SessionLocal()
    existing = db.query(models.Whiskey).count()
    if existing > 0:
        print(f"Database already has {existing} whiskeys. Skipping seed.")
        db.close()
        return
    for data in WHISKEYS:
        db.add(models.Whiskey(**data))
    db.commit()
    db.close()
    print(f"Seeded {len(WHISKEYS)} whiskeys successfully.")


if __name__ == "__main__":
    seed()
