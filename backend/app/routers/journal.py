"""
Tasting journal — photo uploads for ratings and a visual timeline.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..auth import get_current_user
from ..upload_utils import validate_magic_bytes, sanitize_extension
from ..storage import is_s3_enabled, upload_bytes, make_cdn_url

router = APIRouter(tags=["journal"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "ratings"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/ratings/{rating_id}/image")
async def upload_rating_image(
    rating_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a photo for a rating."""
    rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    if rating.user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not your rating")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image too large (max 10 MB)")

    # Validate actual file content via magic bytes (not just client-provided MIME)
    detected_mime = validate_magic_bytes(content, ALLOWED_TYPES)
    if not detected_mime:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    ext = sanitize_extension(file.filename, {"jpg", "jpeg", "png", "webp"}, "jpg")
    filename = f"{rating_id}_{uuid.uuid4().hex[:8]}.{ext}"
    s3_key = f"ratings/{filename}"

    if is_s3_enabled():
        url = upload_bytes(content, s3_key, content_type=detected_mime)
    else:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / filename).write_bytes(content)
        url = f"/uploads/{s3_key}"

    rating.image_path = s3_key
    db.commit()

    return {"image_url": url}


@router.get("/journal/me")
def get_my_journal(
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=200),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's ratings as a visual timeline (paginated)."""
    base_q = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == current_user.username)
    )
    total = base_q.count()
    ratings = (
        base_q
        .options(joinedload(models.UserRating.whiskey))
        .order_by(models.UserRating.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    entries = []
    for r in ratings:
        image_url = make_cdn_url(f"/uploads/{r.image_path}") if r.image_path else None
        entries.append({
            "id": r.id,
            "score": r.score,
            "notes": r.notes,
            "serving_style": r.serving_style,
            "location_note": r.location_note,
            "image_url": image_url,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "whiskey": {
                "id": r.whiskey.id,
                "name": r.whiskey.name,
                "distillery": r.whiskey.distillery,
                "category": r.whiskey.category,
                "price_usd": r.whiskey.price_usd,
                "rating_avg": r.whiskey.rating_avg,
                "flavor_profile": r.whiskey.flavor_profile,
                "image_url": r.whiskey.image_url,
                "abv": r.whiskey.abv,
                "age": r.whiskey.age,
                "region": r.whiskey.region,
                "rating_count": r.whiskey.rating_count,
            } if r.whiskey else None,
        })

    return {"entries": entries, "total": total, "has_more": len(entries) == limit}
