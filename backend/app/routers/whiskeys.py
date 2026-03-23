import json
import os
import math
import logging
from urllib.parse import quote_plus
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from typing import Optional
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user


def _escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards in user input."""
    return s.replace("%", "\\%").replace("_", "\\_")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whiskeys", tags=["whiskeys"])

_SORT_OPTIONS = {"rating", "price_asc", "price_desc", "age", "name"}


@router.get("/", response_model=schemas.WhiskeyListResponse)
def list_whiskeys(
    q: Optional[str] = Query(None, max_length=200, description="Search by name or distillery"),
    category: Optional[str] = Query(None, max_length=50),
    region: Optional[str] = Query(None, max_length=100),
    flavor: Optional[str] = Query(None, max_length=200, description="Filter by flavor tag in flavor_profile"),
    min_abv: Optional[float] = Query(None, ge=0, le=100),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    sort_by: str = Query("rating", description="rating | price_asc | price_desc | age | name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(models.Whiskey).filter(
        models.Whiskey.image_url.isnot(None),
        models.Whiskey.image_url != "",
    )

    if q:
        q_safe = _escape_like(q)
        pattern = f"%{q_safe}%"
        query = query.filter(
            models.Whiskey.name.ilike(pattern) | models.Whiskey.distillery.ilike(pattern)
        )
    if category:
        query = query.filter(models.Whiskey.category.ilike(f"%{_escape_like(category)}%"))
    if region:
        query = query.filter(models.Whiskey.region.ilike(f"%{_escape_like(region)}%"))
    if flavor:
        terms = [t.strip() for t in flavor.split(',') if t.strip()]
        if len(terms) > 1:
            query = query.filter(or_(*[models.Whiskey.flavor_profile.ilike(f"%{_escape_like(t)}%") for t in terms]))
        else:
            query = query.filter(models.Whiskey.flavor_profile.ilike(f"%{_escape_like(flavor)}%"))
    if min_abv is not None:
        query = query.filter(models.Whiskey.abv >= min_abv)
    if min_price is not None:
        query = query.filter(models.Whiskey.price_usd >= min_price)
    if max_price is not None:
        query = query.filter(models.Whiskey.price_usd <= max_price)

    total = query.count()

    if sort_by == "price_asc":
        query = query.order_by(models.Whiskey.price_usd.asc().nullslast())
    elif sort_by == "price_desc":
        query = query.order_by(models.Whiskey.price_usd.desc().nullslast())
    elif sort_by == "age":
        query = query.order_by(models.Whiskey.age.desc().nullslast())
    elif sort_by == "name":
        query = query.order_by(models.Whiskey.name.asc())
    else:  # default: rating
        query = query.order_by(models.Whiskey.rating_avg.desc())

    items = query.offset(skip).limit(limit).all()
    return schemas.WhiskeyListResponse(items=items, total=total)


@router.get("/count")
def get_whiskey_count(db: Session = Depends(get_db)):
    """Total number of whiskeys with images (for hero text)."""
    count = db.query(models.Whiskey).filter(
        models.Whiskey.image_url.isnot(None),
        models.Whiskey.image_url != "",
    ).count()
    return {"count": count}


@router.get("/{whiskey_id}/similar", response_model=list[schemas.WhiskeyRead])
def get_similar(whiskey_id: int, top_n: int = 5, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")
    from ..ml.recommender import similar_whiskeys
    results = similar_whiskeys(whiskey, db, top_n=top_n)
    return [w for w, _ in results if w.image_url]


@router.get("/{whiskey_id}/blurb")
def get_blurb(whiskey_id: int, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Return cached description if complete; also trigger flavor scoring if missing
    desc = (whiskey.description or "").strip()
    has_blurb = desc and not desc.endswith(("...", "…", "read more", "Read more"))
    needs_flavor_scores = whiskey.flavor_x is None or whiskey.flavor_y is None

    if has_blurb and not needs_flavor_scores:
        return {"blurb": desc, "flavor_x": whiskey.flavor_x, "flavor_y": whiskey.flavor_y}

    # Try Claude API if key is set
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"blurb": desc if has_blurb else None, "status": "no_key",
                "flavor_x": whiskey.flavor_x, "flavor_y": whiskey.flavor_y}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        flavor_line = f"Known flavors: {whiskey.flavor_profile}\n" if whiskey.flavor_profile else ""

        prompt = (
            f"You are a friendly whiskey expert writing for beginners.\n\n"
            f"Write 2-3 warm, plain-English sentences about this whiskey. "
            f"Describe what it tastes like and what makes it interesting. "
            f"Base your description on the name and data provided — don't invent specific facts.\n\n"
            f"Name: {whiskey.name}\n"
            f"Distillery: {whiskey.distillery}\n"
            f"Category: {whiskey.category}\n"
            f"{'Region: ' + whiskey.region + chr(10) if whiskey.region else ''}"
            f"{'Age: ' + str(whiskey.age) + ' years' + chr(10) if whiskey.age else 'No age statement' + chr(10)}"
            f"ABV: {whiskey.abv}%\n"
            f"{flavor_line}"
            f"\nAlso return:\n"
            f"1. A comma-separated list of 3-6 flavor tags (e.g. vanilla, oak, caramel, smoky).\n"
            f"2. Two integer scores from 0-100 for plotting this whiskey on a flavor map:\n"
            f"   - SWEET_SMOKY: 0 = very sweet/fruity, 50 = balanced, 100 = very smoky/peaty\n"
            f"   - LIGHT_BOLD: 0 = very light/delicate, 50 = medium body, 100 = very bold/rich/full\n"
            f"\nFormat your response exactly as:\n"
            f"DESCRIPTION: <2-3 sentences>\n"
            f"FLAVORS: <comma-separated tags>\n"
            f"SWEET_SMOKY: <integer 0-100>\n"
            f"LIGHT_BOLD: <integer 0-100>"
        )
        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Parse structured response
        blurb = raw
        flavors = None
        flavor_x = None
        flavor_y = None

        if "DESCRIPTION:" in raw:
            lines_map = {}
            for line in raw.split("\n"):
                line = line.strip()
                for key in ("DESCRIPTION:", "FLAVORS:", "SWEET_SMOKY:", "LIGHT_BOLD:"):
                    if line.startswith(key):
                        lines_map[key] = line[len(key):].strip()
            blurb = lines_map.get("DESCRIPTION:", blurb)
            flavors = lines_map.get("FLAVORS:")
            try:
                flavor_x = max(0, min(100, int(lines_map.get("SWEET_SMOKY:", ""))))
            except (ValueError, TypeError):
                pass
            try:
                flavor_y = max(0, min(100, int(lines_map.get("LIGHT_BOLD:", ""))))
            except (ValueError, TypeError):
                pass

        # Cache in DB
        if not has_blurb:
            whiskey.description = blurb
        if flavors and not whiskey.flavor_profile:
            whiskey.flavor_profile = flavors
        if flavor_x is not None:
            whiskey.flavor_x = flavor_x
        if flavor_y is not None:
            whiskey.flavor_y = flavor_y
        db.commit()

        return {"blurb": whiskey.description or blurb, "status": "generated",
                "flavor_x": whiskey.flavor_x, "flavor_y": whiskey.flavor_y}
    except Exception as e:
        logger.error("Blurb generation failed for whiskey %d: %s", whiskey_id, e)
        return {"blurb": desc if has_blurb else None, "status": "error",
                "flavor_x": whiskey.flavor_x, "flavor_y": whiskey.flavor_y}


@router.get("/value-picks", response_model=list[schemas.WhiskeyRead])
def get_value_picks(
    category: Optional[str] = Query(None),
    max_price: float = Query(75.0, gt=0),
    region: Optional[str] = Query(None),
    limit: int = Query(12, le=50),
    db: Session = Depends(get_db),
):
    q = (
        db.query(models.Whiskey)
        .filter(
            models.Whiskey.image_url.isnot(None),
            models.Whiskey.image_url != "",
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
            models.Whiskey.rating_avg.isnot(None),
            models.Whiskey.rating_avg > 0,
        )
    )
    if category:
        q = q.filter(models.Whiskey.category.ilike(f"%{_escape_like(category)}%"))
    if region:
        q = q.filter(models.Whiskey.region.ilike(f"%{_escape_like(region)}%"))
    q = q.filter(models.Whiskey.price_usd <= max_price)

    # Pre-filter in SQL to avoid loading unbounded rows, then score in Python
    candidates = (
        q.order_by(models.Whiskey.rating_avg.desc())
        .limit(max(limit * 10, 200))
        .all()
    )
    scored = sorted(
        candidates,
        key=lambda w: w.rating_avg / math.log(max(w.price_usd, 2)),
        reverse=True,
    )
    return scored[:limit]


@router.get("/barcode/{upc}", response_model=schemas.WhiskeyRead)
def lookup_barcode(upc: str, db: Session = Depends(get_db)):
    """Look up a whiskey by its UPC barcode."""
    upc = upc.strip()
    if not upc:
        raise HTTPException(status_code=400, detail="Invalid barcode")

    # Exact match
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.upc == upc).first()
    if whiskey:
        return whiskey

    # Fallback: strip leading zeros and compare at SQL level
    upc_clean = upc.lstrip("0")
    whiskey = (
        db.query(models.Whiskey)
        .filter(
            models.Whiskey.upc.isnot(None),
            func.ltrim(models.Whiskey.upc, "0") == upc_clean,
        )
        .first()
    )
    if whiskey:
        return whiskey

    raise HTTPException(
        status_code=404,
        detail="No whiskey found for this barcode. Try searching by name instead.",
    )


@router.get("/{whiskey_id}/price-context")
def get_price_context(whiskey_id: int, db: Session = Depends(get_db)):
    """Price context: category average, percentile, deal verdict, budget alternatives."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    if not whiskey.price_usd:
        return {"available": False, "reason": "No price data for this whiskey"}

    price_stats = (
        db.query(
            func.count(models.Whiskey.id),
            func.avg(models.Whiskey.price_usd),
        )
        .filter(
            models.Whiskey.category == whiskey.category,
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
        )
        .first()
    )
    total_count = price_stats[0] or 0
    avg_price_raw = price_stats[1]
    if not total_count or avg_price_raw is None:
        return {"available": False, "reason": "No price data for this category"}

    avg_price = round(float(avg_price_raw), 2)

    below_count = (
        db.query(func.count(models.Whiskey.id))
        .filter(
            models.Whiskey.category == whiskey.category,
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
            models.Whiskey.price_usd < whiskey.price_usd,
        )
        .scalar() or 0
    )
    percentile = round(below_count / total_count * 100)

    ratio = whiskey.price_usd / avg_price if avg_price > 0 else 1.0
    if ratio <= 0.6:
        verdict, verdict_text = "great_deal", "Great Deal"
    elif ratio <= 0.9:
        verdict, verdict_text = "fair_price", "Fair Price"
    elif ratio <= 1.4:
        verdict, verdict_text = "premium", "Premium"
    else:
        verdict, verdict_text = "splurge", "Splurge"

    # Budget alternatives via content-based similarity
    from ..ml.recommender import similar_whiskeys
    similar = similar_whiskeys(whiskey, db, top_n=20)
    budget_alts = [
        {
            "id": w.id,
            "name": w.name,
            "distillery": w.distillery,
            "category": w.category,
            "price_usd": w.price_usd,
            "rating_avg": w.rating_avg,
            "similarity": round(score, 3),
        }
        for w, score in similar
        if w.price_usd and w.price_usd < whiskey.price_usd
    ][:3]

    return {
        "available": True,
        "category": whiskey.category,
        "category_avg_price": avg_price,
        "category_count": total_count,
        "price_percentile": percentile,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "budget_alternatives": budget_alts,
    }


@router.get("/{whiskey_id}/buy-links")
def get_buy_links(whiskey_id: int, db: Session = Depends(get_db)):
    """Return buy links for a whiskey — stored links or generated search URLs."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    if whiskey.buy_links:
        try:
            return {"links": json.loads(whiskey.buy_links)}
        except json.JSONDecodeError:
            pass

    name_enc = quote_plus(whiskey.name)
    utm = "utm_source=sipsense&utm_medium=referral&utm_campaign=bottle_detail"
    links = [
        {"retailer": "ReserveBar", "url": f"https://www.reservebar.com/search?q={name_enc}&{utm}"},
        {"retailer": "Total Wine", "url": f"https://www.totalwine.com/search/all?text={name_enc}&{utm}"},
        {"retailer": "Caskers", "url": f"https://www.caskers.com/catalogsearch/result/?q={name_enc}&{utm}"},
        {"retailer": "Flaviar", "url": f"https://flaviar.com/search?q={name_enc}&{utm}"},
    ]
    # Add Whisky Exchange for Scotch/Irish/Japanese
    if whiskey.category and any(c in (whiskey.category or "").lower() for c in ["scotch", "irish", "japanese", "world"]):
        links.insert(1, {"retailer": "The Whisky Exchange", "url": f"https://www.thewhiskyexchange.com/search?q={name_enc}&{utm}"})
    return {"links": links}


@router.get("/{whiskey_id}", response_model=schemas.WhiskeyRead)
def get_whiskey(whiskey_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")
    return whiskey


_ADMIN_USERS = set(
    u.strip() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()
)


@router.post("/", response_model=schemas.WhiskeyRead, status_code=201)
def create_whiskey(
    whiskey: schemas.WhiskeyCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.username not in _ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    db_whiskey = models.Whiskey(**whiskey.model_dump())
    db.add(db_whiskey)
    db.commit()
    db.refresh(db_whiskey)
    return db_whiskey


@router.post("/{whiskey_id}/rate", response_model=schemas.CheckInResponse)
def rate_whiskey(
    whiskey_id: int,
    rating: schemas.RatingCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Use the authenticated user's username as user_id
    user_id = current_user.username

    # Upsert: check for existing rating by this user on this whiskey
    existing = db.query(models.UserRating).filter(
        models.UserRating.user_id == user_id,
        models.UserRating.whiskey_id == whiskey_id,
    ).first()

    if existing:
        # Update the existing rating
        existing.score = rating.score
        if rating.notes is not None:
            existing.notes = rating.notes
        if rating.serving_style is not None:
            existing.serving_style = rating.serving_style
        if rating.location_note is not None:
            existing.location_note = rating.location_note
        db_rating = existing
    else:
        rating_data = rating.model_dump()
        rating_data["user_id"] = user_id
        db_rating = models.UserRating(whiskey_id=whiskey_id, **rating_data)
        db.add(db_rating)

    # Atomic recalculation: flush so the new/updated rating is visible in this
    # transaction, then UPDATE whiskey stats via correlated subqueries to avoid
    # a TOCTOU race between concurrent rating requests.
    db.flush()

    subq_avg = (
        db.query(func.avg(models.UserRating.score))
        .filter(models.UserRating.whiskey_id == whiskey_id)
        .correlate(models.Whiskey)
        .scalar_subquery()
    )
    subq_count = (
        db.query(func.count(models.UserRating.id))
        .filter(models.UserRating.whiskey_id == whiskey_id)
        .correlate(models.Whiskey)
        .scalar_subquery()
    )
    db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).update(
        {models.Whiskey.rating_avg: subq_avg, models.Whiskey.rating_count: subq_count},
        synchronize_session="fetch",
    )

    db.commit()
    db.refresh(db_rating)
    db.refresh(whiskey)

    # Evaluate badges after check-in
    from ..badges import evaluate_badges
    new_badges = evaluate_badges(current_user.username, db)

    # Fire watchlist alerts in background (doesn't affect response)
    from .watchlist import maybe_create_alert
    background_tasks.add_task(maybe_create_alert, whiskey_id)

    return schemas.CheckInResponse(
        rating=schemas.RatingRead(
            id=db_rating.id,
            user_id=db_rating.user_id,
            whiskey_id=db_rating.whiskey_id,
            score=db_rating.score,
            notes=db_rating.notes,
            serving_style=db_rating.serving_style,
            location_note=db_rating.location_note,
            image_url=f"/uploads/{db_rating.image_path}" if db_rating.image_path else None,
            created_at=db_rating.created_at,
            toast_count=0,
        ),
        new_badges=[schemas.BadgeRead.model_validate(b) for b in new_badges],
    )


@router.get("/{whiskey_id}/ratings", response_model=list[schemas.RatingRead])
def get_ratings(
    whiskey_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.whiskey_id == whiskey_id)
        .order_by(models.UserRating.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    rating_ids = [r.id for r in ratings]
    toast_counts: dict[int, int] = {}
    if rating_ids:
        counts = (
            db.query(models.Toast.rating_id, func.count(models.Toast.id))
            .filter(models.Toast.rating_id.in_(rating_ids))
            .group_by(models.Toast.rating_id)
            .all()
        )
        toast_counts = {rid: cnt for rid, cnt in counts}

    return [
        schemas.RatingRead(
            id=r.id,
            user_id=r.user_id,
            whiskey_id=r.whiskey_id,
            score=r.score,
            notes=r.notes,
            serving_style=r.serving_style,
            location_note=r.location_note,
            image_url=r.image_url,
            created_at=r.created_at,
            toast_count=toast_counts.get(r.id, 0),
        )
        for r in ratings
    ]
