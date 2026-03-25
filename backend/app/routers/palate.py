from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from collections import Counter
from ..database import get_db
from ..models import Whiskey, UserRating, UserFavorite, User, UserBadge
from ..auth import get_current_user, get_optional_user
from .. import schemas
from ..ml.taste_similarity import compute_palate_match

router = APIRouter(prefix="/palate", tags=["palate"])


def _whiskey_dict(w):
    return {
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


def _build_narrative(top_categories, top_flavors, total_rated, avg_score):
    """Build a short plain-English description of the user's palate."""
    if total_rated == 0:
        return "Rate some whiskeys to build your palate profile."

    top_cat = top_categories[0]["name"] if top_categories else "whiskey"
    top_flavors_str = (
        ", ".join(f["name"] for f in top_flavors[:3]) if top_flavors else "varied flavors"
    )

    score_adj = (
        "discerning" if avg_score >= 4.2
        else "enthusiastic" if avg_score >= 3.5
        else "exploratory"
    )

    experience = (
        "power user" if total_rated >= 20
        else "regular" if total_rated >= 8
        else "beginner"
    )

    if experience == "beginner":
        opener = f"You're just getting started — {total_rated} bottle{'s' if total_rated != 1 else ''} in."
    elif experience == "regular":
        opener = f"With {total_rated} bottles rated, you've built a solid baseline."
    else:
        opener = f"At {total_rated} bottles, you're well into enthusiast territory."

    return (
        f"{opener} You lean toward {top_cat}, and your palate tends toward {top_flavors_str}. "
        f"Your ratings average {avg_score:.1f}/5, which makes you a {score_adj} scorer."
    )


@router.get("/me")
def get_my_palate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.username

    # ── Ratings ──────────────────────────────────────────────────────────────
    ratings = (
        db.query(UserRating)
        .filter(UserRating.user_id == user_id)
        .order_by(UserRating.created_at.desc())
        .all()
    )

    # ── Favorites ─────────────────────────────────────────────────────────────
    favorites_rows = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == user_id)
        .order_by(UserFavorite.created_at.desc())
        .all()
    )
    fav_whiskey_ids = [f.whiskey_id for f in favorites_rows]
    fav_whiskeys = (
        db.query(Whiskey).filter(Whiskey.id.in_(fav_whiskey_ids)).all()
        if fav_whiskey_ids else []
    )

    # ── Aggregations ──────────────────────────────────────────────────────────
    rated_whiskey_ids = [r.whiskey_id for r in ratings]
    rated_whiskeys = (
        db.query(Whiskey).filter(Whiskey.id.in_(rated_whiskey_ids)).all()
        if rated_whiskey_ids else []
    )
    whiskey_by_id = {w.id: w for w in rated_whiskeys}

    category_counter: Counter = Counter()
    flavor_counter: Counter = Counter()
    prices = []

    for r in ratings:
        w = whiskey_by_id.get(r.whiskey_id)
        if not w:
            continue
        category_counter[w.category] += 1
        if w.price_usd:
            prices.append(w.price_usd)
        if w.flavor_profile:
            for tag in [t.strip().lower() for t in w.flavor_profile.split(",")]:
                if tag:
                    flavor_counter[tag] += 1

    top_categories = [
        {"name": cat, "count": cnt}
        for cat, cnt in category_counter.most_common(6)
    ]
    top_flavors = [
        {"name": flavor, "count": cnt}
        for flavor, cnt in flavor_counter.most_common(10)
    ]

    scores = [r.score for r in ratings]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0

    # ── Recent ratings with whiskey data ─────────────────────────────────────
    recent = []
    for r in ratings[:15]:
        w = whiskey_by_id.get(r.whiskey_id)
        if w:
            recent.append({
                "score": r.score,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "whiskey": _whiskey_dict(w),
            })

    narrative = _build_narrative(top_categories, top_flavors, len(ratings), avg_score)

    # ── Badges ─────────────────────────────────────────────────────────────
    from sqlalchemy.orm import joinedload
    user_badges = (
        db.query(UserBadge)
        .filter(UserBadge.user_id == user_id)
        .options(joinedload(UserBadge.badge))
        .order_by(UserBadge.awarded_at.desc())
        .all()
    )
    badges = [
        {
            "slug": ub.badge.slug,
            "name": ub.badge.name,
            "description": ub.badge.description,
            "emoji": ub.badge.emoji,
            "category": ub.badge.category,
            "awarded_at": ub.awarded_at.isoformat() if ub.awarded_at else None,
        }
        for ub in user_badges
    ]

    return {
        "narrative": narrative,
        "stats": {
            "total_rated": len(ratings),
            "total_favorites": len(favorites_rows),
            "avg_score": avg_score,
            "avg_price": avg_price,
        },
        "top_categories": top_categories,
        "top_flavors": top_flavors,
        "recent_ratings": recent,
        "favorites": [_whiskey_dict(w) for w in fav_whiskeys[:12]],
        "badges": badges,
    }


@router.get("/match/{username}", response_model=schemas.PalateMatchResult)
def get_palate_match(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compare your palate with another user's."""
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot match against yourself")

    target = db.query(User).filter(User.username == username).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    return compute_palate_match(current_user.username, username, db)
