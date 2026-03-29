"""Gap 11: Annual community awards — top-rated whiskeys voted by the community."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user, get_optional_user

router = APIRouter(prefix="/awards", tags=["awards"])

AWARD_CATEGORIES = [
    {
        "slug": "best-bourbon",
        "title": "Best Bourbon",
        "description": "The community's top-rated bourbon of the year.",
        "emoji": "\U0001f3c6",
        "category_filter": "bourbon",
    },
    {
        "slug": "best-scotch",
        "title": "Best Scotch",
        "description": "The finest Scotch whisky as voted by the community.",
        "emoji": "\U0001f3c5",
        "category_filter": "scotch",
    },
    {
        "slug": "best-irish",
        "title": "Best Irish Whiskey",
        "description": "Ireland's finest, chosen by SipSense drinkers.",
        "emoji": "\u2618\ufe0f",
        "category_filter": "irish",
    },
    {
        "slug": "best-japanese",
        "title": "Best Japanese Whisky",
        "description": "The top Japanese whisky of the year.",
        "emoji": "\U0001f1ef\U0001f1f5",
        "category_filter": "japanese",
    },
    {
        "slug": "best-rye",
        "title": "Best Rye Whiskey",
        "description": "The spiciest and best rye, community-voted.",
        "emoji": "\U0001f336\ufe0f",
        "category_filter": "rye",
    },
    {
        "slug": "best-value",
        "title": "Best Value Under $50",
        "description": "Outstanding whiskey that won't break the bank.",
        "emoji": "\U0001f4b0",
        "category_filter": None,
        "price_max": 50,
    },
    {
        "slug": "best-newcomer",
        "title": "Best New Discovery",
        "description": "A bottle that surprised and delighted the community this year.",
        "emoji": "\u2b50",
        "category_filter": None,
    },
    {
        "slug": "peoples-choice",
        "title": "People's Choice",
        "description": "The overall community favorite across all categories.",
        "emoji": "\U0001f451",
        "category_filter": None,
    },
]


@router.get("/categories")
def list_award_categories():
    """Return all award category definitions."""
    return [
        schemas.AwardCategoryRead(
            slug=c["slug"],
            title=c["title"],
            description=c["description"],
            emoji=c["emoji"],
        )
        for c in AWARD_CATEGORIES
    ]


@router.get("/{year}")
def get_awards_for_year(
    year: int,
    db: Session = Depends(get_db),
):
    """Return all award results for a given year."""
    awards = (
        db.query(models.CommunityAward)
        .filter(models.CommunityAward.year == year)
        .order_by(models.CommunityAward.category_slug, models.CommunityAward.rank)
        .all()
    )

    # Group by category
    results = {}
    for award in awards:
        cat_slug = award.category_slug
        if cat_slug not in results:
            cat_def = next((c for c in AWARD_CATEGORIES if c["slug"] == cat_slug), None)
            results[cat_slug] = {
                "slug": cat_slug,
                "title": cat_def["title"] if cat_def else cat_slug,
                "description": cat_def["description"] if cat_def else "",
                "emoji": cat_def["emoji"] if cat_def else "\U0001f3c6",
                "winners": [],
            }
        results[cat_slug]["winners"].append({
            "rank": award.rank,
            "whiskey": schemas.WhiskeyRead.model_validate(award.whiskey),
            "vote_count": award.vote_count,
        })

    return list(results.values())


@router.get("/{year}/{category_slug}/nominees")
def get_nominees(
    year: int,
    category_slug: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return top-rated whiskeys eligible for nomination in a category."""
    cat = next((c for c in AWARD_CATEGORIES if c["slug"] == category_slug), None)
    if not cat:
        raise HTTPException(status_code=404, detail="Award category not found")

    q = db.query(models.Whiskey).filter(models.Whiskey.rating_count >= 1)

    if cat.get("category_filter"):
        q = q.filter(models.Whiskey.category.ilike(f"%{cat['category_filter']}%"))
    if cat.get("price_max"):
        q = q.filter(models.Whiskey.price_usd <= cat["price_max"])

    whiskeys = q.order_by(models.Whiskey.rating_avg.desc()).limit(limit).all()

    # Get existing vote counts for this year/category
    vote_counts = dict(
        db.query(models.CommunityVote.whiskey_id, sqlfunc.count(models.CommunityVote.id))
        .filter(
            models.CommunityVote.year == year,
            models.CommunityVote.category_slug == category_slug,
        )
        .group_by(models.CommunityVote.whiskey_id)
        .all()
    )

    return [
        {
            "whiskey": schemas.WhiskeyRead.model_validate(w),
            "vote_count": vote_counts.get(w.id, 0),
        }
        for w in whiskeys
    ]


@router.post("/{year}/{category_slug}/vote", status_code=201)
def cast_vote(
    year: int,
    category_slug: str,
    body: schemas.VoteCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cast a vote for a whiskey in an award category. One vote per user per category per year."""
    cat = next((c for c in AWARD_CATEGORIES if c["slug"] == category_slug), None)
    if not cat:
        raise HTTPException(status_code=404, detail="Award category not found")

    # Check if user already voted
    existing = (
        db.query(models.CommunityVote)
        .filter(
            models.CommunityVote.user_id == current_user.username,
            models.CommunityVote.year == year,
            models.CommunityVote.category_slug == category_slug,
        )
        .first()
    )
    if existing:
        # Update vote
        existing.whiskey_id = body.whiskey_id
        db.commit()
        return {"message": "Vote updated", "whiskey_id": body.whiskey_id}

    vote = models.CommunityVote(
        user_id=current_user.username,
        year=year,
        category_slug=category_slug,
        whiskey_id=body.whiskey_id,
    )
    db.add(vote)
    db.commit()
    return {"message": "Vote cast", "whiskey_id": body.whiskey_id}


@router.get("/{year}/{category_slug}/my-vote")
def get_my_vote(
    year: int,
    category_slug: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if the current user has voted in a category."""
    vote = (
        db.query(models.CommunityVote)
        .filter(
            models.CommunityVote.user_id == current_user.username,
            models.CommunityVote.year == year,
            models.CommunityVote.category_slug == category_slug,
        )
        .first()
    )
    if not vote:
        return {"voted": False, "whiskey_id": None}
    return {"voted": True, "whiskey_id": vote.whiskey_id}
