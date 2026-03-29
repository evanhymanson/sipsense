"""Gap 2: Region exploration pages — whiskey regions with geography, style, and featured bottles."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from .. import models, schemas
from ..database import get_db
from ..auth import get_optional_user

router = APIRouter(prefix="/regions", tags=["regions"])

REGIONS = [
    {
        "slug": "kentucky",
        "title": "Kentucky",
        "country": "United States",
        "emoji": "\U0001f3c7",
        "tagline": "The bourbon capital of the world",
        "lat": 37.8393,
        "lng": -84.2700,
        "map_zoom": 7,
        "style_description": [
            "Kentucky is the undisputed heartland of bourbon whiskey, producing approximately 95% of the world's supply. The state's unique limestone-filtered water, rich in calcium and magnesium but free of iron, creates the ideal mineral profile for distilling.",
            "The dramatic temperature swings between hot, humid summers and cold winters drive the spirit in and out of the charred oak barrels, accelerating the extraction of color, flavor, and character. This natural process gives Kentucky bourbon its signature deep amber color, rich vanilla-caramel sweetness, and full body.",
            "From the historic distilleries along the Kentucky Bourbon Trail to craft upstarts pushing boundaries, the state offers an extraordinary diversity of styles — from wheated bourbons soft as velvet to high-rye expressions with a spicy kick.",
        ],
        "key_characteristics": ["vanilla", "caramel", "oak", "corn sweetness", "baking spice"],
        "notable_distilleries": ["Buffalo Trace", "Maker's Mark", "Wild Turkey", "Woodford Reserve", "Four Roses", "Heaven Hill", "Jim Beam"],
        "categories": ["bourbon"],
        "region_match": ["kentucky"],
        "climate_note": "Hot summers and cold winters cycle spirit aggressively through barrel wood, deepening color and flavor.",
    },
    {
        "slug": "tennessee",
        "title": "Tennessee",
        "country": "United States",
        "emoji": "\U0001f3b5",
        "tagline": "Home of the Lincoln County Process",
        "lat": 35.5175,
        "lng": -86.5804,
        "map_zoom": 7,
        "style_description": [
            "Tennessee whiskey is legally distinct from bourbon thanks to the Lincoln County Process — a charcoal mellowing step where the fresh distillate is slowly filtered through sugar maple charcoal before aging. This extra step imparts a distinctive smoothness and subtle sweetness.",
            "While Jack Daniel's put Tennessee on the global whiskey map, a growing wave of craft distillers is showcasing the state's diverse terroir. From the iron-free cave spring water of Lynchburg to the rolling hills of Middle Tennessee, each distillery brings its own character.",
            "Tennessee whiskeys tend to be approachable and mellow, making them excellent sipping whiskeys and cocktail bases alike.",
        ],
        "key_characteristics": ["charcoal mellowed", "smooth", "maple", "vanilla", "banana"],
        "notable_distilleries": ["Jack Daniel's", "George Dickel", "Nelson's Green Brier", "Chattanooga Whiskey"],
        "categories": ["tennessee"],
        "region_match": ["tennessee"],
        "climate_note": "Similar to Kentucky with hot summers driving barrel interaction, but the charcoal mellowing adds a distinct smoothness.",
    },
    {
        "slug": "islay",
        "title": "Islay",
        "country": "Scotland",
        "emoji": "\U0001f32c\ufe0f",
        "tagline": "Peat, smoke, and the wild Atlantic",
        "lat": 55.6500,
        "lng": -6.2500,
        "map_zoom": 10,
        "style_description": [
            "Islay (pronounced 'eye-lah') is a small island off Scotland's west coast that punches far above its weight in the whisky world. Home to nine active distilleries, Islay is synonymous with heavily peated, smoky single malts that carry the briny character of the Atlantic.",
            "The island's abundant peat bogs provide the fuel for drying malted barley, infusing the grain with phenolic compounds that translate into smoky, medicinal, and iodine-like flavors. But Islay is no one-trick pony — distilleries like Bruichladdich and Bunnahabhain produce unpeated or lightly peated expressions that showcase the island's softer side.",
            "Each Islay distillery has its own water source, microclimate, and barrel program, resulting in a spectrum from the maritime elegance of Bowmore to the campfire intensity of Ardbeg.",
        ],
        "key_characteristics": ["peat", "smoke", "brine", "iodine", "maritime", "medicinal"],
        "notable_distilleries": ["Ardbeg", "Laphroaig", "Lagavulin", "Bruichladdich", "Bowmore", "Kilchoman", "Bunnahabhain", "Caol Ila"],
        "categories": ["scotch"],
        "region_match": ["islay"],
        "climate_note": "Wet, windswept, and maritime — the sea air permeates the warehouses, adding a briny, coastal character to the aging spirit.",
    },
    {
        "slug": "speyside",
        "title": "Speyside",
        "country": "Scotland",
        "emoji": "\U0001f36f",
        "tagline": "Scotland's golden triangle of single malt",
        "lat": 57.4500,
        "lng": -3.2000,
        "map_zoom": 9,
        "style_description": [
            "Speyside is home to more than half of Scotland's distilleries, clustered around the River Spey in the northeast Highlands. This concentration of craft has earned it recognition as a distinct whisky region, and it's where many of the world's best-selling single malts are born.",
            "Speyside malts are generally known for their elegance, complexity, and fruit-forward character. Sherry cask maturation is a hallmark, producing rich notes of dried fruit, Christmas cake, and dark chocolate. Lighter Speyside expressions lean toward honey, green apple, and floral notes.",
            "From the sherried richness of Macallan and GlenDronach to the honeyed delicacy of Glenfiddich and Glenlivet, Speyside offers the widest stylistic range of any Scotch region.",
        ],
        "key_characteristics": ["honey", "dried fruit", "sherry", "apple", "vanilla", "floral"],
        "notable_distilleries": ["The Macallan", "Glenfiddich", "The Glenlivet", "Aberlour", "Balvenie", "GlenDronach"],
        "categories": ["scotch"],
        "region_match": ["speyside"],
        "climate_note": "Sheltered river valleys with moderate rainfall create gentle aging conditions that favor elegance over power.",
    },
    {
        "slug": "highland",
        "title": "Highland",
        "country": "Scotland",
        "emoji": "\u26f0\ufe0f",
        "tagline": "Scotland's vast and diverse whisky heartland",
        "lat": 57.0000,
        "lng": -4.5000,
        "map_zoom": 7,
        "style_description": [
            "The Highland region is the largest and most geographically diverse of Scotland's whisky regions, stretching from the Central Belt north to Caithness and including both coasts. This diversity means Highland whiskies span a remarkable range of styles.",
            "Northern Highlands tend toward heathery, spicy characters (Glenmorangie, Dalmore). Western Highlands lean maritime and slightly peated. Eastern Highlands produce lighter, fruitier expressions. Southern Highlands bridge the gap toward Lowland styles.",
            "What unites Highland whiskies is a general robustness — more body and complexity than Lowland malts, but typically less peat than Islay. They are excellent all-rounders and often recommended as entry points for new single malt drinkers.",
        ],
        "key_characteristics": ["heather", "honey", "dried fruit", "spice", "malt", "light smoke"],
        "notable_distilleries": ["Glenmorangie", "Dalmore", "Oban", "Clynelish", "Old Pulteney", "Edradour"],
        "categories": ["scotch"],
        "region_match": ["highland", "highlands"],
        "climate_note": "Varied — from sheltered glens to windswept coasts, creating a wide spectrum of warehouse conditions.",
    },
    {
        "slug": "lowland",
        "title": "Lowland",
        "country": "Scotland",
        "emoji": "\U0001f33e",
        "tagline": "Gentle, floral, and approachable",
        "lat": 55.9000,
        "lng": -3.5000,
        "map_zoom": 8,
        "style_description": [
            "The Lowland region covers southern Scotland below the Highland Line. Historically known as the 'Lowland Ladies' for their gentle, light character, Lowland whiskies are the most approachable of Scottish single malts.",
            "Triple distillation was once common here (as in Ireland), producing a lighter, smoother spirit. Modern Lowland distilleries maintain this tradition of elegance while adding contemporary twists — grain-forward expressions, botanical influences, and innovative cask finishes.",
            "Lowland malts are ideal for those new to Scotch or who prefer subtlety over power. Notes of grass, citrus, honeysuckle, and light malt prevail.",
        ],
        "key_characteristics": ["floral", "grass", "citrus", "light malt", "honeysuckle", "gentle"],
        "notable_distilleries": ["Auchentoshan", "Glenkinchie", "Bladnoch", "Lindores Abbey"],
        "categories": ["scotch"],
        "region_match": ["lowland", "lowlands"],
        "climate_note": "Mild and temperate, producing slow, gentle maturation and delicate flavor profiles.",
    },
    {
        "slug": "campbeltown",
        "title": "Campbeltown",
        "country": "Scotland",
        "emoji": "\u2693",
        "tagline": "The whisky capital that time forgot",
        "lat": 55.4260,
        "lng": -5.6035,
        "map_zoom": 11,
        "style_description": [
            "Once home to over 30 distilleries in the Victorian era, Campbeltown on the Kintyre peninsula was known as the 'whisky capital of the world.' Today only three distilleries remain, but they produce some of Scotland's most characterful malts.",
            "Campbeltown whiskies are often described as having a unique 'wet wool' or briny maritime character, combined with a slight oiliness and earthy funk. They sit between Highland richness and Islay peatiness — complex, layered, and rewarding.",
            "Springbank in particular is legendary among whisky enthusiasts for its traditional production methods (floor malting, direct-fired stills) and exceptional range of styles.",
        ],
        "key_characteristics": ["brine", "maritime", "oily", "toffee", "light peat", "leather"],
        "notable_distilleries": ["Springbank", "Glen Scotia", "Glengyle (Kilkerran)"],
        "categories": ["scotch"],
        "region_match": ["campbeltown"],
        "climate_note": "Exposed Atlantic coast with salt air influencing the warehoused spirit.",
    },
    {
        "slug": "japan",
        "title": "Japan",
        "country": "Japan",
        "emoji": "\U0001f1ef\U0001f1f5",
        "tagline": "Precision and harmony in every drop",
        "lat": 35.6762,
        "lng": 139.6503,
        "map_zoom": 5,
        "style_description": [
            "Japanese whisky burst onto the world stage in the early 2000s, though its roots trace back to 1923 when Masataka Taketsuru brought Scotch-making techniques home from Scotland. Today, Japan is recognized as one of the world's premier whisky-producing nations.",
            "Japanese distillers are renowned for their meticulous attention to detail, blending artistry, and harmony-driven philosophy (wa). Unlike Scotland where distilleries trade casks, Japanese companies typically own multiple still types within a single distillery to create diverse base spirits for blending.",
            "The result is whiskies of extraordinary refinement — from the delicate, floral elegance of Hakushu to the rich, sherried complexity of Yamazaki. Japanese whisky is often praised for its balance, subtlety, and food-friendliness.",
        ],
        "key_characteristics": ["delicate", "floral", "balanced", "sandalwood", "green tea", "umami"],
        "notable_distilleries": ["Yamazaki", "Hakushu", "Yoichi", "Miyagikyo", "Chichibu", "Mars Shinshu"],
        "categories": ["japanese"],
        "region_match": ["japan", "japanese"],
        "climate_note": "Diverse climates from Hokkaido's cold north to subtropical Kyushu, each imparting different aging characteristics.",
    },
    {
        "slug": "ireland",
        "title": "Ireland",
        "country": "Ireland",
        "emoji": "\u2618\ufe0f",
        "tagline": "Triple-distilled, smooth as silk",
        "lat": 53.3498,
        "lng": -6.2603,
        "map_zoom": 6,
        "style_description": [
            "Ireland has one of the oldest whiskey traditions in the world, with records of distillation dating to the 12th century. After decades of decline, Irish whiskey is experiencing an extraordinary renaissance, with over 40 distilleries now operating across the island.",
            "The hallmark of Irish whiskey is triple distillation, which produces a lighter, smoother spirit than the typical double-distilled Scotch. Most Irish whiskey is also made with unpeated malt, giving it a clean, approachable character.",
            "Pot still whiskey — made from a mix of malted and unmalted barley — is uniquely Irish and delivers a distinctive creamy, spicy mouthfeel. From the honey-smooth Jameson to the complex pot still expressions of Redbreast and Green Spot, Ireland offers something for every palate.",
        ],
        "key_characteristics": ["smooth", "creamy", "honey", "vanilla", "light spice", "green fruit"],
        "notable_distilleries": ["Jameson (Midleton)", "Redbreast", "Bushmills", "Teeling", "Tullamore D.E.W.", "Green Spot"],
        "categories": ["irish"],
        "region_match": ["ireland", "irish"],
        "climate_note": "Mild, damp oceanic climate with minimal temperature extremes, producing slow, gentle maturation.",
    },
]


@router.get("/")
def list_regions():
    """Return all whiskey regions with summary info."""
    return [
        {
            "slug": r["slug"],
            "title": r["title"],
            "country": r["country"],
            "emoji": r["emoji"],
            "tagline": r["tagline"],
            "lat": r["lat"],
            "lng": r["lng"],
        }
        for r in REGIONS
    ]


@router.get("/{slug}")
def get_region(slug: str):
    """Return full detail for a single region."""
    region = next((r for r in REGIONS if r["slug"] == slug), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    return region


@router.get("/{slug}/whiskeys")
def get_region_whiskeys(
    slug: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("rating"),
    db: Session = Depends(get_db),
):
    """Return whiskeys associated with a region, sorted and paginated."""
    region = next((r for r in REGIONS if r["slug"] == slug), None)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")

    q = db.query(models.Whiskey)

    # Match by region string or by category
    from sqlalchemy import or_
    conditions = []
    for rm in region.get("region_match", []):
        conditions.append(models.Whiskey.region.ilike(f"%{rm}%"))
    for cat in region.get("categories", []):
        conditions.append(models.Whiskey.category.ilike(f"%{cat}%"))
    if conditions:
        q = q.filter(or_(*conditions))

    total = q.count()

    if sort == "price_asc":
        q = q.order_by(models.Whiskey.price_usd.asc().nullslast())
    elif sort == "price_desc":
        q = q.order_by(models.Whiskey.price_usd.desc().nullslast())
    elif sort == "name":
        q = q.order_by(models.Whiskey.name)
    else:
        q = q.order_by(models.Whiskey.rating_avg.desc())

    whiskeys = q.offset(skip).limit(limit).all()
    return {
        "items": [schemas.WhiskeyRead.model_validate(w) for w in whiskeys],
        "total": total,
    }
