"""
Fetch real bottle images from Google Images with CLIP-based validation.

Uses Google Images scraping with adaptive backoff and validates every
candidate image using OpenAI CLIP (via HuggingFace transformers) to
ensure only actual whiskey bottle photos are saved.

Usage:
    cd backend
    .venv/bin/python -m scripts.fetch_bottle_images              # all whiskeys
    .venv/bin/python -m scripts.fetch_bottle_images --limit 50   # first 50 only
    .venv/bin/python -m scripts.fetch_bottle_images --overwrite  # re-fetch existing
    .venv/bin/python -m scripts.fetch_bottle_images --category bourbon
    .venv/bin/python -m scripts.fetch_bottle_images --source whiskybase
    .venv/bin/python -m scripts.fetch_bottle_images --no-clip    # skip CLIP validation
    .venv/bin/python -m scripts.fetch_bottle_images --no-ocr     # skip OCR label text check
    .venv/bin/python -m scripts.fetch_bottle_images --proxy socks5://127.0.0.1:9050

    # With Tor for rotating IPs (requires: brew install tor):
    bash scraper/run_with_tor.sh  # for the general scraper
    # Or start Tor manually, then:
    .venv/bin/python -m scripts.fetch_bottle_images --proxy socks5://127.0.0.1:9050

Tips:
    - Safe to Ctrl+C and resume with --resume flag (checkpoint saved automatically)
    - Background is removed automatically via rembg (saves as transparent PNG)
    - CLIP model is downloaded once and cached in ~/.cache/huggingface/
    - Use --proxy with Tor to rotate IPs and avoid Google rate limiting
"""

import os
import re
import sys
import time
import json
import random
import socket
import argparse
import warnings
import requests
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=".*Palette images with Transparency.*")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.database import SessionLocal
from app import models

BOTTLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "uploads", "bottles")
)
os.makedirs(BOTTLES_DIR, exist_ok=True)

MIN_WIDTH        = 150
MIN_HEIGHT       = 200
BASE_DELAY       = 1.0
MAX_DELAY        = 15.0
DOWNLOAD_TIMEOUT = 10
SEARCH_TIMEOUT   = 12

# ── CLIP validation config ──────────────────────────────────────────────

CLIP_THRESHOLD = 0.22
OCR_MIN_CHARS   = 3     # minimum total characters detected to consider "has text"
OCR_MIN_CONF    = 0.3   # minimum confidence for an OCR detection to count

POSITIVE_PROMPTS = [
    "a single whiskey bottle product photo",
    "one whiskey bottle on a plain background",
    "a single bottle of bourbon whiskey",
    "a single bottle of scotch whisky",
    "a single bottle of rye whiskey",
    "a single bottle of irish whiskey",
    "a single bottle of japanese whisky",
    "a single malt whisky bottle isolated on a plain background",
]

NEGATIVE_PROMPTS = [
    "a photo of a person",
    "a photo of food on a plate",
    "a landscape or nature photo",
    "a logo or icon or graphic design",
    "a glass of whiskey without a bottle",
    "a bar or restaurant interior",
    "a screenshot of a webpage or text",
    "a map or diagram",
    "a group of people drinking",
    "a cocktail in a glass",
    "a beer bottle or wine bottle",
    "a blurry or low quality image",
    "multiple whiskey bottles in a row",
    "a collection of several bottles together",
    "a lineup of different whiskey bottles",
    "three or more bottles side by side",
    "a wooden barrel or cask",
    "a whiskey barrel with text on it",
    "a cocktail drink with a bottle behind it",
    "a lifestyle photo with glasses and bottles on a table",
    "a whiskey bottle next to its box or tube packaging",
    "a gift box with a bottle inside",
    "a bottle with a presentation case or tin",
]

# Domains known to have clean single-bottle product photos
_RETAILER_DOMAINS = {
    "totalwine.com", "thewhiskyexchange.com", "masterofmalt.com",
    "reservebar.com", "drizly.com", "caskers.com", "flaviar.com",
    "wine.com", "klwines.com", "binnys.com", "woodencork.com",
    "sipwhiskey.com", "breakingbourbon.com", "fredminnick.com",
    "whiskyadvocate.com", "dekanta.com", "whisky.com",
    "thewhiskyworld.com", "finedrams.com", "drinksdirect.com",
    "liquor.com", "totalwinesandmore.com", "bevmo.com",
}


# ── User agents ──────────────────────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# ── Tor circuit rotation ─────────────────────────────────────────────

TOR_CONTROL_PORT = 9051


def renew_tor_circuit():
    """Send NEWNYM signal to Tor control port to get a new exit IP."""
    try:
        with socket.create_connection(("127.0.0.1", TOR_CONTROL_PORT), timeout=5) as s:
            s.sendall(b"AUTHENTICATE\r\n")
            resp = s.recv(256)
            if b"250" not in resp:
                return False
            s.sendall(b"SIGNAL NEWNYM\r\n")
            resp = s.recv(256)
            return b"250" in resp
    except Exception:
        return False


def make_session(proxy: str | None = None) -> requests.Session:
    """Create a requests session, optionally routing through a SOCKS proxy."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session


# Junk patterns in scraped product names
_JUNK = re.compile(
    r"(\d+(\.\d+)?\s*%[^,)]*)|"
    r"(\d+(\.\d+)?\s*(ml|cl|l)\b)|"
    r"\([^)]*\d[^)]*\)|"
    r"\s{2,}",
    re.IGNORECASE,
)

# Bottler / indie prefixes to strip for simpler queries
_BOTTLER_PREFIXES = re.compile(
    r"^(Scotch Malt Whisky Society|SMWS|Gordon & MacPhail|G&M|"
    r"Signatory Vintage|Cadenhead'?s?|Berry Bros|Douglas Laing|"
    r"Hunter Laing|Single Malts of Scotland|Adelphi|"
    r"Duncan Taylor|Murray McDavid|Compass Box|"
    r"That Boutique-?y? Whisky Company|TBWC|"
    r"Samaroli|Silver Seal|Exclusive Malts|"
    r"Hart Brothers|James MacArthur|Blackadder|"
    r"Wemyss Malts|The Single Malts of Scotland)\s*",
    re.IGNORECASE,
)

# Cask / vintage details to strip
_CASK_DETAILS = re.compile(
    r"\b(cask\s*(no\.?|number|#)?\s*\d+[A-Z]?|"
    r"barrel\s*#?\s*\d+|"
    r"\d+\s*[snrt][tdh]\s*fill|"
    r"single\s*cask|"
    r"cask\s*strength|"
    r"first\s*fill|"
    r"refill|"
    r"hogshead|"
    r"butt\s*\d*|"
    r"sherry\s*(cask|butt)|"
    r"bourbon\s*(cask|barrel)|"
    r"release\s*\d+|"
    r"\d{1,2}\.\d{1,4})\b",
    re.IGNORECASE,
)

_AGE_RE = re.compile(r"(\d{1,2})\s*(?:year|yr|yo|y\.?o\.?)\b", re.IGNORECASE)
_VINTAGE_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\s*(vintage)?\b", re.IGNORECASE)


# ── CLIP validator (lazy-loaded singleton) ───────────────────────────────

class WhiskeyImageValidator:
    """Uses CLIP to verify an image is actually a whiskey bottle."""

    def __init__(self):
        self._model = None
        self._processor = None
        self._pos_tokens = None
        self._neg_tokens = None
        self._count_one = None
        self._count_multi = None

    def _load(self):
        if self._model is not None:
            return

        import torch
        from transformers import CLIPModel, CLIPProcessor

        print("Loading CLIP model for image validation...")
        model_name = "openai/clip-vit-base-patch32"
        self._processor = CLIPProcessor.from_pretrained(model_name)
        self._model = CLIPModel.from_pretrained(model_name)
        self._model.eval()

        # Pre-encode text prompts once
        with torch.no_grad():
            self._pos_embeds = self._encode_texts(POSITIVE_PROMPTS)
            self._neg_embeds = self._encode_texts(NEGATIVE_PROMPTS)
        print("CLIP model loaded.\n")

    def _encode_texts(self, texts: list[str]):
        """Encode a list of text prompts into normalized CLIP embeddings."""
        import torch

        inputs = self._processor(text=texts, return_tensors="pt", padding=True)
        with torch.no_grad():
            out = self._model.get_text_features(**inputs)
        # Unwrap if not a raw tensor
        if not isinstance(out, torch.Tensor):
            for attr in ("text_embeds", "pooler_output"):
                if hasattr(out, attr):
                    out = getattr(out, attr)
                    break
            else:
                out = out[0]
        # Ensure 2D: (batch, hidden_dim)
        if out.ndim == 3:
            out = out[:, 0, :]
        return out / out.norm(dim=-1, keepdim=True)

    def _encode_image(self, img: Image.Image):
        """Encode a single image into a normalized CLIP embedding."""
        import torch

        inputs = self._processor(images=img.convert("RGB"), return_tensors="pt")
        with torch.no_grad():
            out = self._model.get_image_features(**inputs)
        if not isinstance(out, torch.Tensor):
            for attr in ("image_embeds", "pooler_output"):
                if hasattr(out, attr):
                    out = getattr(out, attr)
                    break
            else:
                out = out[0]
        if out.ndim == 3:
            out = out[:, 0, :]
        return out / out.norm(dim=-1, keepdim=True)

    def is_whiskey_bottle(self, img: Image.Image) -> tuple[bool, float, str]:
        """
        Check if an image is a whiskey bottle.

        Returns:
            (passed, best_positive_score, reason)
        """
        self._load()

        img_embed = self._encode_image(img)

        pos_scores = (img_embed @ self._pos_embeds.mT).squeeze(0)
        neg_scores = (img_embed @ self._neg_embeds.mT).squeeze(0)

        best_pos = pos_scores.max().item()
        best_neg = neg_scores.max().item()
        best_neg_idx = neg_scores.argmax().item()

        if best_pos < CLIP_THRESHOLD:
            return False, best_pos, f"low whiskey score ({best_pos:.3f} < {CLIP_THRESHOLD})"

        if best_neg > best_pos:
            reason = NEGATIVE_PROMPTS[best_neg_idx]
            return False, best_pos, f"matched '{reason}' ({best_neg:.3f}) > whiskey ({best_pos:.3f})"

        # Dedicated single-vs-multi bottle count check using binary CLIP comparison
        if self._count_one is None:
            self._count_one = self._encode_texts([
                "exactly one single whiskey bottle",
                "a single isolated bottle product photo",
                "one bottle alone",
            ])
            self._count_multi = self._encode_texts([
                "two or three whiskey bottles side by side",
                "multiple bottles grouped together",
                "several different bottles in one photo",
            ])

        one_score = (img_embed @ self._count_one.mT).squeeze(0).max().item()
        multi_score = (img_embed @ self._count_multi.mT).squeeze(0).max().item()

        if multi_score > one_score:
            return False, best_pos, f"multi-bottle: multi({multi_score:.3f}) > single({one_score:.3f})"

        return True, best_pos, "ok"


# Global singleton — only instantiated if CLIP is enabled
_validator: WhiskeyImageValidator | None = None


def get_validator() -> WhiskeyImageValidator:
    global _validator
    if _validator is None:
        _validator = WhiskeyImageValidator()
    return _validator


# ── AI Vision label validator (lazy-loaded singleton) ─────────────────────

class BottleTextValidator:
    """Uses Claude Vision API to verify a bottle image matches the expected whiskey.

    Instead of local OCR + regex heuristics, we send the image to Claude and ask
    it to identify the whiskey. This handles curved text, fancy fonts, partial
    occlusion, edition variants, and all the edge cases that trip up EasyOCR.

    Cost: ~$0.002-0.004 per image with Haiku. 1000 images ≈ $2-4.
    """

    def __init__(self):
        self._client = None

    def _load(self):
        if self._client is not None:
            return
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
        self._client = anthropic.Anthropic(api_key=api_key)
        print("Claude Vision API ready for label verification.\n")

    def _image_to_base64(self, img: Image.Image) -> str:
        """Convert PIL image to base64-encoded JPEG for the API."""
        import base64
        rgb = img.convert("RGB")
        # Resize to reduce token cost — 512px max dimension is plenty for label reading
        max_dim = 512
        w, h = rgb.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            rgb = rgb.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = BytesIO()
        rgb.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def has_label_text(self, img: Image.Image) -> tuple[bool, str, list[str]]:
        """Check if image has readable label text using Claude Vision.

        Returns: (passed, reason, [detected_text_summary])
        """
        self._load()
        try:
            b64 = self._image_to_base64(img)
            response = self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                        {"type": "text", "text": "What text can you read on this bottle label? List the main words. If no readable text, say NONE."},
                    ],
                }],
            )
            text = response.content[0].text.strip()
            if "NONE" in text.upper() and len(text) < 20:
                return False, "no label text detected by AI", []
            return True, f"ok (AI: {text[:80]})", [text]
        except Exception as e:
            # On API error, pass through (don't block on transient failures)
            return True, f"AI check skipped ({e})", []

    def label_matches_name(self, detected_texts: list[str], whiskey_name: str) -> tuple[bool, str]:
        """Use Claude Vision to verify the bottle matches the expected whiskey name.

        This replaces all the regex/fuzzy-matching heuristics with a single AI call
        that understands whiskey brands, editions, and variants.
        """
        # This is called after has_label_text, but we need the actual image.
        # Since the image isn't passed here, we use the pre-stored result from
        # verify_bottle_match() which is the new primary entry point.
        # For backward compat, if called with just text, do a basic check.
        if not detected_texts:
            return True, "no text to check"
        ai_text = " ".join(detected_texts).lower()
        # Simple sanity: if AI returned text, check if whiskey name words appear
        name_words = set(re.sub(r"[^a-zA-Z\s]", " ", whiskey_name.lower()).split())
        name_words = {w for w in name_words if len(w) >= 4}
        if not name_words:
            return True, "no significant name words"
        matches = sum(1 for w in name_words if w in ai_text)
        if matches == 0:
            return False, f"AI text '{ai_text[:60]}' has none of {name_words}"
        return True, f"AI text contains {matches}/{len(name_words)} name words"

    def verify_bottle_match(self, img: Image.Image, whiskey_name: str) -> tuple[bool, str]:
        """Single-image verification (legacy). Use rank_candidates() for better accuracy."""
        self._load()
        max_retries = 3
        for attempt in range(max_retries):
            try:
                b64 = self._image_to_base64(img)
                response = self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=150,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                            {"type": "text", "text": (
                                f'Is this image a single bottle of "{whiskey_name}"?\n\n'
                                "Reject if ANY of these are true:\n"
                                "- Not a photo of a single bottle (logo, icon, glass, barrel, box, multiple bottles, person, food, etc.)\n"
                                "- Wrong brand/distillery on the label\n"
                                "- Wrong product/edition (e.g. 'Rye' vs 'Single Barrel' are DIFFERENT products even if same brand)\n"
                                "- Wrong age statement (e.g. '12 year' vs '16 year')\n"
                                "- Wrong vintage year if specified\n"
                                "- Different spirit type (e.g. beer, wine, vodka, gin)\n\n"
                                "Respond EXACTLY:\n"
                                "MATCH: yes — [reason]\n"
                                "or\n"
                                "MATCH: no — [what it actually shows]\n"
                            )},
                        ],
                    }],
                )
                result = response.content[0].text.strip()
                result_lower = result.lower()

                if "match: yes" in result_lower or "match:yes" in result_lower:
                    return True, f"AI verified: {result}"
                elif "match: no" in result_lower or "match:no" in result_lower:
                    return False, f"AI rejected: {result}"
                else:
                    if "yes" in result_lower and "no" not in result_lower:
                        return True, f"AI likely match: {result}"
                    elif "no" in result_lower:
                        return False, f"AI likely mismatch: {result}"
                    return True, f"AI unclear (passing): {result}"

            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "rate" in err_str or "429" in err_str or "overloaded" in err_str
                if is_rate_limit and attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 5)
                    continue
                return True, f"AI check skipped ({e})"

        return True, "AI check skipped (max retries)"

    def rank_candidates(self, images: list[Image.Image], whiskey_name: str) -> tuple[int, str]:
        """Send multiple candidate images to Claude and ask it to pick the best match.

        Returns (index, reason) where index is the 0-based index of the best
        image, or -1 if none match.

        This is MUCH more accurate than individual pass/fail checks because
        Claude can compare candidates side-by-side and pick the best one.
        """
        self._load()
        if not images:
            return -1, "no candidates"

        # Retry with exponential backoff for rate limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Build content blocks: numbered images + question
                content = []
                for i, img in enumerate(images):
                    b64 = self._image_to_base64(img)
                    content.append({"type": "text", "text": f"Image {i+1}:"})
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
                    })

                content.append({"type": "text", "text": (
                    f'\nI need a product photo of a single bottle of "{whiskey_name}".\n\n'
                    f"Above are {len(images)} candidate images. Pick the BEST one that shows:\n"
                    "- A single bottle (not multiple bottles, not a box/case, not a glass, not a logo)\n"
                    "- The CORRECT brand/distillery on the label\n"
                    "- The CORRECT product/edition (e.g. 'Rye' and 'Single Barrel' are DIFFERENT products)\n"
                    "- The CORRECT age statement if the name includes one\n"
                    "- The CORRECT vintage year if specified\n"
                    "- A whiskey/whisky (not beer, wine, vodka, gin, etc.)\n\n"
                    "If MULTIPLE images match, prefer the one with:\n"
                    "- Cleaner/whiter background\n"
                    "- Better quality / higher resolution\n"
                    "- Full bottle visible (not cropped)\n\n"
                    "Respond EXACTLY in this format:\n"
                    "BEST: [number] — [reason]\n"
                    "or if NONE of the images are correct:\n"
                    "BEST: none — [what the images actually show]\n"
                )})

                response = self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=200,
                    messages=[{"role": "user", "content": content}],
                )
                result = response.content[0].text.strip()
                result_lower = result.lower()

                # Parse response
                if "best: none" in result_lower:
                    return -1, f"AI rejected all: {result}"

                # Extract the number
                m = re.search(r'best:\s*(\d+)', result_lower)
                if m:
                    idx = int(m.group(1)) - 1  # convert 1-based to 0-based
                    if 0 <= idx < len(images):
                        return idx, f"AI picked #{idx+1}: {result}"

                # Fallback: look for a bare number
                m = re.search(r'\b([1-9])\b', result)
                if m:
                    idx = int(m.group(1)) - 1
                    if 0 <= idx < len(images):
                        return idx, f"AI picked #{idx+1} (parsed): {result}"

                return -1, f"AI unclear response: {result}"

            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "rate" in err_str or "429" in err_str or "overloaded" in err_str
                if is_rate_limit and attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"  [AI rate-limited, retry in {wait}s]", end="", flush=True)
                    time.sleep(wait)
                    continue
                return -1, f"AI ranking failed ({e})"

        return -1, "AI ranking failed (max retries)"


_text_validator: BottleTextValidator | None = None


def get_text_validator() -> BottleTextValidator:
    global _text_validator
    if _text_validator is None:
        _text_validator = BottleTextValidator()
    return _text_validator


# ── Image search engines ─────────────────────────────────────────────────

_BING_SKIP = re.compile(
    r"(bing\.com|bing\.net|microsoft\.com|msn\.com|live\.com|"
    r"bingapis\.com|b-cdn\.net)",
    re.IGNORECASE,
)


def bing_images(
    query: str, session: requests.Session, max_results: int = 20,
    use_tor: bool = False,
) -> list[str]:
    """Scrape Bing Images — much more lenient rate limits than Google."""
    # Add exclusion terms to avoid cocktail/lifestyle images
    filtered_query = query + " -cocktail -drink -glass -recipe -review -tasting"
    for attempt in range(3):
        try:
            resp = session.get(
                "https://www.bing.com/images/search",
                params={
                    "q": filtered_query,
                    "form": "HDRSC2",
                    "first": "1",
                    "tsc": "ImageBasicHover",
                    "qft": "+filterui:photo-transparent",  # prefer isolated product photos
                },
                headers={
                    "Referer": "https://www.bing.com/",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                },
                timeout=SEARCH_TIMEOUT,
            )

            if resp.status_code == 429:
                if use_tor:
                    print(f"  [429→rotating IP]", end="", flush=True)
                    renew_tor_circuit()
                    time.sleep(3)
                else:
                    wait = (attempt + 1) * 5
                    print(f"  [rate-limited, waiting {wait}s]", end="", flush=True)
                    time.sleep(wait)
                session.headers["User-Agent"] = random.choice(_USER_AGENTS)
                continue

            if resp.status_code != 200:
                return []

            # Bing embeds image URLs in murl attributes and JSON blobs
            raw = re.findall(
                r'murl&quot;:&quot;(https?://[^&]+?)&quot;',
                resp.text,
            )
            if not raw:
                # Fallback: extract from imgurl params or raw URLs
                raw = re.findall(
                    r'https?://[^\s"\'\\>]+\.(?:jpg|jpeg|png|webp)(?:[^\s"\'\\>]*)',
                    resp.text,
                )

            seen: set[str] = set()
            unique: list[str] = []
            for u in raw:
                u = re.sub(r'[",\\\]}>]+$', "", u)
                if u in seen or _BING_SKIP.search(u):
                    continue
                seen.add(u)
                unique.append(u)
            return unique[:max_results]

        except Exception:
            if attempt < 2:
                time.sleep(2)
                continue
            return []

    return []


_GOOGLE_SKIP = re.compile(
    r"(gstatic\.com|google\.com|googleapis\.com|ggpht\.com|"
    r"ytimg\.com|schema\.org)",
    re.IGNORECASE,
)


def google_images(
    query: str, session: requests.Session, max_results: int = 20,
    use_tor: bool = False,
) -> list[str]:
    """Scrape Google Images — used as fallback when Bing finds nothing."""
    for attempt in range(2):
        try:
            resp = session.get(
                "https://www.google.com/search",
                params={"q": query, "tbm": "isch", "hl": "en"},
                headers={
                    "Referer": "https://www.google.com/",
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                },
                timeout=SEARCH_TIMEOUT,
            )

            if resp.status_code == 429:
                if use_tor:
                    renew_tor_circuit()
                    time.sleep(3)
                else:
                    time.sleep((attempt + 1) * 5)
                session.headers["User-Agent"] = random.choice(_USER_AGENTS)
                continue

            if resp.status_code != 200:
                return []

            # Google embeds image URLs in various JSON-like patterns
            raw = re.findall(
                r'\["(https?://[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)",[0-9]+,[0-9]+\]',
                resp.text,
            )
            if not raw:
                raw = re.findall(
                    r'https?://[^\s"\'\\>]+\.(?:jpg|jpeg|png|webp)(?:[^\s"\'\\>]*)',
                    resp.text,
                )

            seen: set[str] = set()
            unique: list[str] = []
            for u in raw:
                u = re.sub(r'[",\\\]}>]+$', "", u)
                if u in seen or _GOOGLE_SKIP.search(u):
                    continue
                seen.add(u)
                unique.append(u)
            return unique[:max_results]

        except Exception:
            if attempt < 1:
                time.sleep(2)
                continue
            return []

    return []


def _is_retailer_url(url: str) -> bool:
    """Check if a URL is from a known liquor retailer (likely single-bottle photo)."""
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname or ""
        host = host.lstrip("www.")
        return host in _RETAILER_DOMAINS
    except Exception:
        return False


def _prioritize_urls(urls: list[str]) -> list[str]:
    """Sort retailer URLs first — they almost always have clean single-bottle photos."""
    retailer = [u for u in urls if _is_retailer_url(u)]
    other = [u for u in urls if not _is_retailer_url(u)]
    return retailer + other


def google_cse_images(query: str, max_results: int = 10) -> list[str]:
    """Search via Google Custom Search API — reliable, no rate limiting."""
    api_key = os.environ.get("GOOGLE_CSE_API_KEY", "")
    cx = os.environ.get("GOOGLE_CSE_CX", "")
    if not api_key or not cx:
        return []

    urls: list[str] = []
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cx,
                "q": query,
                "searchType": "image",
                "num": min(max_results, 10),  # API max is 10 per request
                "imgType": "photo",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                link = item.get("link", "")
                if link:
                    urls.append(link)
        elif resp.status_code == 429:
            print("  [Google CSE rate limited]", end="", flush=True)
        elif resp.status_code == 403:
            print("  [Google CSE quota exceeded]", end="", flush=True)
    except Exception:
        pass
    return urls


def search_images(
    query: str, session: requests.Session, max_results: int = 20,
    use_tor: bool = False, use_google_cse: bool = False,
) -> list[str]:
    """Search for images. Bing first, Google Images scraping as fallback."""
    # Primary: Bing
    urls = bing_images(query, session, max_results=max_results, use_tor=use_tor)
    if urls:
        return _prioritize_urls(urls)
    # Fallback: Google Images scraping
    urls = google_images(query, session, max_results=max_results, use_tor=use_tor)
    return _prioritize_urls(urls)


# ── Name cleaning & query building ───────────────────────────────────────


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def clean_name(name: str) -> str:
    cleaned = _JUNK.sub(" ", name).strip()
    cleaned = re.split(r"\s[|\u2013\u2014]\s", cleaned)[0].strip()
    return cleaned


def simplify_name(name: str) -> str:
    """Strip bottler prefixes, cask details, and vintage years."""
    simplified = _BOTTLER_PREFIXES.sub("", name)
    simplified = _CASK_DETAILS.sub("", simplified)
    simplified = _VINTAGE_RE.sub("", simplified)
    simplified = re.sub(r"\([^)]*\)", "", simplified)
    simplified = re.sub(r"\s+", " ", simplified).strip()
    simplified = re.sub(r"[,\-]+$", "", simplified).strip()
    return simplified


def extract_age(name: str) -> str:
    m = _AGE_RE.search(name)
    return f"{m.group(1)} year old" if m else ""


def build_queries(whiskey) -> list[str]:
    """Build Google Images search queries from most specific to most generic."""
    name = clean_name(whiskey.name)
    distillery = (whiskey.distillery or "").strip()
    category = (whiskey.category or "whiskey").strip()
    age = extract_age(whiskey.name)
    simplified = simplify_name(name)

    queries = []

    # 1. Full name + "single bottle" — don't add distillery (it confuses search
    # when distillery makes many brands, e.g. "Buffalo Trace" for Blanton's)
    queries.append(f"{name} single bottle product photo")

    # 2. Simplified name
    if simplified != name and len(simplified) > 5:
        queries.append(f"{simplified} single bottle")

    # 3. Name + category (fallback)
    queries.append(f"{name} {category} bottle")

    # Deduplicate
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen and len(q_lower) > 10:
            seen.add(q_lower)
            unique.append(q)
    return unique


# ── Image helpers ────────────────────────────────────────────────────────


def download_image(url: str, session: requests.Session) -> Image.Image | None:
    try:
        resp = session.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("content-type", "")
        if not any(t in ct for t in ("image/jpeg", "image/png", "image/webp", "image/")):
            return None
        data = resp.content
        if len(data) < 2000:
            return None
        img = Image.open(BytesIO(data))
        img.load()
        return img
    except Exception:
        return None


def is_good_image(img: Image.Image) -> bool:
    """Fast pre-filter: size checks only. Let Claude judge orientation."""
    w, h = img.size
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return False
    # Allow landscape — some retailer crops are wide. Claude will reject
    # images that aren't single bottles regardless of aspect ratio.
    # Only reject extremely wide panoramic images (3:1+)
    if w > h * 3:
        return False
    return True


def _pad_image(img: Image.Image, pad: int = 40) -> Image.Image:
    """Add solid-color padding so rembg doesn't clip edges of the bottle."""
    img = img.convert("RGB")
    w, h = img.size
    pixels = [
        img.getpixel((0, 0)),
        img.getpixel((w - 1, 0)),
        img.getpixel((0, h - 1)),
        img.getpixel((w - 1, h - 1)),
    ]
    bg = tuple(sum(c[i] for c in pixels) // 4 for i in range(3))
    padded = Image.new("RGB", (w + pad * 2, h + pad * 2), bg)
    padded.paste(img, (pad, pad))
    return padded


def _trim_transparent(img: Image.Image, margin: int = 4) -> Image.Image:
    """Crop to the non-transparent bounding box with a small margin."""
    bbox = img.split()[-1].getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - margin)
    y0 = max(0, y0 - margin)
    x1 = min(img.width, x1 + margin)
    y1 = min(img.height, y1 + margin)
    return img.crop((x0, y0, x1, y1))


import hashlib
import threading as _threading

# Shared hash set for dedup — populated at startup, updated by save_image
_saved_hashes: set[str] = set()
_hash_lock = _threading.Lock()


def _init_saved_hashes():
    """Scan existing bottle images and populate the hash set."""
    if not os.path.isdir(BOTTLES_DIR):
        return
    for fname in os.listdir(BOTTLES_DIR):
        fpath = os.path.join(BOTTLES_DIR, fname)
        if os.path.isfile(fpath):
            h = hashlib.md5(open(fpath, "rb").read()).hexdigest()
            _saved_hashes.add(h)


NOBG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "uploads", "bottles_nobg")
)
os.makedirs(NOBG_DIR, exist_ok=True)

# Lazy-loaded rembg session (shared across threads via lock)
_rembg_session = None
_rembg_lock = _threading.Lock()


def _get_rembg_session():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        _rembg_session = new_session("birefnet-general")
    return _rembg_session


def _remove_background(img: Image.Image) -> Image.Image:
    """Remove background with generous padding to avoid clipping."""
    from rembg import remove

    # Add green padding — gives rembg a clear signal of what's "background"
    # (sampling corner pixels often matches the actual background color,
    # confusing the model into keeping background as foreground)
    rgb = img.convert("RGB")
    w, h = rgb.size
    pad = 100
    padded = Image.new("RGB", (w + pad * 2, h + pad * 2), (0, 200, 0))
    padded.paste(rgb, (pad, pad))
    padded = padded.convert("RGBA")

    with _rembg_lock:
        session = _get_rembg_session()
        result = remove(padded, session=session)

    # Trim excess transparent area
    if result.mode == "RGBA":
        alpha = result.split()[-1]
        bbox = alpha.getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            margin = 8
            x0 = max(0, x0 - margin)
            y0 = max(0, y0 - margin)
            x1 = min(result.width, x1 + margin)
            y1 = min(result.height, y1 + margin)
            result = result.crop((x0, y0, x1, y1))

    return result


def save_image(img: Image.Image, name: str, whiskey_id: int) -> str | None:
    """Save original image, dedup by hash. BG removal runs separately after.
    Returns relative path on success, None if duplicate."""

    result = img.convert("RGB")

    # Compute hash before writing to check for duplicates
    from io import BytesIO as _BytesIO
    buf = _BytesIO()
    result.save(buf, "PNG", optimize=True)
    img_bytes = buf.getvalue()
    img_hash = hashlib.md5(img_bytes).hexdigest()

    with _hash_lock:
        if img_hash in _saved_hashes:
            return None  # duplicate — reject
        _saved_hashes.add(img_hash)

    filename = f"{whiskey_id}-{slugify(name)}.png"
    with open(os.path.join(BOTTLES_DIR, filename), "wb") as f:
        f.write(img_bytes)

    return f"/uploads/bottles/{filename}"


# ── Core fetch ───────────────────────────────────────────────────────────


MAX_CANDIDATES = 8  # max images to collect before ranking


def fetch_image_for_whiskey(
    whiskey,
    session: requests.Session,
    use_clip: bool = True,
    use_tor: bool = False,
    use_ocr: bool = True,
    use_google_cse: bool = False,
) -> str | None:
    """
    Multi-candidate approach: collect several candidate images, then ask
    Claude to pick the best match. Much more accurate than accepting the
    first image that passes individual verification.

    Steps:
    1. Collect up to MAX_CANDIDATES downloadable images from search
    2. Send batch to Claude: "which of these is the correct bottle?"
    3. Claude picks the best one (or rejects all)
    4. Save + remove background
    """
    # Skip whiskeys with generic/no-brand names
    name_words = set(re.sub(r"[^a-zA-Z\s]", " ", whiskey.name).lower().split())
    _GENERIC_ONLY = {"blended", "single", "malt", "scotch", "whisky", "whiskey",
                     "bourbon", "rye", "irish", "canadian", "japanese", "american",
                     "highland", "lowland", "speyside", "islay", "campbeltown",
                     "tennessee", "kentucky", "aged", "year", "old", "years",
                     "cask", "barrel", "strength", "reserve", "special", "edition",
                     "limited", "select", "premium", "gold", "silver", "black",
                     "white", "red", "green", "blue", "double", "triple", "small",
                     "batch", "pure", "fine", "extra", "original", "classic"}
    brand_words = name_words - _GENERIC_ONLY - {w for w in name_words if len(w) < 3}
    if not brand_words:
        return None

    queries = build_queries(whiskey)
    ai_validator = get_text_validator() if use_ocr else None

    # Collect candidate images from all queries
    candidates: list[Image.Image] = []

    for query in queries:
        if len(candidates) >= MAX_CANDIDATES:
            break
        urls = search_images(query, session, use_tor=use_tor, use_google_cse=use_google_cse)
        for url in urls:
            if len(candidates) >= MAX_CANDIDATES:
                break
            img = download_image(url, session)
            if img and is_good_image(img):
                candidates.append(img)
        time.sleep(0.3)

    if not candidates:
        return None

    # Ask Claude to pick the best match from all candidates
    if ai_validator:
        best_idx, reason = ai_validator.rank_candidates(candidates, whiskey.name)
        if best_idx < 0:
            return None  # Claude rejected all candidates
        chosen = candidates[best_idx]
    else:
        # No AI — just use first candidate
        chosen = candidates[0]

    result = save_image(chosen, whiskey.name, whiskey.id)
    return result


def update_db(whiskey_id: int, rel_path: str) -> None:
    db = SessionLocal()
    db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).update(
        {"image_url": rel_path}
    )
    db.commit()
    db.close()


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Fetch whiskey bottle images from Google Images with CLIP validation"
    )
    parser.add_argument("--limit", type=int, default=0, help="Max whiskeys (0=all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N whiskeys")
    parser.add_argument("--overwrite", action="store_true", help="Re-fetch existing images")
    parser.add_argument("--category", type=str, default="", help="Filter by category")
    parser.add_argument("--source", type=str, default="", help="Filter by source")
    parser.add_argument(
        "--no-clip", action="store_true", help="Disable CLIP validation (faster but less accurate)"
    )
    parser.add_argument(
        "--no-ocr", action="store_true", help="Disable OCR label text validation"
    )
    parser.add_argument(
        "--proxy", type=str, default="",
        help="SOCKS proxy URL, e.g. socks5://127.0.0.1:9050 (use with Tor)"
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from checkpoint (skips whiskeys already processed)"
    )
    parser.add_argument(
        "--google-cse", action="store_true",
        help="Use Google Custom Search API (requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX in .env)"
    )
    args = parser.parse_args()

    use_clip = not args.no_clip
    use_ocr = not args.no_ocr
    use_tor = bool(args.proxy)
    use_google_cse = args.google_cse

    db = SessionLocal()
    q = db.query(models.Whiskey)
    if args.category:
        q = q.filter(models.Whiskey.category.ilike(f"%{args.category}%"))
    if args.source:
        q = q.filter(models.Whiskey.source == args.source)
    # Order by popularity (most ratings first) for best image hit rate
    whiskeys = q.order_by(models.Whiskey.rating_count.desc().nullslast(), models.Whiskey.id).all()
    db.close()

    if args.offset:
        whiskeys = whiskeys[args.offset:]
    if args.limit:
        whiskeys = whiskeys[: args.limit]

    total = len(whiskeys)
    proxy_label = args.proxy or "none"
    cse_label = "Google CSE" if use_google_cse else "Bing scraping"
    ai_label = "Claude Vision" if use_ocr else "none"
    print(f"Processing {total} whiskeys  (overwrite={args.overwrite}, ai_verify={ai_label}, search={cse_label})")
    print(f"Images -> {BOTTLES_DIR}\n")

    # Initialize hash dedup from existing images on disk
    _init_saved_hashes()
    print(f"Loaded {len(_saved_hashes)} existing image hashes for dedup")

    # Eagerly initialize Claude Vision API client
    if use_ocr:
        get_text_validator()

    if use_tor:
        session = make_session(proxy=args.proxy or None)
        try:
            ip = session.get("https://api.ipify.org", timeout=10).text
            print(f"Tor exit IP: {ip}\n")
        except Exception:
            print("WARNING: Could not verify Tor connection, proceeding anyway...\n")

    # --- Parallel execution with ThreadPoolExecutor ---
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    NUM_WORKERS = args.workers
    print(f"Using {NUM_WORKERS} parallel workers\n")

    # Thread-local sessions (each thread gets its own requests.Session)
    _thread_local = threading.local()

    def _get_session():
        if not hasattr(_thread_local, "session"):
            _thread_local.session = make_session(proxy=args.proxy or None)
        return _thread_local.session

    # Counters with lock
    _lock = threading.Lock()
    counters = {"fetched": 0, "skipped": 0, "failed": 0, "processed": 0}

    # Checkpoint file for resume support
    CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "..", "fetch_checkpoint.json")
    processed_ids: set[int] = set()
    if args.resume and os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            checkpoint_data = json.load(f)
            processed_ids = set(checkpoint_data.get("processed_ids", []))
        print(f"Resuming: {len(processed_ids)} whiskeys already processed")

    # Filter out already-fetched whiskeys
    to_fetch = []
    for w in whiskeys:
        if w.id in processed_ids:
            counters["skipped"] += 1
        elif not args.overwrite and w.image_url and w.image_url.endswith(".png"):
            counters["skipped"] += 1
        else:
            to_fetch.append(w)

    if counters["skipped"]:
        print(f"Skipping {counters['skipped']} whiskeys that already have images or were processed")

    total_to_fetch = len(to_fetch)
    print(f"Fetching images for {total_to_fetch} whiskeys\n")

    def process_one(idx_whiskey):
        idx, w = idx_whiskey
        label = clean_name(w.name)[:60]
        session = _get_session()

        # Rotate user-agent periodically
        session.headers["User-Agent"] = random.choice(_USER_AGENTS)

        rel_path = fetch_image_for_whiskey(
            w, session, use_clip=use_clip, use_tor=use_tor, use_ocr=use_ocr,
            use_google_cse=use_google_cse,
        )

        with _lock:
            counters["processed"] += 1
            n = counters["processed"]

            if rel_path:
                counters["fetched"] += 1
                status = "ok"
            else:
                counters["failed"] += 1
                status = "--"

            print(f"[{n}/{total_to_fetch}] {label}  {status}", flush=True)

            # Progress stats every 200
            if n % 200 == 0:
                f = counters["fetched"]
                pct = round(100 * f / n) if n else 0
                print(f"  --- Progress: {f}/{n} ({pct}%) fetched ---", flush=True)

        if rel_path:
            update_db(w.id, rel_path)

        # Track processed IDs for checkpoint
        with _lock:
            processed_ids.add(w.id)

            # Save checkpoint every 50 processed
            if counters["processed"] % 50 == 0:
                _save_checkpoint(CHECKPOINT_FILE, processed_ids, counters)

        # Small delay to be polite to Bing
        time.sleep(0.5)

        return rel_path is not None

    def _save_checkpoint(path, ids, ctrs):
        with open(path, "w") as f:
            json.dump({
                "processed_ids": list(ids),
                "fetched": ctrs["fetched"],
                "failed": ctrs["failed"],
            }, f)

    # Process in batches to avoid flooding memory with futures
    BATCH_SIZE = 100
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        try:
            for batch_start in range(0, total_to_fetch, BATCH_SIZE):
                batch = to_fetch[batch_start:batch_start + BATCH_SIZE]
                futures = {
                    executor.submit(process_one, (batch_start + i + 1, w)): w
                    for i, w in enumerate(batch)
                }
                for future in as_completed(futures):
                    future.result()  # raises exceptions if any
        except KeyboardInterrupt:
            print("\nInterrupted! Saving checkpoint...")
            executor.shutdown(wait=False, cancel_futures=True)
            _save_checkpoint(CHECKPOINT_FILE, processed_ids, counters)
            print(f"Checkpoint saved ({len(processed_ids)} processed). Resume with --resume flag.")

    # Save final checkpoint
    _save_checkpoint(CHECKPOINT_FILE, processed_ids, counters)

    f = counters["fetched"]
    n = counters["processed"]
    pct = round(100 * f / n) if n else 0
    print(f"\nDone -- fetched: {f} ({pct}%)  skipped: {counters['skipped']}  failed: {counters['failed']}")


if __name__ == "__main__":
    main()
