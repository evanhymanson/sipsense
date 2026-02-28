import os
import math
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whiskeys", tags=["whiskeys"])

_SORT_OPTIONS = {"rating", "price_asc", "price_desc", "age", "name"}


@router.get("/", response_model=list[schemas.WhiskeyRead])
def list_whiskeys(
    q: Optional[str] = Query(None, description="Search by name or distillery"),
    category: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    flavor: Optional[str] = Query(None, description="Filter by flavor tag in flavor_profile"),
    min_abv: Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    sort_by: str = Query("rating", description="rating | price_asc | price_desc | age | name"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(models.Whiskey)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            models.Whiskey.name.ilike(pattern) | models.Whiskey.distillery.ilike(pattern)
        )
    if category:
        query = query.filter(models.Whiskey.category.ilike(f"%{category}%"))
    if region:
        query = query.filter(models.Whiskey.region.ilike(f"%{region}%"))
    if flavor:
        query = query.filter(models.Whiskey.flavor_profile.ilike(f"%{flavor}%"))
    if min_abv is not None:
        query = query.filter(models.Whiskey.abv >= min_abv)
    if min_price is not None:
        query = query.filter(models.Whiskey.price_usd >= min_price)
    if max_price is not None:
        query = query.filter(models.Whiskey.price_usd <= max_price)

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

    return query.offset(skip).limit(limit).all()


@router.get("/{whiskey_id}/similar", response_model=list[schemas.WhiskeyRead])
def get_similar(whiskey_id: int, top_n: int = 5, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")
    from ..ml.recommender import similar_whiskeys
    results = similar_whiskeys(whiskey, db, top_n=top_n)
    return [w for w, _ in results]


@router.get("/{whiskey_id}/blurb")
def get_blurb(whiskey_id: int, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Return cached description only if it's complete (not a truncated scrape)
    desc = (whiskey.description or "").strip()
    if desc and not desc.endswith(("...", "…", "read more", "Read more")):
        return {"blurb": desc}

    # Try Claude API if key is set
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"blurb": None, "status": "no_key"}

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
            f"\nAlso return a comma-separated list of 3-6 flavor tags that best describe this whiskey "
            f"(e.g. vanilla, oak, caramel, smoky, fruity, spicy).\n"
            f"Format your response exactly as:\n"
            f"DESCRIPTION: <2-3 sentences>\n"
            f"FLAVORS: <comma-separated tags>"
        )
        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Parse structured response
        blurb = raw
        flavors = None
        if "DESCRIPTION:" in raw and "FLAVORS:" in raw:
            parts = raw.split("FLAVORS:")
            blurb = parts[0].replace("DESCRIPTION:", "").strip()
            flavors = parts[1].strip()

        # Cache in DB — infer flavor profile only if none exists yet
        whiskey.description = blurb
        if flavors and not whiskey.flavor_profile:
            whiskey.flavor_profile = flavors
        db.commit()

        return {"blurb": blurb, "status": "generated"}
    except Exception as e:
        logger.error("Blurb generation failed for whiskey %d: %s", whiskey_id, e)
        return {"blurb": None, "status": "error"}


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
            models.Whiskey.price_usd.isnot(None),
            models.Whiskey.price_usd > 0,
            models.Whiskey.rating_avg.isnot(None),
            models.Whiskey.rating_avg > 0,
        )
    )
    if category:
        q = q.filter(models.Whiskey.category.ilike(f"%{category}%"))
    if region:
        q = q.filter(models.Whiskey.region.ilike(f"%{region}%"))
    q = q.filter(models.Whiskey.price_usd <= max_price)

    all_results = q.all()
    scored = sorted(
        all_results,
        key=lambda w: w.rating_avg / math.log(max(w.price_usd, 2)),
        reverse=True,
    )
    return scored[:limit]


@router.get("/{whiskey_id}", response_model=schemas.WhiskeyRead)
def get_whiskey(whiskey_id: int, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")
    return whiskey


@router.post("/", response_model=schemas.WhiskeyRead, status_code=201)
def create_whiskey(whiskey: schemas.WhiskeyCreate, db: Session = Depends(get_db)):
    db_whiskey = models.Whiskey(**whiskey.model_dump())
    db.add(db_whiskey)
    db.commit()
    db.refresh(db_whiskey)
    return db_whiskey


@router.post("/{whiskey_id}/rate", response_model=schemas.CheckInResponse)
def rate_whiskey(
    whiskey_id: int,
    rating: schemas.RatingCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Use the authenticated user's username as user_id
    rating_data = rating.model_dump()
    rating_data["user_id"] = current_user.username
    db_rating = models.UserRating(whiskey_id=whiskey_id, **rating_data)
    db.add(db_rating)

    all_scores = [r.score for r in whiskey.ratings] + [rating.score]
    whiskey.rating_avg = sum(all_scores) / len(all_scores)
    whiskey.rating_count = len(all_scores)

    db.commit()
    db.refresh(db_rating)

    # Evaluate badges after check-in
    from ..badges import evaluate_badges
    new_badges = evaluate_badges(current_user.username, db)

    return schemas.CheckInResponse(
        rating=schemas.RatingRead(
            id=db_rating.id,
            user_id=db_rating.user_id,
            whiskey_id=db_rating.whiskey_id,
            score=db_rating.score,
            notes=db_rating.notes,
            serving_style=db_rating.serving_style,
            location_note=db_rating.location_note,
            created_at=db_rating.created_at,
            toast_count=0,
        ),
        new_badges=[schemas.BadgeRead.model_validate(b) for b in new_badges],
    )


@router.get("/{whiskey_id}/ratings", response_model=list[schemas.RatingRead])
def get_ratings(whiskey_id: int, db: Session = Depends(get_db)):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")
    return whiskey.ratings
