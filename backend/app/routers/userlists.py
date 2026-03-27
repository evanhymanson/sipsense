"""User-created whiskey list endpoints."""

import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..auth import get_current_user, get_optional_user
from .. import models, schemas

router = APIRouter(prefix="/userlists", tags=["user-lists"])


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def _make_unique_slug(username: str, title: str, db: Session) -> str:
    """Generate a unique slug from username + title."""
    base = f"{username}-{_slugify(title)}"
    slug = base
    counter = 2
    while db.query(models.UserList).filter(models.UserList.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _build_summary(ul: models.UserList) -> schemas.UserListSummary:
    """Build a UserListSummary from a UserList model instance."""
    items = sorted(ul.items, key=lambda i: i.position)
    preview = [
        schemas.WhiskeyRead.model_validate(item.whiskey)
        for item in items[:3]
        if item.whiskey
    ]
    return schemas.UserListSummary(
        id=ul.id,
        slug=ul.slug,
        title=ul.title,
        description=ul.description,
        is_public=ul.is_public,
        username=ul.user_id,
        item_count=len(ul.items),
        preview_whiskeys=preview,
        created_at=ul.created_at,
        updated_at=ul.updated_at,
    )


@router.post("/", response_model=schemas.UserListSummary, status_code=201)
def create_list(
    body: schemas.UserListCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new whiskey list."""
    count = (
        db.query(models.UserList)
        .filter(models.UserList.user_id == current_user.username)
        .count()
    )
    if count >= 50:
        raise HTTPException(status_code=400, detail="Maximum 50 lists per user")

    slug = _make_unique_slug(current_user.username, body.title, db)
    ul = models.UserList(
        user_id=current_user.username,
        slug=slug,
        title=body.title,
        description=body.description,
        is_public=body.is_public,
    )
    db.add(ul)
    db.flush()

    for pos, wid in enumerate(body.whiskey_ids[:100]):
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == wid).first()
        if whiskey:
            db.add(models.UserListItem(
                list_id=ul.id, whiskey_id=wid, position=pos,
            ))

    db.commit()
    db.refresh(ul)
    return _build_summary(ul)


@router.get("/", response_model=list[schemas.UserListSummary])
def browse_lists(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Browse all public lists."""
    lists = (
        db.query(models.UserList)
        .filter(models.UserList.is_public == True)
        .options(joinedload(models.UserList.items).joinedload(models.UserListItem.whiskey))
        .order_by(models.UserList.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_summary(ul) for ul in lists]


@router.get("/user/{username}", response_model=list[schemas.UserListSummary])
def get_user_lists(
    username: str,
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get all lists for a user (only public unless it\'s the owner)."""
    q = db.query(models.UserList).filter(models.UserList.user_id == username)
    if not current_user or current_user.username != username:
        q = q.filter(models.UserList.is_public == True)
    lists = (
        q.options(joinedload(models.UserList.items).joinedload(models.UserListItem.whiskey))
        .order_by(models.UserList.updated_at.desc())
        .all()
    )
    return [_build_summary(ul) for ul in lists]


@router.get("/{slug}", response_model=schemas.UserListDetail)
def get_list_detail(
    slug: str,
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get list detail with all items."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug)
        .options(joinedload(models.UserList.items).joinedload(models.UserListItem.whiskey))
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")
    if not ul.is_public and (not current_user or current_user.username != ul.user_id):
        raise HTTPException(status_code=404, detail="List not found")

    items_sorted = sorted(ul.items, key=lambda i: i.position)
    return schemas.UserListDetail(
        id=ul.id,
        slug=ul.slug,
        title=ul.title,
        description=ul.description,
        is_public=ul.is_public,
        username=ul.user_id,
        item_count=len(ul.items),
        preview_whiskeys=[],
        created_at=ul.created_at,
        updated_at=ul.updated_at,
        items=[
            schemas.UserListItemRead(
                position=item.position,
                whiskey=schemas.WhiskeyRead.model_validate(item.whiskey),
                note=item.note,
                added_at=item.added_at,
            )
            for item in items_sorted
            if item.whiskey
        ],
    )


@router.patch("/{slug}", response_model=schemas.UserListSummary)
def update_list(
    slug: str,
    body: schemas.UserListUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update list title/description (owner only)."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug, models.UserList.user_id == current_user.username)
        .options(joinedload(models.UserList.items).joinedload(models.UserListItem.whiskey))
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")

    if body.title is not None:
        ul.title = body.title
    if body.description is not None:
        ul.description = body.description
    if body.is_public is not None:
        ul.is_public = body.is_public

    db.commit()
    db.refresh(ul)
    return _build_summary(ul)


@router.delete("/{slug}", status_code=204)
def delete_list(
    slug: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a list (owner only)."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug, models.UserList.user_id == current_user.username)
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")
    db.delete(ul)
    db.commit()


@router.post("/{slug}/items", response_model=schemas.UserListItemRead, status_code=201)
def add_item(
    slug: str,
    body: schemas.UserListItemAdd,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a whiskey to a list (owner only)."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug, models.UserList.user_id == current_user.username)
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == body.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    existing = (
        db.query(models.UserListItem)
        .filter(models.UserListItem.list_id == ul.id, models.UserListItem.whiskey_id == body.whiskey_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Whiskey already in this list")

    max_pos = (
        db.query(models.UserListItem.position)
        .filter(models.UserListItem.list_id == ul.id)
        .order_by(models.UserListItem.position.desc())
        .first()
    )
    next_pos = (max_pos[0] + 1) if max_pos else 0

    item = models.UserListItem(
        list_id=ul.id,
        whiskey_id=body.whiskey_id,
        position=next_pos,
        note=body.note,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return schemas.UserListItemRead(
        position=item.position,
        whiskey=schemas.WhiskeyRead.model_validate(whiskey),
        note=item.note,
        added_at=item.added_at,
    )


@router.delete("/{slug}/items/{whiskey_id}", status_code=204)
def remove_item(
    slug: str,
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a whiskey from a list (owner only)."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug, models.UserList.user_id == current_user.username)
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")

    item = (
        db.query(models.UserListItem)
        .filter(models.UserListItem.list_id == ul.id, models.UserListItem.whiskey_id == whiskey_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()


@router.put("/{slug}/reorder")
def reorder_items(
    slug: str,
    body: schemas.UserListReorder,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reorder items in a list (owner only)."""
    ul = (
        db.query(models.UserList)
        .filter(models.UserList.slug == slug, models.UserList.user_id == current_user.username)
        .first()
    )
    if not ul:
        raise HTTPException(status_code=404, detail="List not found")

    items = {
        item.whiskey_id: item
        for item in db.query(models.UserListItem).filter(models.UserListItem.list_id == ul.id).all()
    }

    for pos, wid in enumerate(body.whiskey_ids):
        if wid in items:
            items[wid].position = pos

    db.commit()
    return {"ok": True}
