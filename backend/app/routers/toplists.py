"""Top Lists — curated and dynamic whiskey rankings."""

import json
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/toplists", tags=["toplists"])


def _has_image():
    return [models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != ""]


@router.get("/", response_model=list[schemas.TopListSummary])
def list_top_lists(db: Session = Depends(get_db)):
    """Return all active top lists, ordered by display_order."""
    lists = (
        db.query(models.TopList)
        .filter(models.TopList.is_active == True)
        .order_by(models.TopList.display_order.asc())
        .all()
    )
    result = []
    for tl in lists:
        if tl.list_type == "curated":
            count = (
                db.query(func.count(models.TopListItem.id))
                .filter(models.TopListItem.list_id == tl.id)
                .scalar() or 0
            )
        else:
            count = 0
        result.append(schemas.TopListSummary(
            id=tl.id, slug=tl.slug, title=tl.title,
            description=tl.description, list_type=tl.list_type,
            category=tl.category, image_emoji=tl.image_emoji,
            item_count=count,
        ))
    return result


@router.get("/{slug}", response_model=schemas.TopListDetail)
def get_top_list(
    slug: str,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get a top list by slug. For dynamic lists, computes results on the fly."""
    tl = db.query(models.TopList).filter(models.TopList.slug == slug).first()
    if not tl:
        raise HTTPException(status_code=404, detail="Top list not found")

    if tl.list_type == "curated":
        items_db = (
            db.query(models.TopListItem)
            .filter(models.TopListItem.list_id == tl.id)
            .options(joinedload(models.TopListItem.whiskey))
            .order_by(models.TopListItem.rank.asc())
            .limit(limit)
            .all()
        )
        items = [
            schemas.TopListItemRead(
                rank=item.rank,
                whiskey=schemas.WhiskeyRead.model_validate(item.whiskey),
                note=item.note,
            )
            for item in items_db if item.whiskey
        ]
        count = (
            db.query(func.count(models.TopListItem.id))
            .filter(models.TopListItem.list_id == tl.id).scalar() or 0
        )
    else:
        items = _compute_dynamic_list(tl, db, limit)
        count = len(items)

    return schemas.TopListDetail(
        id=tl.id, slug=tl.slug, title=tl.title,
        description=tl.description, list_type=tl.list_type,
        category=tl.category, image_emoji=tl.image_emoji,
        item_count=count, items=items,
    )


def _compute_dynamic_list(
    tl: models.TopList, db: Session, limit: int
) -> list[schemas.TopListItemRead]:
    """Compute a dynamic top list based on filters_json."""
    filters = json.loads(tl.filters_json or "{}")

    q = db.query(models.Whiskey).filter(*_has_image())

    if tl.category:
        q = q.filter(models.Whiskey.category.ilike(f"%{tl.category}%"))
    if filters.get("max_price"):
        q = q.filter(models.Whiskey.price_usd <= filters["max_price"])
    if filters.get("min_price"):
        q = q.filter(models.Whiskey.price_usd >= filters["min_price"])
    if filters.get("min_rating"):
        q = q.filter(models.Whiskey.rating_avg >= filters["min_rating"])
    if filters.get("min_age"):
        q = q.filter(models.Whiskey.age >= filters["min_age"])
    if filters.get("region"):
        q = q.filter(models.Whiskey.region.ilike(f"%{filters['region']}%"))
    if filters.get("min_rating_count"):
        q = q.filter(models.Whiskey.rating_count >= filters["min_rating_count"])

    sort_key = filters.get("sort", "rating")
    if sort_key == "value":
        q = q.filter(models.Whiskey.price_usd > 0, models.Whiskey.rating_avg > 0)
        whiskeys = q.limit(limit * 5).all()
        whiskeys.sort(
            key=lambda w: w.rating_avg / math.log(max(w.price_usd, 2)),
            reverse=True,
        )
        whiskeys = whiskeys[:limit]
    elif sort_key == "price_asc":
        whiskeys = q.order_by(models.Whiskey.price_usd.asc().nullslast()).limit(limit).all()
    else:
        whiskeys = q.order_by(desc(models.Whiskey.rating_avg)).limit(limit).all()

    return [
        schemas.TopListItemRead(
            rank=i + 1,
            whiskey=schemas.WhiskeyRead.model_validate(w),
            note=None,
        )
        for i, w in enumerate(whiskeys)
    ]
