"""
Collection tracking ("My Shelf") — track bottles owned, opened, and finished.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

from .. import models
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/collection", tags=["collection"])


# ── Schemas ──────────────────────────────────────────────────────────────

class CollectionItemCreate(BaseModel):
    whiskey_id: int
    status: Literal["sealed", "opened", "finished"] = "sealed"
    purchase_price: Optional[float] = None
    purchase_location: Optional[str] = None
    personal_notes: Optional[str] = None


class CollectionItemUpdate(BaseModel):
    status: Optional[Literal["sealed", "opened", "finished"]] = None
    purchase_price: Optional[float] = None
    purchase_location: Optional[str] = None
    personal_notes: Optional[str] = None


class CollectionItemRead(BaseModel):
    id: int
    whiskey_id: int
    status: str
    purchase_price: Optional[float]
    purchase_location: Optional[str]
    personal_notes: Optional[str]
    added_at: datetime | None = None
    whiskey: Optional[dict] = None

    model_config = {"from_attributes": True}


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/")
def get_my_collection(
    status: Optional[str] = Query(None, description="Filter by status: sealed, opened, finished"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all bottles in the user's collection."""
    user_id = current_user.username
    q = db.query(models.CollectionItem).filter(models.CollectionItem.user_id == user_id)
    if status:
        q = q.filter(models.CollectionItem.status == status)
    items = q.order_by(models.CollectionItem.added_at.desc()).all()

    # Batch-fetch whiskey data
    whiskey_ids = [item.whiskey_id for item in items]
    whiskeys = (
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()
        if whiskey_ids else []
    )
    whiskey_map = {w.id: w for w in whiskeys}

    result = []
    for item in items:
        w = whiskey_map.get(item.whiskey_id)
        result.append({
            "id": item.id,
            "whiskey_id": item.whiskey_id,
            "status": item.status,
            "purchase_price": item.purchase_price,
            "purchase_location": item.purchase_location,
            "personal_notes": item.personal_notes,
            "added_at": item.added_at.isoformat() if item.added_at else None,
            "whiskey": {
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
            } if w else None,
        })

    return result


@router.get("/stats")
def get_collection_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Summary stats for the user's collection."""
    user_id = current_user.username
    items = db.query(models.CollectionItem).filter(models.CollectionItem.user_id == user_id).all()

    sealed = sum(1 for i in items if i.status == "sealed")
    opened = sum(1 for i in items if i.status == "opened")
    finished = sum(1 for i in items if i.status == "finished")
    prices = [i.purchase_price for i in items if i.purchase_price]

    return {
        "total": len(items),
        "sealed": sealed,
        "opened": opened,
        "finished": finished,
        "total_spent": round(sum(prices), 2) if prices else 0,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
    }


@router.post("/", status_code=201)
def add_to_collection(
    item: CollectionItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a bottle to the user's collection."""
    # Verify whiskey exists
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == item.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    db_item = models.CollectionItem(
        user_id=current_user.username,
        whiskey_id=item.whiskey_id,
        status=item.status,
        purchase_price=item.purchase_price,
        purchase_location=item.purchase_location,
        personal_notes=item.personal_notes,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"id": db_item.id, "status": "added"}


@router.patch("/{item_id}")
def update_collection_item(
    item_id: int,
    update: CollectionItemUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a collection item (e.g., mark as opened or finished)."""
    item = db.query(models.CollectionItem).filter(
        and_(models.CollectionItem.id == item_id, models.CollectionItem.user_id == current_user.username)
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Collection item not found")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    return {"id": item.id, "status": item.status}


@router.delete("/{item_id}", status_code=204)
def remove_from_collection(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a bottle from the collection."""
    item = db.query(models.CollectionItem).filter(
        and_(models.CollectionItem.id == item_id, models.CollectionItem.user_id == current_user.username)
    ).first()
    if item:
        db.delete(item)
        db.commit()
