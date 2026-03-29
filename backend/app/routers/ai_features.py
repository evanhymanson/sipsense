"""
AI-powered features: tasting notes, palate summaries, and recommendation explanations.
Uses the Anthropic API (Claude) for generation.
"""

import os
import json
import base64
import re
from collections import Counter

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..schemas import _prefer_nobg
from ..storage import make_cdn_url

router = APIRouter(tags=["ai"])

_client = None
_client_api_key = None


def _get_client():
    global _client, _client_api_key
    current_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if _client is None or current_key != _client_api_key:
        _client = anthropic.Anthropic(api_key=current_key)
        _client_api_key = current_key
    return _client


# ── AI Response Cache helpers ────────────────────────────────────────────


def _get_cached(db: Session, cache_key: str) -> dict | None:
    """Return cached AI response if it exists, else None."""
    row = db.query(models.AICache).filter(models.AICache.cache_key == cache_key).first()
    if row:
        try:
            return json.loads(row.response_json)
        except json.JSONDecodeError:
            pass
    return None


def _set_cached(db: Session, cache_key: str, data: dict) -> None:
    """Store an AI response in the cache."""
    existing = db.query(models.AICache).filter(models.AICache.cache_key == cache_key).first()
    payload = json.dumps(data)
    if existing:
        existing.response_json = payload
    else:
        db.add(models.AICache(cache_key=cache_key, response_json=payload))
    db.commit()


# ── AI Tasting Notes ──────────────────────────────────────────────────────────


@router.get("/whiskeys/{whiskey_id}/ai-tasting-notes")
def get_ai_tasting_notes(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate AI tasting notes (nose, palate, finish) for a whiskey."""
    w = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    # Check cache first
    cache_key = f"v1:tasting_notes:{whiskey_id}"
    cached = _get_cached(db, cache_key)
    if cached:
        return cached

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
        result = {
            "whiskey_id": whiskey_id,
            "whiskey_name": w.name,
            **notes,
        }
        _set_cached(db, cache_key, result)
        return result
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

    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id)
        .order_by(models.UserRating.created_at.desc())
        .limit(200)
        .all()
    )
    favs = (
        db.query(models.UserFavorite)
        .filter(models.UserFavorite.user_id == user_id)
        .order_by(models.UserFavorite.created_at.desc())
        .limit(200)
        .all()
    )
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
Suggest what direction their palate might naturally evolve toward. Keep it under 200 words.
Do not use any markdown formatting — no bold, no italics, no asterisks, no headers. Plain text only."""

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

    # Get user's taste profile for context (capped to avoid loading thousands of rows)
    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == user_id)
        .order_by(models.UserRating.created_at.desc())
        .limit(200)
        .all()
    )
    favs = (
        db.query(models.UserFavorite)
        .filter(models.UserFavorite.user_id == user_id)
        .order_by(models.UserFavorite.created_at.desc())
        .limit(200)
        .all()
    )
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
            "whiskey": schemas.WhiskeyRead.model_validate(whiskey).model_dump(),
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


# ── AI Blind Tasting Coach ─────────────────────────────────────────────────────


from pydantic import BaseModel as _BaseModel


class BlindTastingCoachRequest(_BaseModel):
    whiskey_id: int
    user_guess: str   # the category the user guessed
    difficulty: str = "easy"


@router.post("/blind-tasting/coach")
def get_blind_tasting_coach(
    req: BlindTastingCoachRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    After a blind tasting guess, Claude delivers an educational explanation:
    why does this whiskey smell / taste the way it does, and what production
    choices led to those characteristics?
    """
    # Check cache (keyed by whiskey + guess)
    guess_norm = req.user_guess.lower().strip()
    cache_key = f"v1:blind_coach:{req.whiskey_id}:{guess_norm}"
    cached = _get_cached(db, cache_key)
    if cached:
        return cached

    w = db.query(models.Whiskey).filter(models.Whiskey.id == req.whiskey_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    correct = (w.category or "").lower().strip() == guess_norm
    result_phrase = "correct" if correct else f"incorrect (it was actually {w.category})"

    details = [
        f"Name: {w.name}",
        f"Distillery: {w.distillery}",
        f"Category: {w.category}",
    ]
    if w.region:
        details.append(f"Region: {w.region}")
    if w.age:
        details.append(f"Age: {w.age} years")
    details.append(f"ABV: {w.abv}%")
    if w.flavor_profile:
        details.append(f"Flavor profile: {w.flavor_profile}")

    prompt = f"""You are SipSense, a warm whiskey educator. A user just completed a blind tasting challenge.

Whiskey details:
{chr(10).join(details)}

The user guessed: "{req.user_guess}" — which was {result_phrase}.

Write a brief but genuinely educational coaching response. Return exactly this JSON (no markdown):
{{
  "lesson": "2-3 sentences explaining WHY this whiskey has the flavors it does — connect the production method, region, or aging to the specific taste clues",
  "production_insight": "1-2 sentences on the key production choice (grain, distillation, barrel, region) that most defines this whiskey's character",
  "next_tip": "1 sentence: a concrete sensory cue to look for next time that would help identify this style (e.g. 'Look for that iodine-salt note — it almost always signals Islay peat')"
}}

Be specific, scientific but accessible. Reference the actual flavor profile."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        coaching = json.loads(text)
        result = {
            "whiskey_id": w.id,
            "whiskey_name": w.name,
            "whiskey_category": w.category,
            "user_guess": req.user_guess,
            "correct": correct,
            **coaching,
        }
        _set_cached(db, cache_key, result)
        return result
    except (json.JSONDecodeError, IndexError, KeyError):
        return {
            "whiskey_id": w.id,
            "whiskey_name": w.name,
            "whiskey_category": w.category,
            "user_guess": req.user_guess,
            "correct": correct,
            "lesson": f"This {w.category} gets its character from its production region and aging process.",
            "production_insight": f"The {w.abv}% ABV and {w.flavor_profile or 'balanced'} profile reflect classic {w.category} craftsmanship.",
            "next_tip": f"Next time, look for the defining flavor notes of {w.category} — they're the clearest tell.",
        }
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")


# ── AI Bespoke Cocktail ────────────────────────────────────────────────────────


@router.get("/pairings/{whiskey_id}/ai-cocktail")
def get_ai_bespoke_cocktail(
    whiskey_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Claude creates a unique, named cocktail recipe built around this specific
    whiskey's flavor profile — not a generic template, but a genuinely bespoke
    recipe with creative rationale.
    """
    # Check cache first
    cache_key = f"v1:cocktail:{whiskey_id}"
    cached = _get_cached(db, cache_key)
    if cached:
        return cached

    w = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    details = [
        f"Name: {w.name}",
        f"Category: {w.category}",
        f"ABV: {w.abv}%",
        f"Flavor profile: {w.flavor_profile or 'balanced, classic'}",
    ]
    if w.region:
        details.append(f"Region: {w.region}")
    if w.age:
        details.append(f"Age: {w.age} years")

    prompt = f"""You are a creative craft bartender. Design a bespoke original cocktail for this whiskey.

Whiskey:
{chr(10).join(details)}

Rules:
- The cocktail must be designed SPECIFICALLY for this whiskey's flavor profile
- Give it a creative, memorable name (not a classic cocktail name like "Old Fashioned")
- The recipe should COMPLEMENT or CONTRAST the dominant flavors in an interesting way
- Use real, readily available ingredients

Return exactly this JSON (no markdown, no extra text):
{{
  "name": "Creative cocktail name",
  "tagline": "One evocative sentence about this drink",
  "ingredients": [
    {{"amount": "2 oz", "item": "{w.name}"}},
    {{"amount": "0.75 oz", "item": "example ingredient"}},
    {{"amount": "2 dashes", "item": "example bitters"}}
  ],
  "instructions": "2-3 sentences: how to make it (method, order, technique)",
  "garnish": "specific garnish",
  "glassware": "specific glass type",
  "why": "2 sentences explaining exactly how the ingredients interact with this whiskey's specific flavor profile"
}}"""

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        cocktail = json.loads(text)
        result = {
            "whiskey_id": w.id,
            "whiskey_name": w.name,
            "whiskey_category": w.category,
            **cocktail,
        }
        _set_cached(db, cache_key, result)
        return result
    except (json.JSONDecodeError, IndexError, KeyError):
        return {
            "whiskey_id": w.id,
            "whiskey_name": w.name,
            "whiskey_category": w.category,
            "name": f"The {w.name.split()[0]} Special",
            "tagline": f"A simple serve that lets {w.name} shine.",
            "ingredients": [
                {"amount": "2 oz", "item": w.name},
                {"amount": "4 oz", "item": "sparkling water"},
                {"amount": "1 wedge", "item": "lemon"},
            ],
            "instructions": "Build in a highball glass over ice. Add whiskey, top with sparkling water, squeeze lemon. Stir gently.",
            "garnish": "Lemon wedge",
            "glassware": "Highball glass",
            "why": f"The clean carbonation lifts {w.flavor_profile or 'the flavor notes'} and keeps the drink refreshing.",
        }
    except anthropic.APIError:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")


# ── AI Collection Insight ──────────────────────────────────────────────────────


@router.get("/collection/ai-insight")
def get_ai_collection_insight(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Claude analyzes the user's whiskey shelf and returns: a narrative about
    their collection style, the best bottle to open tonight, and a gap to fill.
    """
    items = (
        db.query(models.CollectionItem)
        .filter(models.CollectionItem.user_id == current_user.username)
        .limit(500)
        .all()
    )

    if not items:
        return {
            "bottle_count": 0,
            "headline": "Your shelf is empty — let's change that.",
            "collection_story": "Add some bottles to your collection and I'll give you a full analysis of your whiskey shelf.",
            "open_tonight": None,
            "gap_to_fill": "Start with a versatile bourbon like Buffalo Trace or an approachable Scotch like Glenfiddich 12.",
            "fun_stat": "The average whiskey enthusiast's collection has 8–12 bottles at any given time.",
        }

    whiskey_ids = [item.whiskey_id for item in items]
    whiskeys_map = {
        w.id: w for w in db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()
    }

    collection_data = []
    for item in items:
        w = whiskeys_map.get(item.whiskey_id)
        if w:
            collection_data.append({
                "name": w.name,
                "category": w.category,
                "region": w.region,
                "age": w.age,
                "abv": w.abv,
                "price_usd": w.price_usd,
                "flavor_profile": w.flavor_profile,
                "status": item.status,
                "rating_avg": w.rating_avg,
            })

    # Find best candidate for "open tonight" — highest rated, opened or sealed
    opened = [i for i in items if i.status == "opened"]
    best_candidate_id = None
    if opened:
        best = max(opened, key=lambda i: (whiskeys_map.get(i.whiskey_id) or models.Whiskey()).rating_avg or 0)
        best_candidate_id = best.whiskey_id
    elif items:
        best = max(items, key=lambda i: (whiskeys_map.get(i.whiskey_id) or models.Whiskey()).rating_avg or 0)
        best_candidate_id = best.whiskey_id

    best_whiskey = whiskeys_map.get(best_candidate_id) if best_candidate_id else None

    prompt = f"""You are SipSense, a thoughtful whiskey curator. Analyze this user's whiskey collection.

Collection ({len(collection_data)} bottles):
{json.dumps(collection_data, indent=2)}

Return exactly this JSON (no markdown):
{{
  "headline": "A punchy 1-sentence headline describing this collection's personality",
  "collection_story": "2-3 sentences: what does this collection say about the person? What patterns do you see? Be specific and warm.",
  "open_tonight_reason": "1-2 sentences: why open {best_whiskey.name if best_whiskey else 'their best bottle'} tonight? What occasion or mood does it fit?",
  "gap_to_fill": "1-2 sentences: what ONE type of whiskey is clearly missing from this collection, and a specific bottle recommendation to fill the gap",
  "fun_stat": "1 interesting observation or fun stat about this specific collection (total value estimate, average age, boldest bottle, etc.)"
}}

Be warm, specific, and reference actual bottles from their collection."""

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        insight = json.loads(text)

        open_tonight = None
        if best_whiskey:
            open_tonight = {
                "whiskey_id": best_whiskey.id,
                "name": best_whiskey.name,
                "category": best_whiskey.category,
                "reason": insight.get("open_tonight_reason", "A great choice for tonight."),
            }

        return {
            "bottle_count": len(items),
            "headline": insight.get("headline", ""),
            "collection_story": insight.get("collection_story", ""),
            "open_tonight": open_tonight,
            "gap_to_fill": insight.get("gap_to_fill", ""),
            "fun_stat": insight.get("fun_stat", ""),
        }
    except (json.JSONDecodeError, IndexError, KeyError):
        categories = list({w.category for w in whiskeys_map.values() if w.category})
        return {
            "bottle_count": len(items),
            "headline": f"A {len(items)}-bottle collection with serious range.",
            "collection_story": f"Your shelf spans {len(categories)} categories — {', '.join(categories[:3])}. That's a well-rounded foundation.",
            "open_tonight": {"whiskey_id": best_whiskey.id, "name": best_whiskey.name, "category": best_whiskey.category, "reason": "Your highest-rated bottle — perfect for tonight."} if best_whiskey else None,
            "gap_to_fill": "Consider adding a Japanese whisky for balance and delicacy.",
            "fun_stat": f"You have {sum(1 for i in items if i.status == 'opened')} opened bottles ready to pour right now.",
        }


# ── Label scan ────────────────────────────────────────────────────────────

_STOP_WORDS = {
    "the", "a", "an", "of", "and", "&", "single", "barrel", "batch",
    "edition", "year", "old", "cask", "strength", "distillery", "whiskey",
    "whisky", "scotch", "bourbon", "irish", "japanese", "blended", "malt",
}


def _word_overlap(a: str, b: str) -> float:
    a_words = set(a.lower().split()) - _STOP_WORDS
    b_words = set(b.lower().split()) - _STOP_WORDS
    if not a_words or not b_words:
        return 0.0
    return len(a_words & b_words) / max(len(a_words), len(b_words))


def _fuzzy_find(name: str, db: Session) -> models.Whiskey | None:
    """Find the best DB match for an AI-identified whiskey name."""
    if not name:
        return None

    # Build keyword search using the significant words
    keywords = [w for w in name.lower().split() if w not in _STOP_WORDS and len(w) > 2]
    if not keywords:
        return None

    # Try progressively broader queries
    for kw in keywords[:3]:
        candidates = (
            db.query(models.Whiskey)
            .filter(func.lower(models.Whiskey.name).contains(kw))
            .limit(20)
            .all()
        )
        if candidates:
            best = max(candidates, key=lambda w: _word_overlap(name, w.name))
            if _word_overlap(name, best.name) >= 0.4:
                return best

    return None


@router.post("/scan/label")
async def scan_label(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Identify a whiskey from a photo of its label using Claude Vision.
    Returns the matched DB whiskey if found, plus AI-extracted details.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI label scanning not configured")

    # Validate image type
    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Cap at 5 MB
    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large — maximum 5 MB")

    image_b64 = base64.standard_b64encode(image_bytes).decode()

    prompt = (
        "This is a photo of a whiskey (or whisky) bottle label. "
        "Extract the product information and respond with ONLY valid JSON — no markdown, no explanation.\n\n"
        "Required format:\n"
        '{"name": "full product name exactly as on label", '
        '"distillery": "distillery or producer name", '
        '"age": null or integer years, '
        '"abv": null or float percentage, '
        '"category": "bourbon|scotch|irish|japanese|rye|canadian|blended|world whisky", '
        '"region": null or "region string"}\n\n'
        "If the image does not show a whiskey bottle label, return: "
        '{"error": "not a whiskey label"}'
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": content_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    raw = response.content[0].text.strip()

    # Extract JSON even if Claude adds surrounding text
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise HTTPException(status_code=422, detail="Could not parse label — try a clearer photo")

    try:
        ai_data = json.loads(json_match.group())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse label — try a clearer photo")

    if "error" in ai_data:
        raise HTTPException(status_code=422, detail=ai_data["error"])

    identified_name = ai_data.get("name", "")

    # Try to match against the database
    matched = _fuzzy_find(identified_name, db)

    # Gap 4: Persist scan to history
    scan_record = models.ScanHistory(
        user_id=current_user.username,
        whiskey_id=matched.id if matched else None,
        ai_identified_name=identified_name,
        scan_type="label",
    )
    db.add(scan_record)
    db.commit()

    return {
        "found_in_db": matched is not None,
        "whiskey": {
            "id": matched.id,
            "name": matched.name,
            "distillery": matched.distillery,
            "category": matched.category,
            "region": matched.region,
            "age": matched.age,
            "abv": matched.abv,
            "price_usd": matched.price_usd,
            "rating_avg": matched.rating_avg,
            "rating_count": matched.rating_count,
            "flavor_profile": matched.flavor_profile,
            "image_url": make_cdn_url(_prefer_nobg(matched.image_url)),
        } if matched else None,
        "ai_identified": {
            "name": identified_name,
            "distillery": ai_data.get("distillery"),
            "age": ai_data.get("age"),
            "abv": ai_data.get("abv"),
            "category": ai_data.get("category"),
            "region": ai_data.get("region"),
        },
    }


# ── Gap 4: Scan History ──────────────────────────────────────────────────────


@router.get("/scan/history", response_model=list[schemas.ScanHistoryRead])
def get_scan_history(
    skip: int = 0,
    limit: int = 50,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's scan history, most recent first."""
    return (
        db.query(models.ScanHistory)
        .filter(models.ScanHistory.user_id == current_user.username)
        .order_by(models.ScanHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.delete("/scan/history/{scan_id}", status_code=204)
def delete_scan_history_item(
    scan_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a single scan history entry."""
    scan = (
        db.query(models.ScanHistory)
        .filter(models.ScanHistory.id == scan_id, models.ScanHistory.user_id == current_user.username)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found")
    db.delete(scan)
    db.commit()


# ── Gap 9: Menu Scanner ──────────────────────────────────────────────────────


@router.post("/scan/menu")
async def scan_menu(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scan a bar/restaurant menu photo and identify whiskeys listed on it.
    Returns matched DB whiskeys plus any unrecognized names.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI scanning not configured")

    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large — maximum 5 MB")

    image_b64 = base64.standard_b64encode(image_bytes).decode()

    prompt = (
        "This is a photo of a bar or restaurant menu (or drink list). "
        "Extract ALL whiskey/whisky products listed. "
        "Respond with ONLY valid JSON — no markdown, no explanation.\n\n"
        "Required format:\n"
        '{"whiskeys": [{"name": "full product name", "price": null or float}]}\n\n'
        "If no whiskeys are found, return: "
        '{"whiskeys": []}'
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001"),
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": content_type, "data": image_b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    raw = response.content[0].text.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        raise HTTPException(status_code=422, detail="Could not parse menu — try a clearer photo")

    try:
        ai_data = json.loads(json_match.group())
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Could not parse menu — try a clearer photo")

    menu_items = ai_data.get("whiskeys", [])
    results = []

    for item in menu_items:
        name = item.get("name", "")
        if not name:
            continue
        matched = _fuzzy_find(name, db)
        results.append({
            "menu_name": name,
            "menu_price": item.get("price"),
            "found_in_db": matched is not None,
            "whiskey": schemas.WhiskeyRead.model_validate(matched) if matched else None,
        })

        # Save each identified whiskey to scan history
        db.add(models.ScanHistory(
            user_id=current_user.username,
            whiskey_id=matched.id if matched else None,
            ai_identified_name=name,
            scan_type="menu",
        ))

    db.commit()

    return {
        "items_found": len(results),
        "results": results,
    }
