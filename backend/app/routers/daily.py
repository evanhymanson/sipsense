"""
Daily Discovery — a rotating "whiskey of the day" with fun facts.

GET /daily/  — get today's featured whiskey
"""

import hashlib
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Whiskey

router = APIRouter(prefix="/daily", tags=["daily"])

# ── Fun trivia & conversation starters ────────────────────────────────────

TASTING_TIPS = [
    "Try adding a single drop of water — it can open up hidden flavors you'd never notice neat.",
    "Let it sit in the glass for 5 minutes before your first sip. Patience pays off.",
    "Smell it with your mouth slightly open — it helps you pick up more nuance.",
    "Try tasting with a piece of dark chocolate between sips. Thank me later.",
    "Compare this side-by-side with something from a different category. Contrast is the best teacher.",
    "Hold a sip in your mouth for 5 seconds before swallowing. Notice how the flavors shift.",
    "Cup the glass in your hand for 30 seconds first — the warmth releases aromas.",
    "Try it in a tulip-shaped glass vs. a rocks glass. The shape changes everything.",
]

TIME_CONTEXT = {
    0: "Monday blues? This bottle says otherwise.",
    1: "Tuesday calls for something worth savoring.",
    2: "Hump day. You've earned a pour.",
    3: "Thursday — close enough to the weekend to start exploring.",
    4: "Friday vibes. This one's a celebration in a glass.",
    5: "Saturday discovery time. No rush, just good whiskey.",
    6: "Sunday slow pour. Take your time with this one.",
}


def _daily_seed(day: date) -> int:
    """Generate a deterministic seed from the date so all users see the same whiskey."""
    date_str = day.isoformat()
    return int(hashlib.sha256(date_str.encode()).hexdigest()[:8], 16)


@router.get("/")
def get_daily_discovery(db: Session = Depends(get_db)):
    """Get today's featured whiskey. The same bottle is shown to all users for the day."""
    today = date.today()
    seed = _daily_seed(today)

    # Count eligible whiskeys (need flavor profile + description for a good feature)
    count = db.query(func.count(Whiskey.id)).filter(
        Whiskey.flavor_profile != None,
        Whiskey.flavor_profile != "",
    ).scalar()

    if not count or count == 0:
        raise HTTPException(status_code=404, detail="No whiskeys available yet")

    # Deterministic pick based on date
    offset = seed % count
    whiskey = db.query(Whiskey).filter(
        Whiskey.flavor_profile != None,
        Whiskey.flavor_profile != "",
    ).offset(offset).first()

    if not whiskey:
        raise HTTPException(status_code=404, detail="No whiskey found")

    # Pick a tasting tip deterministically
    tip = TASTING_TIPS[seed % len(TASTING_TIPS)]
    weekday_msg = TIME_CONTEXT.get(today.weekday(), "")

    # Build flavor tags
    flavors = [f.strip() for f in (whiskey.flavor_profile or "").split(",") if f.strip()]

    # "Did you know" fact based on category
    did_you_know = _category_fact(whiskey.category, seed)

    return {
        "date": today.isoformat(),
        "weekday": today.strftime("%A"),
        "weekday_message": weekday_msg,
        "whiskey": {
            "id": whiskey.id,
            "name": whiskey.name,
            "distillery": whiskey.distillery,
            "category": whiskey.category,
            "region": whiskey.region,
            "age": whiskey.age,
            "abv": whiskey.abv,
            "price_usd": whiskey.price_usd,
            "description": whiskey.description,
            "flavor_profile": whiskey.flavor_profile,
            "rating_avg": whiskey.rating_avg,
            "rating_count": whiskey.rating_count,
        },
        "flavors": flavors,
        "tasting_tip": tip,
        "did_you_know": did_you_know,
        "conversation_starter": _conversation_starter(whiskey, seed),
    }


def _category_fact(category: str, seed: int) -> str:
    """Return a fun fact relevant to the whiskey's category."""
    facts = {
        "bourbon": [
            "There are more barrels of bourbon aging in Kentucky than there are people living there.",
            "Bourbon barrels can only be used once — after that, they're shipped to Scotland, Ireland, and Japan.",
            "The red layer inside a charred bourbon barrel is called the 'red line' and it's where caramel and vanilla flavors come from.",
            "George Washington ran one of the largest whiskey distilleries in America in the 1790s.",
        ],
        "scotch": [
            "Scotland has six whisky regions, each with a distinct character: Speyside, Highland, Lowland, Islay, Campbeltown, and Islands.",
            "The word 'whisky' comes from the Gaelic 'uisge beatha', meaning 'water of life'.",
            "A bottle of Macallan 1926 sold for $1.9 million in 2019, making it the most expensive bottle ever.",
            "Islay, an island of just 3,000 people, has 9 active distilleries.",
        ],
        "irish": [
            "Irish distillers invented the column still, which revolutionized whiskey production worldwide.",
            "In 1900, Irish whiskey outsold scotch by 3 to 1. Prohibition and trade wars reversed that entirely.",
            "The word 'whiskey' (with an 'e') comes from Ireland. Scotland spells it 'whisky' — no 'e'.",
        ],
        "japanese": [
            "Suntory's founder hired Masataka Taketsuru, who had studied in Scotland, to build Japan's first distillery in 1923.",
            "Japanese distilleries are known for making every style in-house — they rarely trade barrels between distilleries.",
            "The Japanese highball (whisky + soda water) is an art form — some bars have dedicated highball machines.",
        ],
        "rye": [
            "Before Prohibition, rye whiskey was America's most popular spirit — particularly in the Northeast.",
            "The Sazerac, America's oldest cocktail (1838), was originally made with rye whiskey.",
            "Maryland and Pennsylvania were once the rye whiskey capitals of America.",
        ],
    }

    cat_lower = category.lower()
    for key, fact_list in facts.items():
        if key in cat_lower:
            return fact_list[seed % len(fact_list)]
    return "Every glass of whiskey represents years of patient aging — time you get to taste."


def _conversation_starter(whiskey: Whiskey, seed: int) -> str:
    """A fun question or talking point related to the featured whiskey."""
    starters = [
        f"If {whiskey.name} were a song, what genre would it be?",
        f"Would you pair {whiskey.name} with a steak dinner or a campfire s'more?",
        f"Describe {whiskey.name} in three words — go!",
        f"If you could only drink one {whiskey.category} for the rest of the year, would this be it?",
        f"At {whiskey.abv}% ABV — neat, on the rocks, or with water?",
        f"What's the perfect setting for sipping {whiskey.name}?",
        f"If {whiskey.distillery} invited you for a tour, what's the first question you'd ask?",
        f"Rate the bottle design of {whiskey.name} from 1-10 — looks matter too!",
    ]
    return starters[seed % len(starters)]
