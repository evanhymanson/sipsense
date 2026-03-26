"""
Remove backgrounds from bottle images using BiRefNet (via HuggingFace transformers).

Runs the BiRefNet segmentation model locally on MPS (Apple Silicon) or CPU
to produce high-quality transparent PNGs.  Falls back to rembg if BiRefNet
fails to load.

Usage:
    cd backend
    .venv/bin/python -m scripts.remove_backgrounds                      # process all
    .venv/bin/python -m scripts.remove_backgrounds --limit 50           # first 50
    .venv/bin/python -m scripts.remove_backgrounds --skip-existing      # skip done
    .venv/bin/python -m scripts.remove_backgrounds --provider rembg     # use rembg instead
    .venv/bin/python -m scripts.remove_backgrounds --device cpu         # force CPU

Model details:
    - BiRefNet (ZhengPeng7/BiRefNet) — 220M params, MIT license
    - Runs at 1024x1024 resolution, ~6-7s per image on MPS
    - Produces clean masks even on glass bottles and reflective surfaces
    - Model downloads automatically on first run (~900MB)

PyTorch learning notes:
    - transforms.Compose: chains preprocessing steps (resize, normalize)
    - model.eval(): disables dropout/batchnorm training behavior
    - torch.no_grad(): disables gradient tracking for inference (saves memory)
    - .sigmoid(): converts raw logits to 0-1 probability mask
    - MPS backend: Apple Silicon GPU acceleration via Metal Performance Shaders
"""

import os
import sys
import time
import argparse
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from app.storage import upload_bytes, download_bytes, list_files


# ── BiRefNet provider (HuggingFace transformers + PyTorch) ────────────────

class BiRefNetProvider:
    """Background removal using BiRefNet via HuggingFace transformers.

    This loads the full BiRefNet model and runs inference locally using
    PyTorch.  On Apple Silicon, it uses MPS acceleration.  The model
    processes images at 1024x1024 and produces a per-pixel probability
    mask that we apply as an alpha channel.
    """

    def __init__(self, device: str = "auto"):
        import torch
        from torchvision import transforms
        from transformers import AutoModelForImageSegmentation

        # Device selection
        if device == "auto":
            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"
        else:
            self.device = device

        print(f"Loading BiRefNet model (device={self.device})...")
        self.model = AutoModelForImageSegmentation.from_pretrained(
            "ZhengPeng7/BiRefNet", trust_remote_code=True
        ).float().eval().to(self.device)

        # Standard ImageNet normalization — BiRefNet expects this
        self.transform = transforms.Compose([
            transforms.Resize((1024, 1024)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self._to_pil = transforms.ToPILImage()

        param_count = sum(p.numel() for p in self.model.parameters()) / 1e6
        print(f"BiRefNet loaded — {param_count:.0f}M parameters\n")

    def remove_background(self, img: Image.Image) -> Image.Image | None:
        """Run BiRefNet segmentation and return image with transparent background."""
        import torch

        rgb = img.convert("RGB")
        original_size = rgb.size  # (W, H)

        # Preprocess: resize to 1024x1024, normalize
        input_tensor = self.transform(rgb).unsqueeze(0).to(self.device)

        # Forward pass — model returns list of predictions at different scales,
        # we take the last (finest) one and apply sigmoid to get probabilities
        with torch.no_grad():
            preds = self.model(input_tensor)[-1].sigmoid().cpu()

        # Convert prediction to PIL mask at original resolution
        pred = preds[0].squeeze()
        mask = self._to_pil(pred).resize(original_size, Image.BILINEAR)

        # Apply mask as alpha channel
        result = rgb.convert("RGBA")
        result.putalpha(mask)

        return result


# ── rembg provider (fallback) ────────────────────────────────────────────

class RembgProvider:
    """Background removal using rembg library (BiRefNet-general model)."""

    def __init__(self, model_name: str = "birefnet-general"):
        from rembg import new_session
        print(f"Loading rembg model ({model_name})...")
        self.session = new_session(model_name)
        self.model_name = model_name
        print("rembg loaded\n")

    def remove_background(self, img: Image.Image) -> Image.Image | None:
        from rembg import remove

        # Add green padding — gives the model a clear background signal
        rgb = img.convert("RGB")
        w, h = rgb.size
        pad = 100
        padded = Image.new("RGB", (w + pad * 2, h + pad * 2), (0, 200, 0))
        padded.paste(rgb, (pad, pad))
        padded = padded.convert("RGBA")

        result = remove(padded, session=self.session)
        return result


# ── Shared utilities ─────────────────────────────────────────────────────

def trim_transparent(img: Image.Image, margin: int = 8) -> Image.Image:
    """Crop to the non-transparent bounding box with a margin."""
    if img.mode != "RGBA":
        return img
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - margin)
    y0 = max(0, y0 - margin)
    x1 = min(img.width, x1 + margin)
    y1 = min(img.height, y1 + margin)
    return img.crop((x0, y0, x1, y1))


def process_image(provider, filename: str) -> bool:
    """Download from S3 bottles/, remove background, upload to S3 bottles_nobg/."""
    try:
        img_bytes = download_bytes(f"bottles/{filename}")
        img = Image.open(BytesIO(img_bytes))
        img.load()

        result = provider.remove_background(img)
        if result is None:
            return False

        # Trim excess transparent area
        result = trim_transparent(result, margin=8)

        # Reject if the result is too small (mask probably failed)
        if result.width < 80 or result.height < 80:
            return False

        out_name = os.path.splitext(filename)[0] + ".png"
        buf = BytesIO()
        result.save(buf, "PNG", optimize=True)
        upload_bytes(buf.getvalue(), f"bottles_nobg/{out_name}", content_type="image/png")
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Remove backgrounds from bottle images using BiRefNet"
    )
    parser.add_argument("--limit", type=int, default=0, help="Max images to process (0=all)")
    parser.add_argument("--skip-existing", action="store_true", help="Skip already-processed images")
    parser.add_argument(
        "--provider", type=str, default="birefnet",
        choices=["birefnet", "rembg"],
        help="Segmentation model: birefnet (default, best quality) or rembg (fallback)"
    )
    parser.add_argument(
        "--device", type=str, default="auto",
        choices=["auto", "mps", "cuda", "cpu"],
        help="PyTorch device (default: auto-detect)"
    )
    parser.add_argument(
        "--skip-db", action="store_true",
        help="Skip updating DB image_url paths after processing"
    )
    args = parser.parse_args()

    # Initialize the segmentation provider
    if args.provider == "birefnet":
        try:
            provider = BiRefNetProvider(device=args.device)
        except Exception as e:
            print(f"BiRefNet failed to load ({e}), falling back to rembg...")
            provider = RembgProvider()
    else:
        provider = RembgProvider()

    # Find all source images from S3 (or local)
    source_files = sorted([
        f for f in list_files("bottles")
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])

    if args.skip_existing:
        existing = list_files("bottles_nobg")
        source_files = [f for f in source_files if f not in existing]

    if args.limit:
        source_files = source_files[:args.limit]

    total = len(source_files)
    print(f"Processing {total} bottle images")
    print(f"  Provider: {args.provider}")
    print(f"  Input:    S3 bottles/")
    print(f"  Output:   S3 bottles_nobg/\n")

    success = 0
    failed = 0
    start_time = time.time()

    for i, filename in enumerate(source_files, 1):
        t0 = time.time()
        ok = process_image(provider, filename)
        elapsed = time.time() - t0

        if ok:
            success += 1
            status = f"ok ({elapsed:.1f}s)"
        else:
            failed += 1
            status = "FAIL"

        print(f"[{i}/{total}] {filename}  {status}", flush=True)

    total_time = time.time() - start_time
    pct = round(100 * success / total) if total else 0
    avg = total_time / total if total else 0
    print(f"\nDone — {success}/{total} ({pct}%) processed, {failed} failed")
    print(f"Total time: {total_time:.0f}s ({avg:.1f}s avg per image)")

    # Update DB to point to processed images
    if success > 0 and not args.skip_db:
        print("\nUpdating DB image_url paths to use bottles_nobg...")
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        updated = 0
        nobg_files = list_files("bottles_nobg")
        for filename in source_files:
            out_name = os.path.splitext(filename)[0] + ".png"
            if out_name in nobg_files:
                try:
                    wid = int(filename.split("-", 1)[0])
                except (ValueError, IndexError):
                    continue
                old_url = f"/uploads/bottles/{filename}"
                new_url = f"/uploads/bottles_nobg/{out_name}"
                rows = db.query(models.Whiskey).filter(
                    models.Whiskey.id == wid,
                    models.Whiskey.image_url == old_url,
                ).update({"image_url": new_url})
                updated += rows
        db.commit()
        db.close()
        print(f"Updated {updated} DB records to use bottles_nobg/")


if __name__ == "__main__":
    main()
