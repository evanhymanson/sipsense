"""
SipSense SEO Router

Dynamic sitemap generation and social crawler OG tag injection.
"""

import html
from fastapi import APIRouter, Depends, Path, HTTPException
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/seo", tags=["seo"])


# ── Category / distillery slugs (must match learn.py) ───────────────────

CATEGORY_SLUGS = ["bourbon", "scotch", "rye", "irish", "japanese", "canadian"]

DISTILLERY_SLUGS = [
    "makers-mark", "buffalo-trace", "glenfiddich", "laphroaig",
    "ardbeg", "macallan", "yamazaki", "jameson", "wild-turkey",
    "four-roses", "redbreast",
]


@router.get("/sitemap.xml", response_class=Response)
def get_sitemap(db: Session = Depends(get_db)):
    """Generate dynamic sitemap.xml with all public pages."""
    urls: list[str] = []

    def _url(loc: str, freq: str = "weekly", priority: str = "0.5"):
        urls.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    # Static pages
    _url("https://sipsense.ai/", "weekly", "1.0")
    _url("https://sipsense.ai/learn", "weekly", "0.8")
    _url("https://sipsense.ai/learn/glossary", "monthly", "0.6")

    # Category guides
    for slug in CATEGORY_SLUGS:
        _url(f"https://sipsense.ai/learn/categories/{slug}", "monthly", "0.8")

    # Distillery pages
    for slug in DISTILLERY_SLUGS:
        _url(f"https://sipsense.ai/learn/distilleries/{slug}", "monthly", "0.7")

    # All whiskey detail pages (with images, ordered by popularity)
    whiskey_ids = (
        db.query(models.Whiskey.id)
        .filter(
            models.Whiskey.image_url.isnot(None),
            models.Whiskey.image_url != "",
        )
        .order_by(models.Whiskey.rating_count.desc())
        .all()
    )
    for (wid,) in whiskey_ids:
        _url(f"https://sipsense.ai/whiskey/{wid}", "weekly", "0.6")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )

    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/og/whiskey/{whiskey_id}", response_class=HTMLResponse)
def whiskey_og(whiskey_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    """Minimal HTML with OG tags for social link previews (Facebook, Twitter, Discord, etc.)."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Not found")

    title = html.escape(f"{whiskey.name} \u2014 {whiskey.distillery} | SipSense")
    raw_desc = (whiskey.description or "")[:200] or (
        f"{whiskey.name} by {whiskey.distillery}. "
        f"{whiskey.category}, {whiskey.abv}% ABV."
    )
    desc = html.escape(raw_desc)
    image = whiskey.image_url or "/og-image.png"
    if not image.startswith("http"):
        image = f"https://sipsense.ai{image}"
    url = f"https://sipsense.ai/whiskey/{whiskey_id}"

    page = (
        "<!DOCTYPE html>\n"
        "<html><head>\n"
        f"<title>{title}</title>\n"
        f'<meta property="og:type" content="product"/>\n'
        f'<meta property="og:title" content="{title}"/>\n'
        f'<meta property="og:description" content="{desc}"/>\n'
        f'<meta property="og:image" content="{image}"/>\n'
        f'<meta property="og:url" content="{url}"/>\n'
        f'<meta property="og:site_name" content="SipSense"/>\n'
        f'<meta name="twitter:card" content="summary_large_image"/>\n'
        f'<meta name="twitter:title" content="{title}"/>\n'
        f'<meta name="twitter:description" content="{desc}"/>\n'
        f'<meta name="twitter:image" content="{image}"/>\n'
        f'<meta http-equiv="refresh" content="0;url={url}"/>\n'
        "</head><body>\n"
        f"<h1>{title}</h1><p>{desc}</p>\n"
        f'<p><a href="{url}">View on SipSense</a></p>\n'
        "</body></html>"
    )
    return HTMLResponse(content=page)
