"""
Share card generation — create branded shareable PNG images for ratings and palate DNA.
"""
import io
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/share", tags=["share"])

# Brand colors matching the frontend CSS variables
BG_COLOR = (26, 18, 8)         # --bg: #1a1208
SURFACE_COLOR = (43, 30, 15)   # --surface: #2b1e0f
AMBER_COLOR = (200, 135, 42)   # --amber: #c8872a
TEXT_COLOR = (240, 230, 211)    # --text: #f0e6d3
MUTED_COLOR = (154, 128, 112)  # --text-muted: #9a8070

CARD_W = 600
CARD_H = 400


_font_cache = None


def _load_fonts():
    """Try system Georgia, fall back to Pillow defaults. Cached after first call."""
    global _font_cache
    if _font_cache is not None:
        return _font_cache

    from PIL import ImageFont

    paths = [
        "/System/Library/Fonts/Georgia.ttf",              # macOS
        "/usr/share/fonts/truetype/georgia.ttf",           # Linux
        "C:\\Windows\\Fonts\\georgia.ttf",                 # Windows
    ]
    for p in paths:
        try:
            _font_cache = (
                ImageFont.truetype(p, 28),
                ImageFont.truetype(p, 18),
                ImageFont.truetype(p, 14),
            )
            return _font_cache
        except (OSError, IOError):
            continue

    default = ImageFont.load_default()
    _font_cache = (default, default, default)
    return _font_cache


@router.get("/rating/{rating_id}")
def generate_share_card(rating_id: int, db: Session = Depends(get_db)):
    """Generate a branded PNG share card for a rating."""
    from PIL import Image, ImageDraw

    rating = db.query(models.UserRating).filter(models.UserRating.id == rating_id).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == rating.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    font_lg, font_md, font_sm = _load_fonts()

    img = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([(0, 0), (CARD_W, 60)], fill=SURFACE_COLOR)
    draw.text((20, 16), "SipSense", fill=AMBER_COLOR, font=font_md)

    # Whiskey name (truncate if long)
    name = whiskey.name if len(whiskey.name) <= 35 else whiskey.name[:32] + "..."
    draw.text((30, 80), name, fill=TEXT_COLOR, font=font_lg)
    draw.text((30, 120), whiskey.distillery, fill=MUTED_COLOR, font=font_md)

    # Rating stars
    filled = round(rating.score)
    stars = "\u2605" * filled + "\u2606" * (5 - filled)
    draw.text((30, 165), stars, fill=AMBER_COLOR, font=font_lg)
    draw.text((200, 173), f"{rating.score}/5", fill=TEXT_COLOR, font=font_md)

    # Notes
    if rating.notes:
        note = rating.notes[:140] + ("..." if len(rating.notes) > 140 else "")
        # Wrap long lines
        words = note.split()
        lines, line = [], ""
        for w in words:
            test = f"{line} {w}".strip()
            if len(test) > 55:
                lines.append(line)
                line = w
            else:
                line = test
        if line:
            lines.append(line)
        y = 220
        for ln in lines[:3]:
            draw.text((30, y), ln, fill=TEXT_COLOR, font=font_sm)
            y += 20

    # Category / region / ABV
    details = whiskey.category
    if whiskey.region:
        details += f" | {whiskey.region}"
    if whiskey.abv:
        details += f" | {whiskey.abv}% ABV"
    draw.text((30, 310), details, fill=MUTED_COLOR, font=font_sm)

    # Rated by
    draw.text((30, 340), f"Rated by {rating.user_id}", fill=MUTED_COLOR, font=font_sm)

    # Bottom bar
    draw.rectangle([(0, CARD_H - 40), (CARD_W, CARD_H)], fill=SURFACE_COLOR)
    draw.text((20, CARD_H - 32), "Discover whiskey at sipsense.app", fill=AMBER_COLOR, font=font_sm)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=sipsense-rating-{rating_id}.png"},
    )


@router.get("/whiskey/{whiskey_id}")
def generate_whiskey_share_card(whiskey_id: int, db: Session = Depends(get_db)):
    """Generate a branded PNG share card for a whiskey (no rating required)."""
    from PIL import Image, ImageDraw

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    font_lg, font_md, font_sm = _load_fonts()

    img = Image.new("RGB", (CARD_W, CARD_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top bar
    draw.rectangle([(0, 0), (CARD_W, 60)], fill=SURFACE_COLOR)
    draw.text((20, 16), "SipSense", fill=AMBER_COLOR, font=font_md)

    # Whiskey name
    name = whiskey.name if len(whiskey.name) <= 35 else whiskey.name[:32] + "..."
    draw.text((30, 80), name, fill=TEXT_COLOR, font=font_lg)
    draw.text((30, 120), whiskey.distillery or "", fill=MUTED_COLOR, font=font_md)

    # Community rating
    if whiskey.rating_avg:
        filled = round(whiskey.rating_avg)
        stars = "\u2605" * filled + "\u2606" * (5 - filled)
        draw.text((30, 165), stars, fill=AMBER_COLOR, font=font_lg)
        draw.text((200, 173), f"{whiskey.rating_avg:.1f}/5 · {whiskey.rating_count} ratings", fill=TEXT_COLOR, font=font_md)

    # Flavor tags
    if whiskey.flavor_profile:
        flavors = [f.strip() for f in whiskey.flavor_profile.split(",") if f.strip()][:5]
        if flavors:
            draw.text((30, 240), "Flavors: " + "  ·  ".join(flavors), fill=MUTED_COLOR, font=font_sm)

    # Category / region / ABV / price
    details = whiskey.category or ""
    if whiskey.region:
        details += f" | {whiskey.region}"
    if whiskey.abv:
        details += f" | {whiskey.abv}% ABV"
    if whiskey.price_usd:
        details += f" | ${whiskey.price_usd}"
    draw.text((30, 310), details, fill=MUTED_COLOR, font=font_sm)

    # CTA
    draw.text((30, 340), "Discover this bottle on SipSense", fill=TEXT_COLOR, font=font_sm)

    # Bottom bar
    draw.rectangle([(0, CARD_H - 40), (CARD_W, CARD_H)], fill=SURFACE_COLOR)
    draw.text((20, CARD_H - 32), "sipsense.app  ·  AI-powered whiskey discovery", fill=AMBER_COLOR, font=font_sm)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=sipsense-{whiskey_id}.png"},
    )


@router.get("/palate/{username}")
def generate_palate_dna_card(username: str, db: Session = Depends(get_db)):
    """Generate a branded PNG 'Whiskey DNA' card for a user's palate."""
    from PIL import Image, ImageDraw

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ratings = (
        db.query(models.UserRating)
        .filter(models.UserRating.user_id == username)
        .all()
    )
    if not ratings:
        raise HTTPException(status_code=404, detail="No ratings to generate DNA card")

    rated_ids = [r.whiskey_id for r in ratings]
    whiskeys = {
        w.id: w
        for w in db.query(models.Whiskey).filter(models.Whiskey.id.in_(rated_ids)).all()
    }

    cat_counter: Counter = Counter()
    flavor_counter: Counter = Counter()
    for r in ratings:
        w = whiskeys.get(r.whiskey_id)
        if not w:
            continue
        if w.category:
            cat_counter[w.category] += 1
        if w.flavor_profile:
            for tag in w.flavor_profile.split(","):
                tag = tag.strip().lower()
                if tag:
                    flavor_counter[tag] += 1

    top_cats = [c for c, _ in cat_counter.most_common(3)]
    top_flavors = [f for f, _ in flavor_counter.most_common(5)]
    avg_score = round(sum(r.score for r in ratings) / len(ratings), 1)
    total = len(ratings)

    # Fun descriptor based on palate
    if avg_score >= 4.2:
        descriptor = "Discerning Palate"
    elif avg_score >= 3.5:
        descriptor = "Enthusiast"
    else:
        descriptor = "Explorer"
    if total >= 50:
        descriptor = f"Seasoned {descriptor}"
    elif total >= 20:
        descriptor = f"Rising {descriptor}"

    font_lg, font_md, font_sm = _load_fonts()
    DNA_W, DNA_H = 600, 420
    img = Image.new("RGB", (DNA_W, DNA_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Top bar with branding
    draw.rectangle([(0, 0), (DNA_W, 56)], fill=SURFACE_COLOR)
    draw.text((20, 14), "SipSense", fill=AMBER_COLOR, font=font_md)
    draw.text((DNA_W - 168, 18), "My Whiskey DNA", fill=MUTED_COLOR, font=font_sm)

    # Username + descriptor
    draw.text((30, 76), f"@{username}", fill=TEXT_COLOR, font=font_lg)
    draw.text((30, 112), descriptor, fill=AMBER_COLOR, font=font_md)

    # Stats row
    y = 152
    draw.text((30, y), f"{total} Bottles Rated", fill=TEXT_COLOR, font=font_md)
    draw.text((250, y), f"Avg {avg_score}/5", fill=AMBER_COLOR, font=font_md)

    # Divider
    y = 188
    draw.line([(30, y), (DNA_W - 30, y)], fill=MUTED_COLOR, width=1)

    # Top categories (left column)
    y = 204
    draw.text((30, y), "Top Styles", fill=MUTED_COLOR, font=font_sm)
    y += 24
    for cat in top_cats:
        draw.text((30, y), f"\u2022 {cat}", fill=TEXT_COLOR, font=font_md)
        y += 26

    # Top flavors (right column)
    y = 204
    draw.text((300, y), "Flavor DNA", fill=MUTED_COLOR, font=font_sm)
    y += 24
    for flav in top_flavors:
        draw.text((300, y), f"\u2022 {flav}", fill=AMBER_COLOR, font=font_md)
        y += 26

    # Bottom bar
    draw.rectangle([(0, DNA_H - 40), (DNA_W, DNA_H)], fill=SURFACE_COLOR)
    draw.text(
        (20, DNA_H - 32),
        "Discover your whiskey DNA at sipsense.ai",
        fill=AMBER_COLOR,
        font=font_sm,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=sipsense-dna-{username}.png"
        },
    )
