"""
Process pairing images: remove backgrounds with rembg, save as transparent PNG.

Food items will float directly on the card background in the UI.
Reads JPGs from S3 pairings/, processes them, uploads PNGs back to S3.

Usage:
    cd backend
    python -m scripts.process_pairing_images
"""

import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from rembg import remove
from tqdm import tqdm

from app.storage import upload_bytes, download_bytes, list_files


def process_image(filename: str):
    """Download JPG from S3, remove background, upload PNG to S3."""
    img_bytes = download_bytes(f"pairings/{filename}")
    img = Image.open(BytesIO(img_bytes)).convert("RGBA")
    segmented = remove(img)

    # Upload as transparent PNG (same name, .png extension)
    png_name = os.path.splitext(filename)[0] + ".png"
    buf = BytesIO()
    segmented.save(buf, "PNG")
    upload_bytes(buf.getvalue(), f"pairings/{png_name}", content_type="image/png")


def main():
    all_files = list_files("pairings")
    jpg_files = sorted(f for f in all_files if f.lower().endswith(".jpg"))
    print(f"Segmenting {len(jpg_files)} pairing images to transparent PNG...")
    print(f"Source: S3 pairings/\n")

    for filename in tqdm(jpg_files, desc="Segmenting"):
        try:
            process_image(filename)
        except Exception as e:
            print(f"  FAILED: {filename} — {e}")

    print("\nDone! All images saved as transparent PNGs in S3.")


if __name__ == "__main__":
    main()
