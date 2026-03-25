from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Whiskey

router = APIRouter(prefix="/compare", tags=["compare"])


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
        "description": w.description,
        "flavor_profile": w.flavor_profile,
        "rating_avg": w.rating_avg,
        "rating_count": w.rating_count,
    }


@router.get("/")
def compare_bottles(id_a: int, id_b: int, db: Session = Depends(get_db)):
    """Return full details for two whiskeys to display side-by-side."""
    a = db.query(Whiskey).filter(Whiskey.id == id_a).first()
    b = db.query(Whiskey).filter(Whiskey.id == id_b).first()

    if not a:
        raise HTTPException(status_code=404, detail=f"Whiskey with id {id_a} not found")
    if not b:
        raise HTTPException(status_code=404, detail=f"Whiskey with id {id_b} not found")

    return {"a": _whiskey_dict(a), "b": _whiskey_dict(b)}
