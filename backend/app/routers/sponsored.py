"""
Sponsored content — serve and track paid placements for whiskey brands.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/sponsored", tags=["sponsored"])


def _active_filter(query):
    """Filter to only active, in-window placements."""
    now = datetime.now(timezone.utc)
    return query.filter(
        models.SponsoredPlacement.is_active == True,
        (models.SponsoredPlacement.starts_at == None) | (models.SponsoredPlacement.starts_at <= now),
        (models.SponsoredPlacement.ends_at == None) | (models.SponsoredPlacement.ends_at >= now),
    )


@router.get("/{placement_type}", response_model=list[schemas.SponsoredPlacementRead])
def get_placements(
    placement_type: str,
    limit: int = Query(3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Get active sponsored placements for a given slot type (feed, browse, video_slot, search)."""
    query = (
        db.query(models.SponsoredPlacement)
        .options(joinedload(models.SponsoredPlacement.whiskey))
        .filter(models.SponsoredPlacement.placement_type == placement_type)
    )
    query = _active_filter(query)
    placements = (
        query.order_by(models.SponsoredPlacement.priority.desc())
        .limit(limit)
        .all()
    )

    results = []
    for p in placements:
        read = schemas.SponsoredPlacementRead(
            id=p.id,
            advertiser_name=p.advertiser_name,
            whiskey_id=p.whiskey_id,
            placement_type=p.placement_type,
            title=p.title,
            description=p.description,
            image_url=p.image_url,
            link_url=p.link_url,
            whiskey=schemas.WhiskeyRead.model_validate(p.whiskey) if p.whiskey else None,
        )
        results.append(read)

    return results


@router.post("/{placement_id}/impression")
def record_impression(
    placement_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record an ad impression (requires auth to prevent manipulation)."""
    p = db.query(models.SponsoredPlacement).filter(
        models.SponsoredPlacement.id == placement_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Placement not found")

    db.query(models.SponsoredPlacement).filter(
        models.SponsoredPlacement.id == placement_id
    ).update({"impression_count": func.coalesce(models.SponsoredPlacement.impression_count, 0) + 1})
    db.commit()
    return {"status": "recorded"}


@router.post("/{placement_id}/click")
def record_click(
    placement_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record an ad click (requires auth to prevent manipulation)."""
    p = db.query(models.SponsoredPlacement).filter(
        models.SponsoredPlacement.id == placement_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Placement not found")

    db.query(models.SponsoredPlacement).filter(
        models.SponsoredPlacement.id == placement_id
    ).update({"click_count": func.coalesce(models.SponsoredPlacement.click_count, 0) + 1})
    db.commit()
    return {"status": "recorded"}
