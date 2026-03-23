"""
Audit all existing bottle images using CLIP + OCR to find:
  1. Non-whiskey-bottle images (CLIP check)
  2. Wrong bottles — images that ARE whiskey but have the WRONG label (OCR check)

Usage:
    cd backend
    .venv/bin/python -m scripts.audit_bottle_images                 # audit only
    .venv/bin/python -m scripts.audit_bottle_images --fix           # clear bad image_urls
    .venv/bin/python -m scripts.audit_bottle_images --fix --refetch # clear + re-fetch correct images
    .venv/bin/python -m scripts.audit_bottle_images --no-clip       # skip CLIP, only do OCR name check
    .venv/bin/python -m scripts.audit_bottle_images --no-ocr        # skip OCR, only do CLIP check
    .venv/bin/python -m scripts.audit_bottle_images --workers 8     # OCR thread pool size
"""

import os
import sys
import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor
from tqdm import tqdm

from app.database import SessionLocal
from app import models

CLIP_THRESHOLD = 0.22
CLIP_BATCH_SIZE = 64  # process images in batches for speed

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
    "a map or diagram",
    "a group of people drinking",
    "a cocktail in a glass",
    "a beer bottle or wine bottle",
    "a blurry or low quality image",
    "wooden barrels or casks in a warehouse",
    "a distillery building exterior",
    "whiskey being poured into a glass",
    "a box or packaging without a bottle visible",
]


def unwrap(out):
    if isinstance(out, torch.Tensor):
        return out
    for attr in ("text_embeds", "image_embeds", "pooler_output"):
        if hasattr(out, attr):
            return getattr(out, attr)
    return out[0]


def run_clip_audit(whiskeys_with_imgs, processor, clip_model, pos_embeds, neg_embeds):
    """
    Run CLIP audit in batches for speed. Returns (passed_list, flagged_list, error_list).
    passed_list contains (whiskey, img) tuples that passed CLIP for further OCR checking.
    """
    flagged = []
    errors = []
    passed = []  # (whiskey, PIL.Image) tuples

    # Pre-load all images first
    print("Loading images from disk...")
    loaded = []  # (whiskey, img_or_none, error_or_none)
    for w, path in tqdm(whiskeys_with_imgs, desc="Loading", unit="img"):
        if not os.path.exists(path):
            errors.append({"id": w.id, "name": w.name, "path": path, "reason": "file missing"})
            continue
        try:
            img = Image.open(path).convert("RGB")
            loaded.append((w, img, path))
        except Exception as e:
            errors.append({"id": w.id, "name": w.name, "path": path, "reason": f"open error: {e}"})

    # Process in batches
    print(f"\nRunning CLIP on {len(loaded)} images in batches of {CLIP_BATCH_SIZE}...")
    for batch_start in tqdm(range(0, len(loaded), CLIP_BATCH_SIZE), desc="CLIP batches", unit="batch"):
        batch = loaded[batch_start:batch_start + CLIP_BATCH_SIZE]
        imgs = [item[1] for item in batch]

        with torch.no_grad():
            img_inputs = processor(images=imgs, return_tensors="pt", padding=True)
            img_embeds = unwrap(clip_model.get_image_features(**img_inputs))
            if img_embeds.ndim == 3:
                img_embeds = img_embeds[:, 0, :]
            img_embeds = img_embeds / img_embeds.norm(dim=-1, keepdim=True)

            pos_scores = img_embeds @ pos_embeds.T  # (batch, num_pos)
            neg_scores = img_embeds @ neg_embeds.T  # (batch, num_neg)

        for i, (w, img, path) in enumerate(batch):
            best_pos = pos_scores[i].max().item()
            best_neg = neg_scores[i].max().item()
            best_neg_idx = neg_scores[i].argmax().item()

            if best_pos < CLIP_THRESHOLD:
                flagged.append({
                    "id": w.id, "name": w.name, "path": path,
                    "reason": f"low whiskey score ({best_pos:.3f} < {CLIP_THRESHOLD})",
                    "type": "not_bottle",
                })
            elif best_neg > best_pos:
                flagged.append({
                    "id": w.id, "name": w.name, "path": path,
                    "reason": f"matched '{NEGATIVE_PROMPTS[best_neg_idx]}' ({best_neg:.3f}) > whiskey ({best_pos:.3f})",
                    "type": "not_bottle",
                })
            else:
                passed.append((w, img, path))

    return passed, flagged, errors


def run_ocr_audit(passed_clip, text_validator, num_workers):
    """
    Run OCR label-name matching on images that passed CLIP, using a thread pool.
    EasyOCR internally uses numpy/CPU so threads help with I/O and parallelism.
    """
    flagged = []
    lock = threading.Lock()
    # Create per-thread OCR readers to avoid contention
    thread_local = threading.local()

    def get_reader():
        if not hasattr(thread_local, "validator"):
            from scripts.fetch_bottle_images import BottleTextValidator
            v = BottleTextValidator()
            v._load()  # eagerly load the model
            thread_local.validator = v
        return thread_local.validator

    # Pre-load the main validator so model downloads happen once
    text_validator._load()

    pbar = tqdm(total=len(passed_clip), desc="OCR check", unit="img")

    def check_one(item):
        w, img, path = item
        v = get_reader()
        try:
            has_text, ocr_reason, detected_texts = v.has_label_text(img)
            if has_text and detected_texts:
                name_ok, name_reason = v.label_matches_name(detected_texts, w.name)
                if not name_ok:
                    ocr_text = " ".join(detected_texts[:5])
                    with lock:
                        flagged.append({
                            "id": w.id, "name": w.name, "path": path,
                            "reason": name_reason,
                            "ocr_text": ocr_text[:100],
                            "type": "wrong_bottle",
                        })
        except Exception as e:
            with lock:
                flagged.append({
                    "id": w.id, "name": w.name, "path": path,
                    "reason": f"OCR error: {e}",
                    "type": "ocr_error",
                })
        finally:
            pbar.update(1)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(check_one, item) for item in passed_clip]
        try:
            for f in as_completed(futures):
                f.result()
        except KeyboardInterrupt:
            print("\nInterrupted OCR audit!")
            executor.shutdown(wait=False, cancel_futures=True)

    pbar.close()
    return flagged


def main():
    parser = argparse.ArgumentParser(description="Audit bottle images with CLIP + OCR")
    parser.add_argument("--fix", action="store_true", help="Clear image_url for bad images")
    parser.add_argument("--refetch", action="store_true", help="Re-fetch correct images after clearing bad ones")
    parser.add_argument("--no-clip", action="store_true", help="Skip CLIP visual check")
    parser.add_argument("--no-ocr", action="store_true", help="Skip OCR label name check")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of images to audit")
    parser.add_argument("--workers", type=int, default=6, help="OCR thread pool size (default: 6)")
    parser.add_argument("--refetch-workers", type=int, default=4, help="Re-fetch thread pool size (default: 4)")
    args = parser.parse_args()

    use_clip = not args.no_clip
    use_ocr = not args.no_ocr

    # --- Load models ---
    clip_model = None
    processor = None
    pos_embeds = None
    neg_embeds = None

    if use_clip:
        print("Loading CLIP model...")
        model_name = "openai/clip-vit-base-patch32"
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

        print("CLIP model loaded.\n")

    text_validator = None
    if use_ocr:
        from scripts.fetch_bottle_images import BottleTextValidator
        text_validator = BottleTextValidator()
        print("Loading EasyOCR model...")
        text_validator._load()
        print("EasyOCR model loaded.\n")

    # --- Query DB ---
    db = SessionLocal()
    whiskeys = (
        db.query(models.Whiskey)
        .filter(models.Whiskey.image_url.isnot(None), models.Whiskey.image_url != "")
        .all()
    )
    if args.limit:
        whiskeys = whiskeys[:args.limit]

    whiskeys_with_imgs = [(w, w.image_url.lstrip("/")) for w in whiskeys]
    print(f"Auditing {len(whiskeys_with_imgs)} images (clip={use_clip}, ocr={use_ocr}, workers={args.workers})...\n")

    # --- Phase 1: CLIP audit (batched, fast) ---
    flagged_clip = []
    errors = []
    passed_clip = []

    if use_clip:
        passed_clip, flagged_clip, errors = run_clip_audit(
            whiskeys_with_imgs, processor, clip_model, pos_embeds, neg_embeds
        )
        print(f"\nCLIP done: {len(passed_clip)} passed, {len(flagged_clip)} flagged, {len(errors)} errors")
    else:
        # If no CLIP, load all images for OCR
        for w, path in whiskeys_with_imgs:
            if not os.path.exists(path):
                errors.append({"id": w.id, "name": w.name, "path": path, "reason": "file missing"})
                continue
            try:
                img = Image.open(path).convert("RGB")
                passed_clip.append((w, img, path))
            except Exception as e:
                errors.append({"id": w.id, "name": w.name, "path": path, "reason": f"open error: {e}"})

    # --- Phase 2: OCR audit (multithreaded) ---
    flagged_ocr = []
    if use_ocr and text_validator and passed_clip:
        print(f"\nRunning OCR name check on {len(passed_clip)} images with {args.workers} workers...")
        flagged_ocr = run_ocr_audit(passed_clip, text_validator, args.workers)
        print(f"OCR done: {len(flagged_ocr)} wrong bottles found")

    # --- Report ---
    all_flagged = flagged_clip + flagged_ocr
    total_flagged = len(all_flagged)

    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE")
    print(f"{'='*60}")
    print(f"Total scanned:        {len(whiskeys)}")
    print(f"Passed:               {len(whiskeys) - total_flagged - len(errors)}")
    print(f"FLAGGED (not bottle): {len(flagged_clip)}")
    print(f"FLAGGED (wrong bottle): {len(flagged_ocr)}")
    print(f"Errors:               {len(errors)}")

    if flagged_clip:
        print(f"\n{'='*60}")
        print("NOT WHISKEY BOTTLES (CLIP):")
        print(f"{'='*60}")
        for f in flagged_clip[:30]:
            print(f"  [{f['id']}] {f['name']}")
            print(f"         {f['reason']}")

    if flagged_ocr:
        print(f"\n{'='*60}")
        print("WRONG BOTTLES (OCR label mismatch):")
        print(f"{'='*60}")
        for f in flagged_ocr[:50]:
            print(f"  [{f['id']}] {f['name']}")
            print(f"         {f['reason']}")
            if "ocr_text" in f:
                print(f"         OCR saw: {f['ocr_text']}")

    if errors:
        print(f"\n{'='*60}")
        print(f"ERRORS: {len(errors)}")
        print(f"{'='*60}")
        for e in errors[:20]:
            print(f"  [{e['id']}] {e['name']} — {e['reason']}")

    # Save report
    report = {"flagged_clip": flagged_clip, "flagged_ocr": flagged_ocr, "errors": errors}
    report_path = os.path.join(os.path.dirname(__file__), "..", "image_audit_report.json")
    with open(report_path, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"\nFull report saved to: {report_path}")

    # --- Fix if requested ---
    if args.fix and all_flagged:
        flagged_ids = [f["id"] for f in all_flagged]
        print(f"\nClearing image_url for {len(flagged_ids)} flagged whiskeys...")
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(flagged_ids)).update(
            {"image_url": None}, synchronize_session="fetch"
        )
        db.commit()
        print("Done — bad image_url values cleared.")

    if args.fix and errors:
        error_ids = [e["id"] for e in errors]
        db.query(models.Whiskey).filter(models.Whiskey.id.in_(error_ids)).update(
            {"image_url": None}, synchronize_session="fetch"
        )
        db.commit()
        print(f"Cleared image_url for {len(errors)} error entries too.")

    # --- Re-fetch if requested ---
    if args.refetch and args.fix and all_flagged:
        print(f"\n{'='*60}")
        print(f"RE-FETCHING {len(all_flagged)} images with stricter validation...")
        print(f"{'='*60}\n")

        import time
        import random
        from scripts.fetch_bottle_images import (
            fetch_image_for_whiskey, update_db, make_session,
        )

        _thread_local = threading.local()
        _lock = threading.Lock()
        counters = {"fetched": 0, "failed": 0}

        def _get_session():
            if not hasattr(_thread_local, "session"):
                _thread_local.session = make_session()
            return _thread_local.session

        flagged_ids = [f["id"] for f in all_flagged]
        to_refetch = db.query(models.Whiskey).filter(models.Whiskey.id.in_(flagged_ids)).all()

        def process_one(w):
            session = _get_session()
            rel_path = fetch_image_for_whiskey(w, session, use_clip=True, use_ocr=True)
            with _lock:
                if rel_path:
                    counters["fetched"] += 1
                    status = "ok"
                else:
                    counters["failed"] += 1
                    status = "--"
                n = counters["fetched"] + counters["failed"]
                print(f"  [{n}/{len(to_refetch)}] {w.name[:50]}  {status}", flush=True)
            if rel_path:
                update_db(w.id, rel_path)
            time.sleep(0.5)

        with ThreadPoolExecutor(max_workers=args.refetch_workers) as executor:
            futures = [executor.submit(process_one, w) for w in to_refetch]
            try:
                for f in as_completed(futures):
                    f.result()
            except KeyboardInterrupt:
                print("\nInterrupted!")
                executor.shutdown(wait=False, cancel_futures=True)

        print(f"\nRe-fetch done: {counters['fetched']} fixed, {counters['failed']} still missing")

    db.close()


if __name__ == "__main__":
    main()
