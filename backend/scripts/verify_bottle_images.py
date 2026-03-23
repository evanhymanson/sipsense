"""
Verify all bottle images on disk for correctness after a fetch run.

Checks:
  1. File integrity — corrupt, tiny, or oversized files
  2. Image quality — too small resolution, extreme aspect ratios, mostly blank
  3. Duplicates — same image content (MD5) used for different whiskeys
  4. CLIP — is this a whiskey bottle? (not food, person, landscape, etc.)
  5. OCR  — does the label text match the whiskey name? (brand, age, vintage, edition)
  6. Orphans — image files with no matching DB record
  7. Cross-check — CLIP prompt with specific whiskey name for edition matching

Actions:
  --delete    Delete flagged images from disk and clear DB image_url
  --report    Save JSON report to image_verify_report.json

Usage:
    cd backend
    .venv/bin/python -m scripts.verify_bottle_images              # full audit
    .venv/bin/python -m scripts.verify_bottle_images --delete      # audit + remove bad
    .venv/bin/python -m scripts.verify_bottle_images --no-clip     # OCR only (faster)
    .venv/bin/python -m scripts.verify_bottle_images --no-ocr      # CLIP only
    .venv/bin/python -m scripts.verify_bottle_images --workers 8   # more OCR threads
"""

import os
import re
import sys
import json
import hashlib
import argparse
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
from PIL import Image

from app.database import SessionLocal
from app import models

BOTTLES_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "bottles")

# ── Thresholds ───────────────────────────────────────────────────────────

CLIP_THRESHOLD = 0.22
CLIP_BATCH_SIZE = 64
MIN_FILE_SIZE = 5_000           # 5 KB — anything smaller is likely broken
MAX_FILE_SIZE = 20_000_000      # 20 MB — suspiciously large
MIN_RESOLUTION = 80             # pixels — either dimension
MAX_ASPECT_RATIO = 5.0          # width/height or height/width
MIN_OPAQUE_RATIO = 0.02         # at least 2% non-transparent pixels (RGBA)

POSITIVE_PROMPTS = [
    "a photo of a whiskey bottle",
    "a whiskey bottle product photo",
    "a bottle of bourbon whiskey",
    "a bottle of scotch whisky",
    "a bottle of rye whiskey",
    "a bottle of irish whiskey",
    "a bottle of japanese whisky",
    "a single malt whisky bottle on a plain background",
]

NEGATIVE_PROMPTS = [
    "a photo of a person",
    "a photo of food on a plate",
    "a landscape or nature photo",
    "a logo or icon or graphic design",
    "a glass of whiskey without a bottle",
    "a bar or restaurant interior",
    "a screenshot of a webpage or text",
    "a cocktail in a glass",
    "a beer bottle or wine bottle",
    "wooden barrels or casks in a warehouse",
    "a distillery building exterior",
    "whiskey being poured into a glass",
    "a box or packaging without a bottle visible",
    "a blurry or low quality image",
    "a map or diagram",
    "a group of people drinking",
    "multiple bottles of whiskey together",
]


def unwrap(out):
    if isinstance(out, torch.Tensor):
        return out
    for attr in ("text_embeds", "image_embeds", "pooler_output"):
        if hasattr(out, attr):
            return getattr(out, attr)
    return out[0]


# ── Check helpers ────────────────────────────────────────────────────────

def check_file_integrity(fpath):
    """Check file size and basic integrity. Returns (ok, reason)."""
    size = os.path.getsize(fpath)
    if size < MIN_FILE_SIZE:
        return False, f"file too small ({size} bytes)"
    if size > MAX_FILE_SIZE:
        return False, f"file too large ({size // 1_000_000} MB)"
    try:
        img = Image.open(fpath)
        img.verify()  # checks for corruption without fully loading
        return True, None
    except Exception as e:
        return False, f"corrupt image: {e}"


def check_image_quality(fpath):
    """Check resolution, aspect ratio, and content. Returns (ok, reason, img_or_None)."""
    try:
        img = Image.open(fpath)
        w, h = img.size

        if w < MIN_RESOLUTION or h < MIN_RESOLUTION:
            return False, f"too small ({w}x{h})", None

        aspect = max(w / h, h / w)
        if aspect > MAX_ASPECT_RATIO:
            return False, f"extreme aspect ratio ({aspect:.1f}:1, {w}x{h})", None

        # For RGBA images, check that there's actual content (not mostly transparent)
        if img.mode == "RGBA":
            import numpy as np
            alpha = np.array(img.split()[-1])
            opaque_ratio = (alpha > 10).sum() / alpha.size
            if opaque_ratio < MIN_OPAQUE_RATIO:
                return False, f"mostly transparent ({opaque_ratio:.1%} opaque)", None

        return True, None, img

    except Exception as e:
        return False, f"quality check error: {e}", None


def check_mostly_single_color(img, threshold=0.85):
    """Flag images that are mostly one color (placeholder/error images)."""
    import numpy as np
    arr = np.array(img.convert("RGB"))
    median_color = np.median(arr.reshape(-1, 3), axis=0)
    diffs = np.abs(arr.astype(float) - median_color)
    close_pixels = (diffs.max(axis=-1) < 20).sum()
    ratio = close_pixels / (arr.shape[0] * arr.shape[1])
    if ratio > threshold:
        return True, f"mostly single color ({ratio:.0%} similar pixels)"
    return False, None


def compute_phash(img, hash_size=8):
    """Compute perceptual hash for near-duplicate detection."""
    import numpy as np
    img_gray = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = np.array(img_gray)
    diff = pixels[:, 1:] > pixels[:, :-1]
    return diff.flatten().tobytes()


def check_near_duplicates(items):
    """Find near-duplicate images using perceptual hashing (Hamming distance)."""
    import numpy as np
    hashes = []
    for w, fpath, fname in items:
        try:
            img = Image.open(fpath).convert("RGB")
            h = compute_phash(img)
            hashes.append((w, fname, h))
        except Exception:
            pass

    near_dupes = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            w1, f1, h1 = hashes[i]
            w2, f2, h2 = hashes[j]
            # Hamming distance
            dist = sum(a != b for a, b in zip(h1, h2))
            if dist <= 5:  # very similar (out of 64 bits)
                near_dupes.append({
                    "file1": f1, "name1": w1.name, "id1": w1.id,
                    "file2": f2, "name2": w2.name, "id2": w2.id,
                    "distance": dist,
                })
    return near_dupes


# Sub-brands that MUST match if present in whiskey name
_SUB_BRANDS = {
    # Bruichladdich lines
    "octomore", "black art", "port charlotte", "classic laddie",
    # Jack Daniel's lines
    "gentleman jack", "single barrel",
    # Compass Box blends
    "oak cross", "the general", "peat monster", "spice tree",
    "great king", "hedonism",
    # Jim Beam lines
    "knob creek", "basil hayden", "booker", "baker",
    # Buffalo Trace lines
    "eagle rare", "blanton", "weller", "sazerac", "elmer",
    "george t stagg", "taylor",
    # Ardbeg lines
    "uigeadail", "corryvreckan", "supernova",
    # Glenmorangie lines
    "quinta ruban", "lasanta", "signet",
    # Maker's Mark
    "maker's 46",
    # Redbreast editions
    "cask strength", "lustau",
    # Dalmore editions
    "king alexander", "cigar malt",
    # Macallan editions
    "rare cask", "double cask", "triple cask", "sherry oak",
    # Glenfiddich
    "fire & cane", "experimental",
    # Johnnie Walker
    "blue label", "green label", "gold label", "double black",
}


def check_sub_brand_in_ocr(whiskey_name, ocr_text):
    """Check that sub-brand names from whiskey name appear in OCR text."""
    name_lower = whiskey_name.lower()
    ocr_lower = ocr_text.lower()
    for sub in _SUB_BRANDS:
        if sub in name_lower:
            sub_words = [sw for sw in sub.split() if len(sw) >= 3]
            if sub_words and not any(sw in ocr_lower for sw in sub_words):
                return False, f"sub-brand '{sub}' not found on label"
    return True, None


# ── Main verification ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Verify bottle images: integrity + CLIP + OCR + dedup")
    parser.add_argument("--delete", action="store_true", help="Delete bad images from disk + clear DB")
    parser.add_argument("--report", action="store_true", help="Save JSON report")
    parser.add_argument("--no-clip", action="store_true", help="Skip CLIP visual check")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR label check")
    parser.add_argument("--workers", type=int, default=4, help="OCR thread pool size")
    args = parser.parse_args()

    use_clip = not args.no_clip
    use_ocr = not args.no_ocr

    # ── Discover images on disk ──────────────────────────────────────────
    if not os.path.isdir(BOTTLES_DIR):
        print(f"No bottles directory: {BOTTLES_DIR}")
        return

    files = sorted(f for f in os.listdir(BOTTLES_DIR) if f.endswith(".png"))
    print(f"Found {len(files)} images on disk\n")

    if not files:
        return

    # ── Build whiskey ID → name map from filenames ───────────────────────
    id_to_file = {}
    bad_filenames = []
    for f in files:
        m = re.match(r"^(\d+)-(.+)\.png$", f)
        if m:
            id_to_file[int(m.group(1))] = f
        else:
            bad_filenames.append(f)

    # ── Load DB records for these IDs ────────────────────────────────────
    db = SessionLocal()
    whiskey_ids = list(id_to_file.keys())
    whiskeys = db.query(models.Whiskey).filter(models.Whiskey.id.in_(whiskey_ids)).all()
    id_to_whiskey = {w.id: w for w in whiskeys}

    orphans = [f for wid, f in id_to_file.items() if wid not in id_to_whiskey]
    orphans.extend(bad_filenames)

    items = []
    for wid, fname in id_to_file.items():
        if wid in id_to_whiskey:
            items.append((id_to_whiskey[wid], os.path.join(BOTTLES_DIR, fname), fname))

    print(f"Matched {len(items)} images to DB records")
    if orphans:
        print(f"Orphan files (no DB match or bad filename): {len(orphans)}")

    # ── Check 1: File integrity ──────────────────────────────────────────
    print("\n--- File integrity check ---")
    flagged_integrity = []
    passed_items = []
    for w, fpath, fname in items:
        ok, reason = check_file_integrity(fpath)
        if not ok:
            flagged_integrity.append({
                "id": w.id, "name": w.name, "file": fname,
                "reason": reason, "type": "integrity",
            })
        else:
            passed_items.append((w, fpath, fname))
    print(f"Integrity: {len(passed_items)} passed, {len(flagged_integrity)} flagged")

    # ── Check 2: Image quality ───────────────────────────────────────────
    print("\n--- Image quality check ---")
    flagged_quality = []
    quality_passed = []
    for w, fpath, fname in passed_items:
        ok, reason, img = check_image_quality(fpath)
        if not ok:
            flagged_quality.append({
                "id": w.id, "name": w.name, "file": fname,
                "reason": reason, "type": "quality",
            })
            continue

        # Check for placeholder/single-color images
        is_mono, mono_reason = check_mostly_single_color(img)
        if is_mono:
            flagged_quality.append({
                "id": w.id, "name": w.name, "file": fname,
                "reason": mono_reason, "type": "quality",
            })
            continue

        quality_passed.append((w, fpath, fname))

    passed_items = quality_passed
    print(f"Quality: {len(passed_items)} passed, {len(flagged_quality)} flagged")

    # ── Check 3: Duplicates by MD5 hash ──────────────────────────────────
    print("\n--- Duplicate check ---")
    hash_to_files = defaultdict(list)
    for w, fpath, fname in passed_items:
        h = hashlib.md5(open(fpath, "rb").read()).hexdigest()
        hash_to_files[h].append((w, fname))

    dupes = {h: entries for h, entries in hash_to_files.items() if len(entries) > 1}
    if dupes:
        print(f"DUPLICATES: {len(dupes)} groups")
        for h, entries in dupes.items():
            names = [f"{w.name} ({fname})" for w, fname in entries]
            print(f"  Hash {h[:8]}: {', '.join(names)}")
    else:
        print("No duplicates found")

    # ── Check 3b: Near-duplicates by perceptual hash ─────────────────────
    print("\n--- Near-duplicate check (perceptual hash) ---")
    near_dupes = check_near_duplicates(passed_items)
    if near_dupes:
        print(f"NEAR-DUPLICATES: {len(near_dupes)} pairs (visually similar but different files)")
        for nd in near_dupes:
            print(f"  {nd['name1']} <-> {nd['name2']} (hamming={nd['distance']})")
    else:
        print("No near-duplicates found")

    # ── Check 4: CLIP visual check ───────────────────────────────────────
    flagged_clip = []

    if use_clip:
        print("\n--- CLIP check ---")
        from transformers import CLIPModel, CLIPProcessor

        model_name = "openai/clip-vit-base-patch32"
        print("Loading CLIP model...")
        processor = CLIPProcessor.from_pretrained(model_name)
        clip_model = CLIPModel.from_pretrained(model_name)
        clip_model.eval()

        with torch.no_grad():
            pos_inputs = processor(text=POSITIVE_PROMPTS, return_tensors="pt", padding=True)
            pos_embeds = unwrap(clip_model.get_text_features(**pos_inputs))
            pos_embeds = pos_embeds / pos_embeds.norm(dim=-1, keepdim=True)

            neg_inputs = processor(text=NEGATIVE_PROMPTS, return_tensors="pt", padding=True)
            neg_embeds = unwrap(clip_model.get_text_features(**neg_inputs))
            neg_embeds = neg_embeds / neg_embeds.norm(dim=-1, keepdim=True)

        print("CLIP model loaded.")

        # Load all images
        loaded = []
        for w, fpath, fname in passed_items:
            try:
                img = Image.open(fpath).convert("RGB")
                loaded.append((w, img, fpath, fname))
            except Exception as e:
                flagged_clip.append({"id": w.id, "name": w.name, "file": fname,
                                     "reason": f"open error: {e}", "type": "error"})

        # Batch CLIP
        clip_passed = []
        for batch_start in range(0, len(loaded), CLIP_BATCH_SIZE):
            batch = loaded[batch_start:batch_start + CLIP_BATCH_SIZE]
            imgs = [item[1] for item in batch]

            with torch.no_grad():
                img_inputs = processor(images=imgs, return_tensors="pt", padding=True)
                img_embeds = unwrap(clip_model.get_image_features(**img_inputs))
                if img_embeds.ndim == 3:
                    img_embeds = img_embeds[:, 0, :]
                img_embeds = img_embeds / img_embeds.norm(dim=-1, keepdim=True)

                pos_scores = img_embeds @ pos_embeds.T
                neg_scores = img_embeds @ neg_embeds.T

            for i, (w, img, fpath, fname) in enumerate(batch):
                best_pos = pos_scores[i].max().item()
                best_neg = neg_scores[i].max().item()
                best_neg_idx = neg_scores[i].argmax().item()

                if best_pos < CLIP_THRESHOLD:
                    flagged_clip.append({
                        "id": w.id, "name": w.name, "file": fname,
                        "reason": f"low whiskey score ({best_pos:.3f} < {CLIP_THRESHOLD})",
                        "type": "not_bottle",
                    })
                elif best_neg > best_pos:
                    flagged_clip.append({
                        "id": w.id, "name": w.name, "file": fname,
                        "reason": f"looks like '{NEGATIVE_PROMPTS[best_neg_idx]}' ({best_neg:.3f} > {best_pos:.3f})",
                        "type": "not_bottle",
                    })
                else:
                    clip_passed.append((w, fpath, fname))

        # CLIP name-specific check: verify image matches the specific whiskey, not just "any bottle"
        # This catches edition mismatches (e.g., Jack Daniel's No. 7 vs No. 27)
        flagged_clip_name = []
        if clip_passed:
            print("Running CLIP name-specific check...")
            for batch_start in range(0, len(clip_passed), CLIP_BATCH_SIZE):
                batch_items = clip_passed[batch_start:batch_start + CLIP_BATCH_SIZE]
                # Build specific prompts like "a bottle of Jack Daniel's Old No. 7"
                specific_prompts = [f"a bottle of {w.name}" for w, _, _ in batch_items]
                wrong_prompts = [f"a bottle of whiskey that is NOT {w.name}" for w, _, _ in batch_items]

                imgs = []
                for w, fpath, fname in batch_items:
                    try:
                        imgs.append(Image.open(fpath).convert("RGB"))
                    except Exception:
                        imgs.append(Image.new("RGB", (224, 224)))

                with torch.no_grad():
                    img_inputs = processor(images=imgs, return_tensors="pt", padding=True)
                    img_embeds = unwrap(clip_model.get_image_features(**img_inputs))
                    if img_embeds.ndim == 3:
                        img_embeds = img_embeds[:, 0, :]
                    img_embeds = img_embeds / img_embeds.norm(dim=-1, keepdim=True)

                    spec_inputs = processor(text=specific_prompts, return_tensors="pt", padding=True, truncation=True)
                    spec_embeds = unwrap(clip_model.get_text_features(**spec_inputs))
                    spec_embeds = spec_embeds / spec_embeds.norm(dim=-1, keepdim=True)

                # Per-image similarity with its specific prompt
                for i, (w, fpath, fname) in enumerate(batch_items):
                    sim = (img_embeds[i] @ spec_embeds[i]).item()
                    # Very low similarity to its own name = likely wrong bottle
                    if sim < 0.18:
                        flagged_clip_name.append({
                            "id": w.id, "name": w.name, "file": fname,
                            "reason": f"low name-specific CLIP score ({sim:.3f}) — may be wrong edition",
                            "type": "wrong_edition_clip",
                        })

        passed_items = clip_passed
        print(f"CLIP: {len(passed_items)} passed, {len(flagged_clip)} not-bottle, {len(flagged_clip_name)} wrong-edition")
        flagged_clip.extend(flagged_clip_name)

    # ── Check 5: OCR label matching ──────────────────────────────────────
    flagged_ocr = []

    if use_ocr and passed_items:
        print(f"\n--- OCR check ({args.workers} workers) ---")
        from scripts.fetch_bottle_images import BottleTextValidator

        main_validator = BottleTextValidator()
        print("Loading EasyOCR model...")
        main_validator._load()
        print("EasyOCR loaded.")

        thread_local = threading.local()
        lock = threading.Lock()
        done_count = [0]

        def get_validator():
            if not hasattr(thread_local, "validator"):
                from scripts.fetch_bottle_images import BottleTextValidator
                v = BottleTextValidator()
                v._load()
                thread_local.validator = v
            return thread_local.validator

        def check_one(item):
            w, fpath, fname = item
            v = get_validator()
            try:
                img = Image.open(fpath).convert("RGB")
                has_text, _, detected_texts = v.has_label_text(img)
                if has_text and detected_texts:
                    # Standard OCR name match (brand words, age, vintage)
                    name_ok, name_reason = v.label_matches_name(detected_texts, w.name)
                    if not name_ok:
                        ocr_text = " ".join(detected_texts[:5])
                        with lock:
                            flagged_ocr.append({
                                "id": w.id, "name": w.name, "file": fname,
                                "reason": name_reason,
                                "ocr_text": ocr_text[:120],
                                "type": "wrong_bottle",
                            })
                        return

                    # Sub-brand check — critical product line words must appear
                    ocr_text = " ".join(detected_texts).lower()
                    sub_ok, sub_reason = check_sub_brand_in_ocr(w.name, ocr_text)
                    if not sub_ok:
                        with lock:
                            flagged_ocr.append({
                                "id": w.id, "name": w.name, "file": fname,
                                "reason": sub_reason,
                                "ocr_text": ocr_text[:120],
                                "type": "wrong_edition",
                            })
                        return

                    # Category cross-check: if OCR clearly shows a different spirit type
                    # e.g., whiskey name but label says "vodka", "gin", "rum", "tequila"
                    wrong_spirits = ["vodka", "gin ", "tequila", "mezcal", "cognac",
                                     "brandy", "absinthe", "schnapps"]
                    for spirit in wrong_spirits:
                        if spirit in ocr_text and spirit not in w.name.lower():
                            with lock:
                                flagged_ocr.append({
                                    "id": w.id, "name": w.name, "file": fname,
                                    "reason": f"label says '{spirit}' — wrong spirit type",
                                    "ocr_text": ocr_text[:120],
                                    "type": "wrong_spirit",
                                })
                            return

                # No text detected — flag as suspicious
                elif not has_text or not detected_texts:
                    with lock:
                        flagged_ocr.append({
                            "id": w.id, "name": w.name, "file": fname,
                            "reason": "no text detected on label — may not be a real bottle photo",
                            "type": "no_text",
                        })
            except Exception as e:
                with lock:
                    flagged_ocr.append({
                        "id": w.id, "name": w.name, "file": fname,
                        "reason": f"OCR error: {e}",
                        "type": "ocr_error",
                    })
            with lock:
                done_count[0] += 1
                if done_count[0] % 10 == 0 or done_count[0] == len(passed_items):
                    print(f"  OCR progress: {done_count[0]}/{len(passed_items)}", flush=True)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(check_one, item) for item in passed_items]
            for f in as_completed(futures):
                f.result()

        # Separate real OCR failures from "no text" warnings
        ocr_wrong = [f for f in flagged_ocr if f["type"] == "wrong_bottle"]
        ocr_notext = [f for f in flagged_ocr if f["type"] == "no_text"]
        ocr_errors = [f for f in flagged_ocr if f["type"] == "ocr_error"]
        print(f"OCR: {len(ocr_wrong)} wrong bottles, {len(ocr_notext)} no-text warnings, {len(ocr_errors)} errors")

    # ── Summary ──────────────────────────────────────────────────────────
    all_flagged = flagged_integrity + flagged_quality + flagged_clip + flagged_ocr
    # Only count definite errors for deletion (not "no_text" warnings)
    delete_flagged = [f for f in all_flagged if f["type"] not in ("no_text",)]

    dupe_files = set()
    for h, entries in dupes.items():
        for w, fname in entries[1:]:
            dupe_files.add(fname)

    total_bad = len(delete_flagged) + len(dupe_files) + len(orphans)
    total_good = len(files) - total_bad
    warnings = len([f for f in all_flagged if f["type"] == "no_text"])

    print(f"\n{'='*60}")
    print(f"  VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"  Total images:       {len(files)}")
    print(f"  GOOD:               {total_good}")
    print(f"  Corrupt/broken:     {len(flagged_integrity)}")
    print(f"  Bad quality:        {len(flagged_quality)}")
    print(f"  Not a bottle:       {len([f for f in flagged_clip if f['type'] == 'not_bottle'])}")
    print(f"  Wrong edition:      {len([f for f in flagged_clip if f['type'] == 'wrong_edition_clip'])}")
    print(f"  Wrong bottle (OCR): {len([f for f in flagged_ocr if f['type'] == 'wrong_bottle'])}")
    print(f"  Duplicate copies:   {len(dupe_files)}")
    print(f"  Orphan files:       {len(orphans)}")
    print(f"  TOTAL BAD:          {total_bad}")
    print(f"  Warnings (no text): {warnings}")
    print(f"{'='*60}")

    # Print details for each category
    for label, items_list in [
        ("CORRUPT/BROKEN", flagged_integrity),
        ("BAD QUALITY", flagged_quality),
    ]:
        if items_list:
            print(f"\n  {label}:")
            for f in items_list:
                print(f"    [{f['id']}] {f['name']} — {f['reason']}")

    clip_not_bottle = [f for f in flagged_clip if f["type"] == "not_bottle"]
    clip_wrong_ed = [f for f in flagged_clip if f["type"] == "wrong_edition_clip"]
    if clip_not_bottle:
        print(f"\n  NOT BOTTLES (CLIP):")
        for f in clip_not_bottle:
            print(f"    [{f['id']}] {f['name']} — {f['reason']}")

    if clip_wrong_ed:
        print(f"\n  WRONG EDITION (CLIP name-specific):")
        for f in clip_wrong_ed:
            print(f"    [{f['id']}] {f['name']} — {f['reason']}")

    ocr_wrong = [f for f in flagged_ocr if f["type"] == "wrong_bottle"]
    if ocr_wrong:
        print(f"\n  WRONG BOTTLES (OCR):")
        for f in ocr_wrong:
            print(f"    [{f['id']}] {f['name']}")
            print(f"           {f['reason']}")
            if "ocr_text" in f:
                print(f"           OCR: {f['ocr_text']}")

    ocr_notext = [f for f in flagged_ocr if f["type"] == "no_text"]
    if ocr_notext:
        print(f"\n  WARNINGS — NO TEXT ON LABEL (may be ok for clean product photos):")
        for f in ocr_notext:
            print(f"    [{f['id']}] {f['name']}")

    if dupe_files:
        print(f"\n  DUPLICATE FILES:")
        for fname in sorted(dupe_files):
            print(f"    {fname}")

    if orphans:
        print(f"\n  ORPHAN FILES:")
        for fname in orphans:
            print(f"    {fname}")

    # ── Delete bad images ────────────────────────────────────────────────
    if args.delete:
        to_delete = set()
        for f in delete_flagged:
            to_delete.add(f["file"])
        to_delete.update(dupe_files)
        to_delete.update(orphans)

        if to_delete:
            print(f"\nDeleting {len(to_delete)} bad images...")
            deleted_ids = []
            for fname in to_delete:
                fpath = os.path.join(BOTTLES_DIR, fname)
                if os.path.exists(fpath):
                    os.remove(fpath)
                m_id = re.match(r"^(\d+)-", fname)
                if m_id:
                    deleted_ids.append(int(m_id.group(1)))

            if deleted_ids:
                db.query(models.Whiskey).filter(
                    models.Whiskey.id.in_(deleted_ids)
                ).update({"image_url": None}, synchronize_session="fetch")
                db.commit()
                print(f"Cleared image_url for {len(deleted_ids)} whiskeys in DB")

            remaining = len([f for f in os.listdir(BOTTLES_DIR) if f.endswith(".png")])
            print(f"Done. {remaining} images remain on disk.")
        else:
            print("\nNothing to delete — all images are good!")

    # ── Save report ──────────────────────────────────────────────────────
    if args.report or True:  # always save report
        report = {
            "total_images": len(files),
            "good": total_good,
            "total_bad": total_bad,
            "flagged_integrity": flagged_integrity,
            "flagged_quality": flagged_quality,
            "flagged_clip": flagged_clip,
            "flagged_ocr": flagged_ocr,
            "duplicates": {h: [(w.name, fname) for w, fname in entries]
                           for h, entries in dupes.items()},
            "orphans": orphans,
        }
        report_path = os.path.join(os.path.dirname(__file__), "..", "image_verify_report.json")
        with open(report_path, "w") as fp:
            json.dump(report, fp, indent=2)
        print(f"\nReport saved to: {report_path}")

    db.close()


if __name__ == "__main__":
    main()
