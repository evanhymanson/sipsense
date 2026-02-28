"""
AI-powered features: tasting notes, palate summaries, and recommendation explanations.
Uses the Anthropic API (Claude) for generation.
"""

import os
import json
from collections import Counter

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..auth import get_current_user, get_optional_user

router = APIRouter(tags=["ai"])

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
    return _client


# ── AI Tasting Notes ──────────────────────────────────────────────────────────


@router.get("/whiskeys/{whiskey_id}/ai-tasting-notes")
def get_ai_tasting_notes(
    whiskey_id: int,
    db: Session = Depends(get_db),
):
    """Generate AI tasting notes (nose, palate, finish) for a whiskey."""
    w = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Build a context string for Claude
    details = [f"Name: {w.name}", f"Distillery: {w.distillery}", f"Category: {w.category}"]
    if w.region:
        details.append(f"Region: {w.region}")
    if w.age:
        details.append(f"Age: {w.age} years")
    details.append(f"ABV: {w.abv}%")
    if w.flavor_profile:
        details.append(f"Flavor tags: {w.flavor_profile}")
    if w.description:
        details.append(f"Description: {w.description}")

    prompt = f"""You are a professional whiskey reviewer. Given this whiskey's details, write tasting notes.

{chr(10).join(details)}

Write exactly this JSON (no markdown, no extra text):
{{"nose": "2-3 sentences about aroma", "palate": "2-3 sentences about taste", "finish": "1-2 sentences about the finish", "overall": "1 sentence summary and who it's best for"}}

Be specific and evocative. Reference the actual flavor profile. Write as if you've tasted it."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        notes = json.loads(text)
        return {
            "whiskey_id": whiskey_id,
            "whiskey_name": w.name,
            **notes,
        }
    except (json.JSONDecodeError, IndexError, KeyError):
        # Fallback: generate notes from flavor profile
        flavors = w.flavor_profile or "balanced"
        return {
            "whiskey_id": whiskey_id,
            "whiskey_name": w.name,
            "nose": f"Aromas of {flavors} greet the glass.",
            "palate": f"On the palate, {flavors} notes come through with {w.abv}% ABV warmth.",
            "finish": f"A {'long' if (w.age or 0) > 12 else 'medium'} finish with lingering character.",
            "overall": f"A solid {w.category or 'whiskey'} worth exploring.",
        }
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")


# ── AI Palate Summary ─────────────────────────────────────────────────────────


@router.get("/palate/me/ai-summary")
def get_ai_palate_summary(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an AI-written narrative summary of the user's palate."""
    user_id = current_user.username

    ratings = db.query(models.UserRating).filter(models.UserRating.user_id == user_id).all()
    favs = db.query(models.UserFavorite).filter(models.UserFavorite.user_id == user_id).all()
    fav_ids = {f.whiskey_id for f in favs}

    if not ratings and not fav_ids:
        return {"narrative": "Rate some whiskeys and save favorites to get your AI palate portrait!"}

    all_ids = {r.whiskey_id for r in ratings} | fav_ids
    whiskeys_map = {
        w.id: w for w in db.query(models.Whiskey).filter(models.Whiskey.id.in_(all_ids)).all()
    }

    top_ids = {r.whiskey_id for r in ratings if r.score >= 4.0} | fav_ids
    profile_whiskeys = [whiskeys_map[i] for i in top_ids if i in whiskeys_map]

    categories = Counter(w.category for w in profile_whiskeys if w.category)
    all_flavors = []
    for w in profile_whiskeys:
        if w.flavor_profile:
            all_flavors.extend([f.strip().lower() for f in w.flavor_profile.split(",")])
    flavor_counts = Counter(all_flavors)
    top_flavors = [f for f, _ in flavor_counts.most_common(6)]

    prices = [w.price_usd for w in profile_whiskeys if w.price_usd]
    avg_price = sum(prices) / len(prices) if prices else 0

    high_rated = [(r, whiskeys_map.get(r.whiskey_id)) for r in ratings if r.score >= 4.5]
    low_rated = [(r, whiskeys_map.get(r.whiskey_id)) for r in ratings if r.score <= 2.0]

    # Build data summary for Claude
    data = {
        "total_rated": len(ratings),
        "total_favorites": len(fav_ids),
        "top_categories": dict(categories.most_common(3)),
        "top_flavors": top_flavors,
        "avg_price": round(avg_price, 2),
        "avg_score": round(sum(r.score for r in ratings) / len(ratings), 2) if ratings else 0,
        "loved": [f"{w.name} ({r.score}\u2605)" for r, w in high_rated[:3] if w],
        "disliked": [f"{w.name} ({r.score}\u2605)" for r, w in low_rated[:3] if w],
    }

    prompt = f"""You are SipSense, a warm and knowledgeable whiskey guide. Write a 3-4 paragraph
palate portrait for this user based on their data. Be specific, personal, and encouraging.

User data: {json.dumps(data)}

Write like you're a friend who really gets their taste. Reference specific patterns you notice.
Suggest what direction their palate might naturally evolve toward. Keep it under 200 words."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = response.content[0].text.strip()
        return {"narrative": narrative}
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")


# ── "Why You'll Like This" for Recommendations ──────────────────────────────


@router.get("/recommendations/explained")
def get_explained_recommendations(
    top_n: int = 6,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get recommendations with AI-generated explanations of why the user will like each one."""
    from ..ml.recommender import content_based_recommendations

    user_id = current_user.username

    # Get user's taste profile for context
    ratings = db.query(models.UserRating).filter(models.UserRating.user_id == user_id).all()
    favs = db.query(models.UserFavorite).filter(models.UserFavorite.user_id == user_id).all()
    fav_ids = {f.whiskey_id for f in favs}
    all_ids = {r.whiskey_id for r in ratings} | fav_ids
    profile_whiskeys = (
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(all_ids)).all()
        if all_ids else []
    )

    # User taste summary
    categories = Counter(w.category for w in profile_whiskeys if w.category)
    all_flavors = []
    for w in profile_whiskeys:
        if w.flavor_profile:
            all_flavors.extend([f.strip().lower() for f in w.flavor_profile.split(",")])
    flavor_counts = Counter(all_flavors)
    top_flavors = [f for f, _ in flavor_counts.most_common(5)]
    top_cats = [c for c, _ in categories.most_common(2)]

    # Get recommendations
    results = content_based_recommendations(user_id=user_id, db=db, top_n=top_n)

    # Generate "why" reasons efficiently — template-based (no API call)
    output = []
    for whiskey, score in results:
        reason = _generate_reason(whiskey, top_flavors, top_cats)
        output.append({
            "whiskey": {
                "id": whiskey.id, "name": whiskey.name, "distillery": whiskey.distillery,
                "category": whiskey.category, "region": whiskey.region, "age": whiskey.age,
                "abv": whiskey.abv, "price_usd": whiskey.price_usd,
                "flavor_profile": whiskey.flavor_profile,
                "rating_avg": whiskey.rating_avg, "rating_count": whiskey.rating_count,
            },
            "score": score,
            "reason": reason,
        })
    return output


def _generate_reason(whiskey, user_top_flavors, user_top_cats):
    """Generate a brief 'why you'll like this' reason based on flavor/category overlap."""
    reasons = []

    # Category match
    if whiskey.category and whiskey.category.lower() in [c.lower() for c in user_top_cats]:
        reasons.append(f"Fits your {whiskey.category} preference")

    # Flavor overlap
    if whiskey.flavor_profile and user_top_flavors:
        w_flavors = [f.strip().lower() for f in whiskey.flavor_profile.split(",")]
        overlapping = [f for f in w_flavors if f in user_top_flavors]
        if overlapping:
            reasons.append(f"Matches your love of {', '.join(overlapping[:2])} notes")

    # Value angle
    if whiskey.price_usd and whiskey.price_usd < 50 and (whiskey.rating_avg or 0) >= 4.0:
        reasons.append("Great value for the quality")

    # Age angle
    if whiskey.age and whiskey.age >= 15:
        reasons.append("A well-aged expression with depth")

    if not reasons:
        if whiskey.rating_avg and whiskey.rating_avg >= 4.2:
            reasons.append("Highly rated by the community")
        else:
            reasons.append("A great match for your palate profile")

    return ". ".join(reasons[:2]) + "."
