"""
Generate stylized bottle images for all whiskeys in the database.

Each image is a 400x600 PNG with:
- A bottle silhouette shape
- Category-themed color scheme
- Whiskey name and distillery on the label

Usage:
    cd backend
    .venv/bin/python -m scripts.generate_bottle_images
"""

import os
import sys
import re
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw, ImageFont
from app.database import SessionLocal
from app import models
from app.storage import upload_bytes

# Color themes per category (bg, bottle_color, label_bg, label_text, accent)
CATEGORY_COLORS = {
    "bourbon": ("#2b1e0f", "#8B4513", "#f5e6c8", "#2b1e0f", "#c8872a"),
    "rye":     ("#1a2010", "#6B4226", "#e8dcc8", "#1a2010", "#8fa050"),
    "scotch":  ("#1a1a2e", "#4a3520", "#f0e6d3", "#1a1a2e", "#d4a847"),
    "irish":   ("#0f2818", "#2d5a27", "#e8f0e0", "#0f2818", "#4ade80"),
    "japanese":("#1a1020", "#3d2b4a", "#f0e8f5", "#1a1020", "#c084fc"),
}

DEFAULT_COLORS = ("#1a1208", "#4a3520", "#f0e6d3", "#1a1208", "#c8872a")


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_bottle_image(name, distillery, category, age, abv, region):
    """Create a stylized bottle image."""
    W, H = 400, 600
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)
    bg_color, bottle_color, label_bg, label_text_color, accent = colors

    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load a nice font, fall back to default
    title_font = None
    sub_font = None
    detail_font = None
    for font_path in [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]:
        if os.path.exists(font_path):
            title_font = ImageFont.truetype(font_path, 22)
            sub_font = ImageFont.truetype(font_path, 14)
            detail_font = ImageFont.truetype(font_path, 12)
            break

    if not title_font:
        title_font = ImageFont.load_default()
        sub_font = title_font
        detail_font = title_font

    # ── Draw bottle silhouette ──────────────────────────────────────────
    cx = W // 2

    # Neck
    neck_w = 30
    draw.rectangle(
        [cx - neck_w // 2, 40, cx + neck_w // 2, 140],
        fill=bottle_color
    )

    # Neck ring
    draw.rectangle(
        [cx - neck_w // 2 - 4, 38, cx + neck_w // 2 + 4, 50],
        fill=accent
    )

    # Shoulder taper (polygon)
    draw.polygon([
        (cx - neck_w // 2, 140),
        (cx + neck_w // 2, 140),
        (cx + 80, 190),
        (cx - 80, 190),
    ], fill=bottle_color)

    # Body
    draw.rounded_rectangle(
        [cx - 80, 190, cx + 80, 520],
        radius=8,
        fill=bottle_color,
    )

    # Base
    draw.rounded_rectangle(
        [cx - 85, 510, cx + 85, 535],
        radius=5,
        fill=accent,
    )

    # Subtle reflection line on bottle
    draw.line(
        [(cx - 50, 200), (cx - 50, 500)],
        fill=label_bg + "30" if len(label_bg) == 7 else label_bg,
        width=2,
    )

    # ── Draw label area ────────────────────────────────────────────────
    label_top = 250
    label_bottom = 460
    label_left = cx - 68
    label_right = cx + 68
    label_w = label_right - label_left

    # Label background
    draw.rounded_rectangle(
        [label_left, label_top, label_right, label_bottom],
        radius=6,
        fill=label_bg,
    )

    # Label border
    draw.rounded_rectangle(
        [label_left + 3, label_top + 3, label_right - 3, label_bottom - 3],
        radius=4,
        outline=accent,
        width=1,
    )

    # Top accent line on label
    draw.line(
        [(label_left + 10, label_top + 15), (label_right - 10, label_top + 15)],
        fill=accent,
        width=1,
    )

    # ── Whiskey name (wrapped) ──────────────────────────────────────────
    name_lines = wrap_text(name, title_font, label_w - 20, draw)
    y = label_top + 25
    for line in name_lines[:3]:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y), line, fill=label_text_color, font=title_font)
        y += bbox[3] - bbox[1] + 4

    # Separator line
    y += 5
    draw.line([(label_left + 15, y), (label_right - 15, y)], fill=accent, width=1)
    y += 10

    # Distillery
    dist_lines = wrap_text(distillery, sub_font, label_w - 20, draw)
    for line in dist_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=sub_font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y), line, fill=label_text_color, font=sub_font)
        y += bbox[3] - bbox[1] + 3

    # Details row
    y += 8
    details = []
    if region:
        details.append(region)
    if age:
        details.append(f"{age} Year")
    details.append(f"{abv}% ABV")
    detail_text = " · ".join(details)
    detail_lines = wrap_text(detail_text, detail_font, label_w - 16, draw)
    for line in detail_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=detail_font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, y), line, fill=accent, font=detail_font)
        y += bbox[3] - bbox[1] + 2

    # Category badge near bottom of label
    cat_text = category.upper()
    bbox = draw.textbbox((0, 0), cat_text, font=detail_font)
    cat_w = bbox[2] - bbox[0]
    cat_h = bbox[3] - bbox[1]
    cat_y = label_bottom - cat_h - 18
    draw.rounded_rectangle(
        [cx - cat_w // 2 - 10, cat_y - 3, cx + cat_w // 2 + 10, cat_y + cat_h + 5],
        radius=3,
        fill=accent,
    )
    draw.text((cx - cat_w // 2, cat_y), cat_text, fill=bg_color, font=detail_font)

    # Bottom accent line
    draw.line(
        [(label_left + 10, label_bottom - 8), (label_right - 10, label_bottom - 8)],
        fill=accent,
        width=1,
    )

    return img


def main():
    db = SessionLocal()
    whiskeys = db.query(models.Whiskey).all()

    if not whiskeys:
        print("No whiskeys in database. Run seed_data.py first.")
        db.close()
        return

    count = 0
    for w in whiskeys:
        filename = f"{slugify(w.name)}.png"

        img = generate_bottle_image(
            name=w.name,
            distillery=w.distillery,
            category=w.category,
            age=w.age,
            abv=w.abv,
            region=w.region,
        )

        buf = BytesIO()
        img.save(buf, "PNG")
        upload_bytes(buf.getvalue(), f"bottles/{filename}", content_type="image/png")

        # Update database with image URL
        w.image_url = f"/uploads/bottles/{filename}"
        count += 1
        print(f"  Generated: {filename}")

    db.commit()
    db.close()
    print(f"\nGenerated {count} bottle images -> S3 bottles/")


if __name__ == "__main__":
    main()
