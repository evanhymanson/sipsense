"""
Price alerts — users subscribe to price-drop notifications for whiskeys.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/price-alerts", tags=["price-alerts"])


@router.post("/", status_code=201, response_model=schemas.PriceAlertRead)
def create_price_alert(
    body: schemas.PriceAlertCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Subscribe to price-drop alerts for a whiskey."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == body.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    alert = models.PriceAlert(
        username=current_user.username,
        whiskey_id=body.whiskey_id,
        target_price=body.target_price,
        original_price=whiskey.price_usd,
    )
    db.add(alert)
    try:
        db.commit()
        db.refresh(alert)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Already watching this price")

    return schemas.PriceAlertRead(
        id=alert.id,
        whiskey_id=alert.whiskey_id,
        whiskey_name=whiskey.name,
        target_price=alert.target_price,
        original_price=alert.original_price,
        triggered=alert.triggered,
        created_at=alert.created_at,
    )


@router.get("/", response_model=list[schemas.PriceAlertRead])
def get_my_alerts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all of the current user's price alerts."""
    alerts = (
        db.query(models.PriceAlert)
        .filter(models.PriceAlert.username == current_user.username)
        .order_by(models.PriceAlert.created_at.desc())
        .all()
    )
    result = []
    for a in alerts:
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == a.whiskey_id).first()
        result.append(schemas.PriceAlertRead(
            id=a.id,
            whiskey_id=a.whiskey_id,
            whiskey_name=whiskey.name if whiskey else "Unknown",
            target_price=a.target_price,
            original_price=a.original_price,
            triggered=a.triggered,
            created_at=a.created_at,
        ))
    return result


@router.get("/status/{whiskey_id}")
def get_alert_status(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if the user has an active price alert for a whiskey."""
    alert = (
        db.query(models.PriceAlert)
        .filter(
            models.PriceAlert.username == current_user.username,
            models.PriceAlert.whiskey_id == whiskey_id,
        )
        .first()
    )
    return {
        "has_alert": alert is not None,
        "target_price": alert.target_price if alert else None,
    }


@router.delete("/{whiskey_id}")
def remove_price_alert(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a price alert for a whiskey."""
    alert = (
        db.query(models.PriceAlert)
        .filter(
            models.PriceAlert.username == current_user.username,
            models.PriceAlert.whiskey_id == whiskey_id,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="No price alert found")
    db.delete(alert)
    db.commit()
    return {"removed": True}
