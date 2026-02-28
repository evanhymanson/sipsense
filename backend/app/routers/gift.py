from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from ..database import get_db
from ..models import Whiskey

router = APIRouter(prefix="/gift", tags=["gift"])

BUDGET_RANGES = {
    "budget":  (25,  55),
    "mid":     (55,  110),
    "premium": (110, 220),
    "luxury":  (220, 9999),
}

LEVEL_LABELS = {
    "newbie":      "whiskey newcomer",
    "casual":      "casual whiskey fan",
    "enthusiast":  "whiskey enthusiast",
    "connoisseur": "seasoned connoisseur",
}


class GiftRequest(BaseModel):
    drinker_level: str = "casual"   # newbie | casual | enthusiast | connoisseur
    style: str = "any"              # bourbon | scotch | irish | japanese | rye | any
    budget: str = "mid"             # budget | mid | premium | luxury
    occasion: str = ""              # birthday | holiday | host_gift | just_because


@router.post("/")
def find_gift(req: GiftRequest, db: Session = Depends(get_db)):
    budget_min, budget_max = BUDGET_RANGES.get(req.budget, (25, 110))

    q = db.query(Whiskey).filter(
        Whiskey.price_usd.isnot(None),
        Whiskey.price_usd >= budget_min,
        Whiskey.price_usd <= budget_max,
        Whiskey.rating_avg >= 3.5,
    )

    if req.style != "any":
        q = q.filter(Whiskey.category == req.style)

    # Tune by drinker level
    if req.drinker_level == "newbie":
        # Sweet, approachable, lower ABV
        q = q.filter(
            or_(
                Whiskey.flavor_profile.ilike("%vanilla%"),
                Whiskey.flavor_profile.ilike("%honey%"),
                Whiskey.flavor_profile.ilike("%caramel%"),
                Whiskey.flavor_profile.ilike("%sweet%"),
            )
        )
    elif req.drinker_level == "connoisseur":
        # Prefer aged, higher-rated, niche
        q = q.filter(Whiskey.rating_avg >= 4.0)

    picks = q.order_by(Whiskey.rating_avg.desc()).limit(4).all()

    # Fallback: drop level filter if no results
    if not picks:
        q2 = db.query(Whiskey).filter(
            Whiskey.price_usd.isnot(None),
            Whiskey.price_usd >= budget_min,
            Whiskey.price_usd <= budget_max,
            Whiskey.rating_avg >= 3.0,
        )
        if req.style != "any":
            q2 = q2.filter(Whiskey.category == req.style)
        picks = q2.order_by(Whiskey.rating_avg.desc()).limit(4).all()

    style_label = req.style if req.style != "any" else "whiskey"
    level_label = LEVEL_LABELS.get(req.drinker_level, "whiskey fan")
    budget_label = f"${budget_min}–${budget_max if budget_max < 9000 else '200+'}"

    occasion_phrases = {
        "birthday": "For a birthday gift,",
        "holiday": "A holiday bottle they'll remember —",
        "host_gift": "A host gift that says you actually know what you're doing.",
        "just_because": "No occasion needed. Just a great bottle.",
    }
    occasion_phrase = occasion_phrases.get(req.occasion, "Here are our top picks:")

    message = (
        f"{occasion_phrase} we picked these for a {level_label} who loves {style_label}, "
        f"with a {budget_label} budget."
    )

    return {
        "message": message,
        "picks": [
            {
                "id": w.id,
                "name": w.name,
                "distillery": w.distillery,
                "category": w.category,
                "region": w.region,
                "age": w.age,
                "abv": w.abv,
                "price_usd": w.price_usd,
                "flavor_profile": w.flavor_profile,
                "rating_avg": w.rating_avg,
                "rating_count": w.rating_count,
            }
            for w in picks
        ],
    }
