"""
Admin API — protected endpoints for managing whiskey data.

PATCH /admin/whiskeys/{whiskey_id}       — update a single whiskey
POST  /admin/whiskeys/batch-clear-images — clear image_url for a list of IDs
"""

import os
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

_ADMIN_USERS = {
    u.strip() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()
}


def _require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.username not in _ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.patch("/whiskeys/{whiskey_id}")
def update_whiskey(
    whiskey_id: int,
    update: schemas.WhiskeyAdminUpdate,
    admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    changes = update.model_dump(exclude_unset=True)

    # Treat empty string as NULL for image_url
    if "image_url" in changes and changes["image_url"] == "":
        changes["image_url"] = None

    for key, value in changes.items():
        setattr(whiskey, key, value)

    db.commit()
    db.refresh(whiskey)

    logger.info("Admin %s updated whiskey %d: %s", admin.username, whiskey_id, list(changes.keys()))
    return {"id": whiskey.id, "name": whiskey.name, "updated_fields": list(changes.keys())}


@router.post("/whiskeys/batch-clear-images")
def batch_clear_images(
    payload: schemas.WhiskeyBatchClearImages,
    admin: models.User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    updated = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.id.in_(payload.whiskey_ids))
        .update({models.Whiskey.image_url: None}, synchronize_session="fetch")
    )
    db.commit()

    logger.info("Admin %s cleared images for %d whiskeys: %s", admin.username, updated, payload.whiskey_ids)
    return {"cleared_count": updated, "whiskey_ids": payload.whiskey_ids}
