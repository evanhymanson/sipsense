"""
SipSense SEO Router

Dynamic sitemap generation, social crawler OG tag injection,
and search engine prerendering for public pages.
"""

import html
from fastapi import APIRouter, Depends, Path, HTTPException
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .learn import CATEGORIES, DISTILLERIES, GLOSSARY

router = APIRouter(prefix="/seo", tags=["seo"])


CATEGORY_SLUGS = [c["slug"] for c in CATEGORIES]
DISTILLERY_SLUGS = [d["slug"] for d in DISTILLERIES]

TOP_LIST_DEFS = [
    {"slug": "top-bourbons", "title": "Top Bourbons", "description": "The highest-rated bourbons on SipSense"},
    {"slug": "top-scotch", "title": "Top Scotch Whisky", "description": "Community favorites from Scotland"},
    {"slug": "best-under-50", "title": "Best Whiskeys Under $50", "description": "Top-rated bottles that won't break the bank"},
    {"slug": "best-value", "title": "Best Value Whiskeys", "description": "Highest rating-to-price ratio"},
    {"slug": "top-japanese", "title": "Top Japanese Whisky", "description": "The best of Japanese whisky craftsmanship"},
    {"slug": "top-rye", "title": "Top Rye Whiskeys", "description": "Spice-forward ryes the community loves"},
    {"slug": "premium-picks", "title": "Premium Picks ($100+)", "description": "Top-shelf bottles worth the splurge"},
    {"slug": "top-irish", "title": "Top Irish Whiskey", "description": "Ireland's smoothest and most beloved"},
]


def _prerender_page(title, description, url, body_html):
    """Build a full prerendered HTML page for search engine crawlers."""
    t = html.escape(title)
    d = html.escape(description)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head>\n'
        f"<title>{t}</title>\n"
        f'<meta name="description" content="{d}"/>\n'
        f'<link rel="canonical" href="{url}"/>\n'
        f'<meta property="og:type" content="website"/>\n'
        f'<meta property="og:title" content="{t}"/>\n'
        f'<meta property="og:description" content="{d}"/>\n'
        f'<meta property="og:url" content="{url}"/>\n'
        f'<meta property="og:site_name" content="SipSense"/>\n'
        f'<meta name="twitter:card" content="summary"/>\n'
        f'<meta name="twitter:title" content="{t}"/>\n'
        f'<meta name="twitter:description" content="{d}"/>\n'
        "</head><body>\n"
        f"{body_html}\n"
        "</body></html>"
    )


@router.get("/sitemap.xml", response_class=Response)
def get_sitemap(db: Session = Depends(get_db)):
    """Generate dynamic sitemap.xml with all public pages."""
    urls = []

    def _url(loc, freq="weekly", priority="0.5"):
        urls.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    _url("https://sipsense.ai/", "weekly", "1.0")
    _url("https://sipsense.ai/learn", "weekly", "0.8")
    _url("https://sipsense.ai/learn/glossary", "monthly", "0.6")

    for slug in CATEGORY_SLUGS:
        _url(f"https://sipsense.ai/learn/categories/{slug}", "monthly", "0.8")

    for slug in DISTILLERY_SLUGS:
        _url(f"https://sipsense.ai/learn/distilleries/{slug}", "monthly", "0.7")

    _url("https://sipsense.ai/lists", "weekly", "0.8")
    for tl in TOP_LIST_DEFS:
        _url(f"https://sipsense.ai/lists/{tl['slug']}", "weekly", "0.7")

    whiskey_ids = (
        db.query(models.Whiskey.id)
        .filter(models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != "")
        .order_by(models.Whiskey.rating_count.desc())
        .all()
    )
    for (wid,) in whiskey_ids:
        _url(f"https://sipsense.ai/whiskey/{wid}", "weekly", "0.6")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=3600"})


@router.get("/og/whiskey/{whiskey_id}", response_class=HTMLResponse)
def whiskey_og(whiskey_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    """Prerendered whiskey page with OG tags for social/search crawlers."""
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
        "<!DOCTYPE html>\n<html><head>\n"
        f"<title>{title}</title>\n"
        f'<meta name="description" content="{desc}"/>\n'
        f'<link rel="canonical" href="{url}"/>\n'
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
        "</head><body>\n"
        f"<h1>{title}</h1><p>{desc}</p>\n"
        f'<p><a href="{url}">View on SipSense</a></p>\n'
        "</body></html>"
    )
    return HTMLResponse(content=page)


@router.get("/prerender/", response_class=HTMLResponse)
def prerender_home(db: Session = Depends(get_db)):
    """Prerendered homepage for search crawlers."""
    top = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.rating_count > 0)
        .order_by(models.Whiskey.rating_avg.desc())
        .limit(20).all()
    )
    items = "\n".join(
        f'<li><a href="https://sipsense.ai/whiskey/{w.id}">'
        f"{html.escape(w.name)} \u2014 {html.escape(w.distillery or '')}</a></li>"
        for w in top
    )
    body = (
        "<h1>SipSense \u2014 Discover Your Perfect Whiskey</h1>\n"
        "<p>AI-powered whiskey recommendations, tasting notes, and a community "
        "of enthusiasts. Rate, track, and discover your next favorite pour.</p>\n"
        f"<h2>Top Rated Whiskeys</h2>\n<ul>{items}</ul>\n"
        "<h2>Explore</h2>\n<ul>\n"
        '<li><a href="https://sipsense.ai/learn">Learn About Whiskey</a></li>\n'
        '<li><a href="https://sipsense.ai/lists">Top Lists</a></li>\n</ul>'
    )
    return HTMLResponse(content=_prerender_page(
        "SipSense \u2014 Discover Your Perfect Whiskey",
        "AI-powered whiskey recommendations, tasting notes, and a community of enthusiasts.",
        "https://sipsense.ai/", body))


@router.get("/prerender/learn", response_class=HTMLResponse)
def prerender_learn():
    """Prerendered learn hub."""
    cats = "\n".join(
        f'<li><a href="https://sipsense.ai/learn/categories/{c["slug"]}">'
        f'{html.escape(c["title"])}</a> \u2014 {html.escape(c["tagline"])}</li>'
        for c in CATEGORIES
    )
    dists = "\n".join(
        f'<li><a href="https://sipsense.ai/learn/distilleries/{d["slug"]}">'
        f'{html.escape(d["title"])}</a> \u2014 {html.escape(d["tagline"])}</li>'
        for d in DISTILLERIES
    )
    body = (
        "<h1>Learn About Whiskey</h1>\n"
        "<p>Whiskey guides, distillery stories, and a complete glossary.</p>\n"
        f"<h2>Category Guides</h2>\n<ul>\n{cats}\n</ul>\n"
        f"<h2>Distillery Stories</h2>\n<ul>\n{dists}\n</ul>\n"
        '<p><a href="https://sipsense.ai/learn/glossary">Whiskey Glossary</a></p>'
    )
    return HTMLResponse(content=_prerender_page(
        "Learn About Whiskey | SipSense",
        "Whiskey guides, distillery stories, and a complete glossary.",
        "https://sipsense.ai/learn", body))


@router.get("/prerender/learn/glossary", response_class=HTMLResponse)
def prerender_glossary():
    """Prerendered glossary page."""
    terms = "\n".join(
        f"<dt><strong>{html.escape(g['term'])}</strong></dt>"
        f"<dd>{html.escape(g['definition'])}</dd>"
        for g in sorted(GLOSSARY, key=lambda x: x["term"])
    )
    body = (
        "<h1>Whiskey Glossary</h1>\n"
        "<p>A complete whiskey glossary \u2014 30+ terms explained simply.</p>\n"
        f"<dl>\n{terms}\n</dl>"
    )
    return HTMLResponse(content=_prerender_page(
        "Whiskey Glossary | SipSense",
        "A complete whiskey glossary \u2014 30+ terms explained simply.",
        "https://sipsense.ai/learn/glossary", body))


@router.get("/prerender/learn/categories/{slug}", response_class=HTMLResponse)
def prerender_category(slug: str):
    """Prerendered category guide."""
    cat = next((c for c in CATEGORIES if c["slug"] == slug), None)
    if not cat:
        raise HTTPException(status_code=404, detail="Not found")
    paragraphs = "\n".join(f"<p>{html.escape(p)}</p>" for p in cat["body"])
    facts = "\n".join(f"<li>{html.escape(f)}</li>" for f in cat["quick_facts"])
    bottles = "\n".join(f"<li>{html.escape(b)}</li>" for b in cat["entry_bottles"])
    body = (
        f"<h1>{html.escape(cat['title'])} Guide | SipSense</h1>\n"
        f"<p>{html.escape(cat['tagline'])}</p>\n"
        f"<h2>Quick Facts</h2>\n<ul>\n{facts}\n</ul>\n"
        f"{paragraphs}\n"
        f"<h2>Where to Start</h2>\n<ul>\n{bottles}\n</ul>"
    )
    return HTMLResponse(content=_prerender_page(
        f"{cat['title']} Guide | SipSense", cat["tagline"],
        f"https://sipsense.ai/learn/categories/{slug}", body))


@router.get("/prerender/learn/distilleries/{slug}", response_class=HTMLResponse)
def prerender_distillery(slug: str):
    """Prerendered distillery page."""
    dist = next((d for d in DISTILLERIES if d["slug"] == slug), None)
    if not dist:
        raise HTTPException(status_code=404, detail="Not found")
    paragraphs = "\n".join(f"<p>{html.escape(p)}</p>" for p in dist["body"])
    known = "\n".join(f"<li>{html.escape(k)}</li>" for k in dist["known_for"])
    body = (
        f"<h1>{html.escape(dist['title'])} \u2014 {html.escape(dist['location'])} | SipSense</h1>\n"
        f"<p>{html.escape(dist['tagline'])}</p>\n"
        f"<h2>Known For</h2>\n<ul>\n{known}\n</ul>\n{paragraphs}"
    )
    return HTMLResponse(content=_prerender_page(
        f"{dist['title']} \u2014 {dist['location']} | SipSense", dist["tagline"],
        f"https://sipsense.ai/learn/distilleries/{slug}", body))


@router.get("/prerender/lists", response_class=HTMLResponse)
def prerender_lists():
    """Prerendered top lists index."""
    items = "\n".join(
        f'<li><a href="https://sipsense.ai/lists/{tl["slug"]}">'
        f'{html.escape(tl["title"])}</a> \u2014 {html.escape(tl["description"])}</li>'
        for tl in TOP_LIST_DEFS
    )
    body = (
        "<h1>Top Whiskey Lists | SipSense</h1>\n"
        "<p>Community-curated whiskey rankings.</p>\n"
        f"<ul>\n{items}\n</ul>"
    )
    return HTMLResponse(content=_prerender_page(
        "Top Whiskey Lists | SipSense",
        "Community-curated whiskey rankings.",
        "https://sipsense.ai/lists", body))


@router.get("/prerender/lists/{slug}", response_class=HTMLResponse)
def prerender_list_detail(slug: str, db: Session = Depends(get_db)):
    """Prerendered individual top list."""
    tl_def = next((t for t in TOP_LIST_DEFS if t["slug"] == slug), None)
    if not tl_def:
        raise HTTPException(status_code=404, detail="Not found")
    tl = db.query(models.TopList).filter(models.TopList.slug == slug).first()
    items_html = ""
    if tl:
        entries = (
            db.query(models.TopListEntry)
            .filter(models.TopListEntry.top_list_id == tl.id)
            .order_by(models.TopListEntry.rank).limit(20).all()
        )
        whiskey_ids = [e.whiskey_id for e in entries]
        whiskeys = {w.id: w for w in db.query(models.Whiskey).filter(
            models.Whiskey.id.in_(whiskey_ids)).all()} if whiskey_ids else {}
        items = []
        for e in entries:
            w = whiskeys.get(e.whiskey_id)
            if w:
                items.append(
                    f'<li>#{e.rank} <a href="https://sipsense.ai/whiskey/{w.id}">'
                    f"{html.escape(w.name)}</a> \u2014 {html.escape(w.distillery or '')}</li>"
                )
        items_html = f"\n<ul>\n{''.join(items)}\n</ul>" if items else ""
    body = (
        f"<h1>{html.escape(tl_def['title'])} | SipSense</h1>\n"
        f"<p>{html.escape(tl_def['description'])}</p>{items_html}"
    )
    return HTMLResponse(content=_prerender_page(
        f"{tl_def['title']} | SipSense", tl_def["description"],
        f"https://sipsense.ai/lists/{slug}", body))
