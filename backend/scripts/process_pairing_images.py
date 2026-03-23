"""
Process pairing images: remove backgrounds with rembg, save as transparent PNG.

Food items will float directly on the card background in the UI.

Usage:
    cd backend
    python -m scripts.process_pairing_images
"""

from pathlib import Path

from PIL import Image
from rembg import remove
from tqdm import tqdm

PAIRINGS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "pairings"


def process_image(jpg_path: Path, size: int = 300):
    """Remove background from JPG, save as transparent PNG."""
    img = Image.open(jpg_path).convert("RGBA")
    segmented = remove(img)

    # Save as transparent PNG (same name, .png extension)
    png_path = jpg_path.with_suffix(".png")
    segmented.save(png_path, "PNG")

    # Delete the original JPG
    jpg_path.unlink()


def main():
    images = sorted(PAIRINGS_DIR.glob("*.jpg"))
    print(f"Segmenting {len(images)} pairing images to transparent PNG...")
    print(f"Directory: {PAIRINGS_DIR}\n")

    for img_path in tqdm(images, desc="Segmenting"):
        try:
            process_image(img_path)
        except Exception as e:
            print(f"  FAILED: {img_path.name} — {e}")

    print("\nDone! All images saved as transparent PNGs.")


if __name__ == "__main__":
    main()
