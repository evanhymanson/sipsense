"""
Blind Tasting Challenge — gamified whiskey education.

GET  /blind-tasting/challenge  — get a random whiskey with clues (no name/brand shown)
POST /blind-tasting/guess      — submit a guess and get scored
"""

import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Whiskey

router = APIRouter(prefix="/blind-tasting", tags=["blind-tasting"])

# Difficulty levels control how much info is revealed
DIFFICULTY = {
    "easy": {
        "show_category": False,
        "show_region": False,
        "show_abv": True,
        "show_age": True,
        "show_price_range": True,
        "show_flavors": True,      # all flavors
        "show_description": True,
        "points": 10,
    },
    "medium": {
        "show_category": False,
        "show_region": False,
        "show_abv": True,
        "show_age": False,
        "show_price_range": True,
        "show_flavors": True,      # limited flavors
        "max_flavors": 3,
        "show_description": False,
        "points": 25,
    },
    "hard": {
        "show_category": False,
        "show_region": False,
        "show_abv": False,
        "show_age": False,
        "show_price_range": False,
        "show_flavors": True,
        "max_flavors": 2,
        "show_description": False,
        "points": 50,
    },
}

PRICE_RANGES = [
    (0, 25, "Budget-friendly (under $25)"),
    (25, 50, "Mid-range ($25-$50)"),
    (50, 100, "Premium ($50-$100)"),
    (100, 200, "Luxury ($100-$200)"),
    (200, 99999, "Ultra-premium ($200+)"),
]


def _price_range_label(price: float | None) -> str | None:
    if price is None:
        return None
    for low, high, label in PRICE_RANGES:
        if low <= price < high:
            return label
    return None


def _build_clues(whiskey: Whiskey, difficulty: str) -> dict:
    """Build a clue set from a whiskey based on difficulty level."""
    config = DIFFICULTY[difficulty]
    clues = {"difficulty": difficulty, "points": config["points"]}

    if config.get("show_abv"):
        clues["abv"] = whiskey.abv
    if config.get("show_age") and whiskey.age:
        clues["age"] = whiskey.age
    if config.get("show_price_range") and whiskey.price_usd:
        clues["price_range"] = _price_range_label(whiskey.price_usd)
    if config.get("show_description") and whiskey.description:
        # Strip any mention of the whiskey name from the description
        desc = whiskey.description
        for word in whiskey.name.split():
            if len(word) > 3:  # skip short words like "The"
                desc = desc.replace(word, "___")
        clues["description_hint"] = desc

    if config.get("show_flavors") and whiskey.flavor_profile:
        flavors = [f.strip() for f in whiskey.flavor_profile.split(",") if f.strip()]
        max_f = config.get("max_flavors", len(flavors))
        if len(flavors) > max_f:
            flavors = random.sample(flavors, max_f)
        clues["flavors"] = flavors

    # Always show the possible categories to guess from
    clues["guess_options"] = ["bourbon", "scotch", "irish", "japanese", "rye", "canadian", "single malt", "blended"]

    return clues


class GuessRequest(BaseModel):
    whiskey_id: int
    guess_category: str
    difficulty: str = "easy"


@router.get("/challenge")
def get_challenge(
    difficulty: str = "easy",
    db: Session = Depends(get_db),
):
    """Get a random whiskey challenge with clues appropriate to the difficulty level."""
    if difficulty not in DIFFICULTY:
        raise HTTPException(status_code=400, detail="Difficulty must be: easy, medium, or hard")

    # Pick a random whiskey that has a flavor profile (needed for clues)
    count = db.query(func.count(Whiskey.id)).filter(
        Whiskey.flavor_profile != None,
        Whiskey.flavor_profile != "",
    ).scalar()

    if not count or count == 0:
        raise HTTPException(status_code=404, detail="No whiskeys available for the challenge")

    offset = random.randint(0, count - 1)
    whiskey = db.query(Whiskey).filter(
        Whiskey.flavor_profile != None,
        Whiskey.flavor_profile != "",
    ).offset(offset).first()

    if not whiskey:
        raise HTTPException(status_code=404, detail="No whiskeys available")

    clues = _build_clues(whiskey, difficulty)

    return {
        "challenge_id": whiskey.id,
        "clues": clues,
    }


@router.post("/guess")
def submit_guess(
    guess: GuessRequest,
    db: Session = Depends(get_db),
):
    """Check a guess and return the result with the full whiskey reveal."""
    whiskey = db.query(Whiskey).filter(Whiskey.id == guess.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    config = DIFFICULTY.get(guess.difficulty, DIFFICULTY["easy"])
    actual_category = whiskey.category.lower().strip()
    guess_category = guess.guess_category.lower().strip()

    # Score the guess
    correct = actual_category == guess_category
    # Partial credit for close guesses
    partial = False
    if not correct:
        # e.g. guessing "scotch" for a "single malt" (which is often scotch)
        close_pairs = [
            ({"scotch", "single malt"}),
            ({"bourbon", "rye"}),
            ({"blended", "scotch"}),
            ({"blended", "canadian"}),
        ]
        for pair in close_pairs:
            if actual_category in pair and guess_category in pair:
                partial = True
                break

    points = config["points"] if correct else (config["points"] // 2 if partial else 0)

    # Fun feedback messages
    if correct:
        messages = [
            "Nailed it! Your palate is sharp.",
            "Spot on! You clearly know your whiskey.",
            "Correct! That nose doesn't lie.",
            "You got it! Are you a sommelier in disguise?",
        ]
    elif partial:
        messages = [
            f"Close! It's actually {whiskey.category} — but you're in the right neighborhood.",
            f"Almost! {whiskey.category}, not {guess.guess_category} — but a reasonable guess.",
            f"Not quite, but {whiskey.category} and {guess.guess_category} do share some DNA.",
        ]
    else:
        messages = [
            f"Not this time! It's a {whiskey.category}. Now you'll remember it.",
            f"Tricky one! This is actually {whiskey.category}. The flavors can be deceiving.",
            f"Nope — {whiskey.category}! But that's how you learn.",
        ]

    return {
        "correct": correct,
        "partial": partial,
        "points": points,
        "message": random.choice(messages),
        "reveal": {
            "id": whiskey.id,
            "name": whiskey.name,
            "distillery": whiskey.distillery,
            "category": whiskey.category,
            "region": whiskey.region,
            "age": whiskey.age,
            "abv": whiskey.abv,
            "price_usd": whiskey.price_usd,
            "flavor_profile": whiskey.flavor_profile,
            "rating_avg": whiskey.rating_avg,
            "description": whiskey.description,
        },
        "fun_fact": _get_fun_fact(whiskey),
    }


def _get_fun_fact(whiskey: Whiskey) -> str:
    """Generate a fun fact about the whiskey or its category."""
    facts = {
        "bourbon": [
            "By law, bourbon must be made from at least 51% corn and aged in new charred oak barrels.",
            "95% of the world's bourbon is made in Kentucky, but it can legally be made anywhere in the US.",
            "The name 'bourbon' likely comes from Bourbon County, Kentucky — though that's debated.",
        ],
        "scotch": [
            "Scotch must be aged at least 3 years in oak barrels in Scotland to earn the name.",
            "There are over 130 active scotch distilleries in Scotland.",
            "The 'angel's share' — about 2% of scotch evaporates from the barrel each year.",
        ],
        "irish": [
            "Irish whiskey is typically triple-distilled, making it exceptionally smooth.",
            "Ireland's oldest licensed distillery, Bushmills, has been operating since 1608.",
            "Irish whiskey was once the most popular spirit in the world before Prohibition devastated it.",
        ],
        "japanese": [
            "Japanese whisky was inspired by scotch after Masataka Taketsuru studied distilling in Scotland in 1918.",
            "Japanese distilleries often use multiple still shapes to create variety within a single distillery.",
            "Yamazaki 2013 Sherry Cask was named World's Best Whisky in 2015, shocking the spirits world.",
        ],
        "rye": [
            "Rye whiskey must contain at least 51% rye grain — giving it that signature spicy kick.",
            "Rye was the most popular American whiskey before Prohibition nearly killed it off.",
            "A classic Manhattan cocktail was originally made with rye, not bourbon.",
        ],
        "canadian": [
            "Canadian whisky is often called 'rye whisky' even when it contains very little actual rye.",
            "Canada has no minimum age requirement, but most Canadian whisky is aged at least 3 years.",
            "During Prohibition, Canadian whisky was smuggled across the border in huge quantities.",
        ],
    }

    category = whiskey.category.lower()
    for key, fact_list in facts.items():
        if key in category:
            return random.choice(fact_list)

    return "Every whiskey tells a story — from the grain that grew it to the barrel that shaped it."
