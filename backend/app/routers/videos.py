"""
Short-form video feed: upload, browse, toast, and comment on whiskey videos.
"""
import uuid
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import func as sqlfunc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, get_optional_user
from ..upload_utils import validate_magic_bytes, sanitize_extension
from ..track import track_action
from ..analytics_constants import ACTION_VIDEO_WATCH

router = APIRouter(prefix="/videos", tags=["videos"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "videos"
THUMB_DIR = UPLOAD_DIR / "thumbs"
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


def _generate_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    """Extract a single frame from the video at 1s using ffmpeg."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", "scale=360:-1",
                str(thumb_path),
            ],
            capture_output=True,
            timeout=30,
        )
        return thumb_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _get_duration(video_path: Path) -> Optional[float]:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else None
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return None


def _build_video_read(
    video: models.Video,
    toast_count: int = 0,
    comment_count: int = 0,
    user_toasted: bool = False,
) -> schemas.VideoRead:
    """Convert a Video model instance to a VideoRead schema."""
    return schemas.VideoRead(
        id=video.id,
        user_id=video.user_id,
        title=video.title,
        description=video.description,
        video_url=f"/uploads/{video.video_path}",
        thumbnail_url=f"/uploads/{video.thumbnail_path}" if video.thumbnail_path else None,
        duration_seconds=video.duration_seconds,
        whiskey_id=video.whiskey_id,
        whiskey_name=video.whiskey.name if video.whiskey else None,
        whiskey_image_url=video.whiskey.image_url if video.whiskey else None,
        location_name=video.location_name,
        price_tag=video.price_tag,
        view_count=video.view_count,
        toast_count=toast_count,
        comment_count=comment_count,
        user_toasted=user_toasted,
        is_sponsored=video.is_sponsored,
        sponsor_label=video.sponsor_label,
        created_at=video.created_at,
    )


def _batch_load_engagement(
    db: Session,
    video_ids: list[int],
    current_username: Optional[str],
) -> tuple[dict[int, int], dict[int, int], set[int]]:
    """Batch-load toast counts, comment counts, and user toast status."""
    toast_counts: dict[int, int] = {}
    comment_counts: dict[int, int] = {}
    user_toasts: set[int] = set()

    if not video_ids:
        return toast_counts, comment_counts, user_toasts

    # Toast counts
    rows = (
        db.query(models.VideoToast.video_id, sqlfunc.count(models.VideoToast.id))
        .filter(models.VideoToast.video_id.in_(video_ids))
        .group_by(models.VideoToast.video_id)
        .all()
    )
    toast_counts = {vid: cnt for vid, cnt in rows}

    # Comment counts
    rows = (
        db.query(models.VideoComment.video_id, sqlfunc.count(models.VideoComment.id))
        .filter(models.VideoComment.video_id.in_(video_ids))
        .group_by(models.VideoComment.video_id)
        .all()
    )
    comment_counts = {vid: cnt for vid, cnt in rows}

    # User's own toasts
    if current_username:
        user_toast_rows = (
            db.query(models.VideoToast.video_id)
            .filter(
                models.VideoToast.video_id.in_(video_ids),
                models.VideoToast.user_id == current_username,
            )
            .all()
        )
        user_toasts = {row[0] for row in user_toast_rows}

    return toast_counts, comment_counts, user_toasts


# ── Upload ───────────────────────────────────────────────────────────────


@router.post("/upload", response_model=schemas.VideoRead)
async def upload_video(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    whiskey_id: Optional[int] = Form(None),
    location_name: Optional[str] = Form(None),
    price_tag: Optional[float] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a short-form video."""
    content = await file.read()
    if len(content) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=400, detail="Video too large (max 100 MB)")

    # Validate actual file content via magic bytes (not just client-provided MIME)
    if not validate_magic_bytes(content, ALLOWED_VIDEO_TYPES):
        raise HTTPException(status_code=400, detail="Only MP4, MOV, and WebM videos are allowed")

    # Validate whiskey exists if tagged
    if whiskey_id is not None:
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
        if not whiskey:
            raise HTTPException(status_code=404, detail="Whiskey not found")

    ext = sanitize_extension(file.filename, {"mp4", "mov", "webm"}, "mp4")
    uid = uuid.uuid4().hex[:12]
    filename = f"{uid}.{ext}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    video_file = UPLOAD_DIR / filename
    video_file.write_bytes(content)

    # Generate thumbnail
    thumb_filename = f"{uid}.jpg"
    thumb_file = THUMB_DIR / thumb_filename
    has_thumb = _generate_thumbnail(video_file, thumb_file)

    # Get duration
    duration = _get_duration(video_file)

    video = models.Video(
        user_id=current_user.username,
        title=title,
        description=description,
        video_path=f"videos/{filename}",
        thumbnail_path=f"videos/thumbs/{thumb_filename}" if has_thumb else None,
        duration_seconds=duration,
        whiskey_id=whiskey_id,
        location_name=location_name,
        price_tag=price_tag,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # Eager-load whiskey for the response
    if whiskey_id:
        db.refresh(video, ["whiskey"])

    return _build_video_read(video)


# ── Feed ─────────────────────────────────────────────────────────────────


@router.get("/feed", response_model=schemas.VideoFeedResponse)
def get_video_feed(
    following_only: bool = Query(False),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, le=10000),
    limit: int = Query(10, ge=1, le=30),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Paginated video feed, newest first."""
    query = (
        db.query(models.Video)
        .options(joinedload(models.Video.whiskey))
        .filter(models.Video.status == "active")
        .order_by(models.Video.created_at.desc())
    )

    if following_only and current_user:
        following_ids = select(models.Follow.following_id).where(
            models.Follow.follower_id == current_user.username
        )
        query = query.filter(models.Video.user_id.in_(following_ids))

    if category:
        cat_safe = category.replace("%", "\\%").replace("_", "\\_")
        query = query.join(models.Whiskey).filter(
            models.Whiskey.category.ilike(f"%{cat_safe}%")
        )

    videos = query.offset(skip).limit(limit + 1).all()
    has_more = len(videos) > limit
    videos = videos[:limit]

    video_ids = [v.id for v in videos]
    username = current_user.username if current_user else None
    toast_counts, comment_counts, user_toasts = _batch_load_engagement(db, video_ids, username)

    items = [
        _build_video_read(
            v,
            toast_count=toast_counts.get(v.id, 0),
            comment_count=comment_counts.get(v.id, 0),
            user_toasted=v.id in user_toasts,
        )
        for v in videos
    ]

    return schemas.VideoFeedResponse(items=items, has_more=has_more)


# ── Single video ─────────────────────────────────────────────────────────


@router.get("/{video_id}", response_model=schemas.VideoRead)
def get_video(
    video_id: int,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    video = (
        db.query(models.Video)
        .options(joinedload(models.Video.whiskey))
        .filter(models.Video.id == video_id, models.Video.status == "active")
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    toast_counts, comment_counts, user_toasts = _batch_load_engagement(
        db, [video.id], current_user.username if current_user else None
    )

    return _build_video_read(
        video,
        toast_count=toast_counts.get(video.id, 0),
        comment_count=comment_counts.get(video.id, 0),
        user_toasted=video.id in user_toasts,
    )


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(models.Video).filter(models.Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not your video")

    video.status = "removed"
    db.commit()


# ── View count ───────────────────────────────────────────────────────────


@router.post("/{video_id}/view")
def record_view(
    video_id: int,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id, models.Video.status == "active"
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db.query(models.Video).filter(models.Video.id == video_id).update(
        {"view_count": models.Video.view_count + 1},
        synchronize_session="fetch",
    )
    if current_user:
        track_action(db, current_user.username, ACTION_VIDEO_WATCH,
                     whiskey_id=video.whiskey_id, detail={"video_id": video_id})
    db.commit()
    db.refresh(video)
    return {"view_count": video.view_count}


# ── Toast (like) ─────────────────────────────────────────────────────────


@router.post("/{video_id}/toast", status_code=201)
def toast_video(
    video_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id, models.Video.status == "active"
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    toast = models.VideoToast(user_id=current_user.username, video_id=video_id)
    db.add(toast)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "already_toasted"}
    return {"status": "toasted"}


@router.delete("/{video_id}/toast", status_code=204)
def untoast_video(
    video_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    toast = db.query(models.VideoToast).filter(
        models.VideoToast.user_id == current_user.username,
        models.VideoToast.video_id == video_id,
    ).first()
    if not toast:
        raise HTTPException(status_code=404, detail="Toast not found")

    db.delete(toast)
    db.commit()


# ── Comments ─────────────────────────────────────────────────────────────


@router.post("/{video_id}/comment", response_model=schemas.VideoCommentRead, status_code=201)
def add_comment(
    video_id: int,
    body: schemas.VideoCommentCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(models.Video).filter(
        models.Video.id == video_id, models.Video.status == "active"
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    comment = models.VideoComment(
        user_id=current_user.username,
        video_id=video_id,
        text=body.text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(models.VideoComment).filter(
        models.VideoComment.id == comment_id
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.username:
        raise HTTPException(status_code=403, detail="Not your comment")

    db.delete(comment)
    db.commit()


@router.get("/{video_id}/comments", response_model=list[schemas.VideoCommentRead])
def get_comments(
    video_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.VideoComment)
        .filter(models.VideoComment.video_id == video_id)
        .order_by(models.VideoComment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ── User's videos ────────────────────────────────────────────────────────


@router.get("/user/{username}", response_model=schemas.VideoFeedResponse)
def get_user_videos(
    username: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Video)
        .options(joinedload(models.Video.whiskey))
        .filter(models.Video.user_id == username, models.Video.status == "active")
        .order_by(models.Video.created_at.desc())
    )

    videos = query.offset(skip).limit(limit + 1).all()
    has_more = len(videos) > limit
    videos = videos[:limit]

    video_ids = [v.id for v in videos]
    uname = current_user.username if current_user else None
    toast_counts, comment_counts, user_toasts = _batch_load_engagement(db, video_ids, uname)

    items = [
        _build_video_read(v, toast_counts.get(v.id, 0), comment_counts.get(v.id, 0), v.id in user_toasts)
        for v in videos
    ]

    return schemas.VideoFeedResponse(items=items, has_more=has_more)


# ── Videos for a whiskey ─────────────────────────────────────────────────


@router.get("/whiskey/{whiskey_id}", response_model=schemas.VideoFeedResponse)
def get_whiskey_videos(
    whiskey_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=30),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.Video)
        .options(joinedload(models.Video.whiskey))
        .filter(models.Video.whiskey_id == whiskey_id, models.Video.status == "active")
        .order_by(models.Video.created_at.desc())
    )

    videos = query.offset(skip).limit(limit + 1).all()
    has_more = len(videos) > limit
    videos = videos[:limit]

    video_ids = [v.id for v in videos]
    uname = current_user.username if current_user else None
    toast_counts, comment_counts, user_toasts = _batch_load_engagement(db, video_ids, uname)

    items = [
        _build_video_read(v, toast_counts.get(v.id, 0), comment_counts.get(v.id, 0), v.id in user_toasts)
        for v in videos
    ]

    return schemas.VideoFeedResponse(items=items, has_more=has_more)
