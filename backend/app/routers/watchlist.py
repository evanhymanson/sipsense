"""
Watchlist & in-app alerts — users watch whiskeys and receive notifications
when a watched bottle has new community activity.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# How many new ratings on a watched whiskey trigger an alert
ALERT_RATING_THRESHOLD = 3


# ── Watch / Unwatch ───────────────────────────────────────────────────────

@router.post("/{whiskey_id}", status_code=201)
def watch_whiskey(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    item = models.WatchlistItem(username=current_user.username, whiskey_id=whiskey_id)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # already watching — idempotent
    return {"watching": True, "whiskey_id": whiskey_id}


@router.delete("/{whiskey_id}")
def unwatch_whiskey(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(models.WatchlistItem)
        .filter(
            models.WatchlistItem.username == current_user.username,
            models.WatchlistItem.whiskey_id == whiskey_id,
        )
        .first()
    )
    if item:
        db.delete(item)
        db.commit()
    return {"watching": False, "whiskey_id": whiskey_id}


@router.get("/status/{whiskey_id}")
def watch_status(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watching = (
        db.query(models.WatchlistItem)
        .filter(
            models.WatchlistItem.username == current_user.username,
            models.WatchlistItem.whiskey_id == whiskey_id,
        )
        .first()
        is not None
    )
    return {"watching": watching}


# ── My Watchlist ──────────────────────────────────────────────────────────

@router.get("/", response_model=list[schemas.WatchlistItemRead])
def get_my_watchlist(
    current_user: models.User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items = (
        db.query(models.WatchlistItem)
        .options(joinedload(models.WatchlistItem.whiskey))
        .filter(models.WatchlistItem.username == current_user.username)
        .order_by(models.WatchlistItem.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        schemas.WatchlistItemRead(
            id=item.id,
            whiskey_id=item.whiskey_id,
            whiskey_name=item.whiskey.name if item.whiskey else "Unknown",
            created_at=item.created_at,
        )
        for item in items
    ]


# ── Alerts ────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=list[schemas.WatchlistAlertRead])
def get_my_alerts(
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=200),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerts = (
        db.query(models.WatchlistAlert)
        .options(joinedload(models.WatchlistAlert.whiskey))
        .filter(models.WatchlistAlert.username == current_user.username)
        .order_by(models.WatchlistAlert.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        schemas.WatchlistAlertRead(
            id=a.id,
            alert_type=a.alert_type or "watchlist",
            whiskey_id=a.whiskey_id,
            whiskey_name=a.whiskey.name if a.whiskey else None,
            from_username=a.from_username,
            message=a.message,
            is_read=a.is_read,
            created_at=a.created_at,
        )
        for a in alerts
    ]


@router.get("/alerts/unread-count")
def get_unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.WatchlistAlert)
        .filter(
            models.WatchlistAlert.username == current_user.username,
            models.WatchlistAlert.is_read.is_(False),
        )
        .count()
    )
    return {"count": count}


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = (
        db.query(models.WatchlistAlert)
        .filter(
            models.WatchlistAlert.id == alert_id,
            models.WatchlistAlert.username == current_user.username,
        )
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/alerts/read-all")
def mark_all_alerts_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.WatchlistAlert).filter(
        models.WatchlistAlert.username == current_user.username,
        models.WatchlistAlert.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ── Alert generation helper (called from rating endpoint) ─────────────────

def maybe_create_alert(whiskey_id: int):
    """
    Check if a whiskey being rated should trigger watchlist alerts.
    Called as a background task after a new rating is saved.
    Creates its own DB session since the request session is closed by this point.
    """
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
        if not whiskey:
            return

        # Only fire at threshold multiples (3, 6, 9, ... ratings)
        count = whiskey.rating_count or 0
        if count == 0 or count % ALERT_RATING_THRESHOLD != 0:
            return

        watchers = (
            db.query(models.WatchlistItem)
            .filter(models.WatchlistItem.whiskey_id == whiskey_id)
            .all()
        )
        if not watchers:
            return

        # Proper ordinal suffix
        if count % 100 in (11, 12, 13):
            suffix = "th"
        elif count % 10 == 1:
            suffix = "st"
        elif count % 10 == 2:
            suffix = "nd"
        elif count % 10 == 3:
            suffix = "rd"
        else:
            suffix = "th"
        message = f"{whiskey.name} just received its {count}{suffix} rating on SipSense!"

        for watcher in watchers:
            alert = models.WatchlistAlert(
                username=watcher.username,
                whiskey_id=whiskey_id,
                message=message,
            )
            db.add(alert)
        db.commit()
    finally:
        db.close()
