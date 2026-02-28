"""
Batch-generate Claude descriptions for whiskeys that don't have one.

Run from the backend/ directory:
    python -m scripts.generate_descriptions

Options:
    --limit N       Only process N whiskeys (default: all)
    --delay SECS    Seconds between API calls (default: 0.5)
    --dry-run       Print whiskeys that would be processed, don't call API
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Load .env from backend/ directory so ANTHROPIC_API_KEY is available
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def build_prompt(w) -> str:
    flavor_line = f"Known flavors: {w.flavor_profile}\n" if w.flavor_profile else ""
    age_line = f"Age: {w.age} years\n" if w.age else "No age statement\n"
    region_line = f"Region: {w.region}\n" if w.region else ""
    return (
        "You are a friendly whiskey expert writing for beginners.\n\n"
        "Write 2-3 warm, plain-English sentences about this whiskey. "
        "Describe what it tastes like and what makes it interesting. "
        "Base your description on the name and data provided — don't invent specific facts.\n\n"
        f"Name: {w.name}\n"
        f"Distillery: {w.distillery}\n"
        f"Category: {w.category}\n"
        f"{region_line}"
        f"{age_line}"
        f"ABV: {w.abv}%\n"
        f"{flavor_line}"
        "\nAlso return a comma-separated list of 3-6 flavor tags that best describe this whiskey "
        "(e.g. vanilla, oak, caramel, smoky, fruity, spicy).\n"
        "Format your response exactly as:\n"
        "DESCRIPTION: <2-3 sentences>\n"
        "FLAVORS: <comma-separated tags>"
    )


def parse_response(raw: str) -> tuple[str, str | None]:
    """Return (description, flavors_or_None)."""
    if "DESCRIPTION:" in raw and "FLAVORS:" in raw:
        parts = raw.split("FLAVORS:")
        desc = parts[0].replace("DESCRIPTION:", "").strip()
        flavors = parts[1].strip()
        return desc, flavors
    return raw.strip(), None


def main():
    parser = argparse.ArgumentParser(description="Batch-generate whiskey descriptions via Claude")
    parser.add_argument("--limit", type=int, default=0, help="Max whiskeys to process (0 = all)")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Print targets without calling API")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        log.error("ANTHROPIC_API_KEY is not set. Export it before running.")
        sys.exit(1)

    # Import after env check so missing deps give a clean error
    import anthropic
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import or_

    db = SessionLocal()
    client = anthropic.Anthropic(api_key=api_key) if not args.dry_run else None

    try:
        # Select whiskeys with no description, or only a truncated one
        query = db.query(models.Whiskey).filter(
            or_(
                models.Whiskey.description.is_(None),
                models.Whiskey.description == "",
                models.Whiskey.description.ilike("%..."),
                models.Whiskey.description.ilike("%…"),
                models.Whiskey.description.ilike("%read more"),
            )
        ).order_by(models.Whiskey.id)

        total_missing = query.count()
        limit = args.limit if args.limit > 0 else total_missing
        whiskeys = query.limit(limit).all()

        log.info("Whiskeys missing descriptions: %d | will process: %d", total_missing, len(whiskeys))

        if args.dry_run:
            for w in whiskeys:
                log.info("  [dry-run] id=%d  %s", w.id, w.name)
            return

        done = 0
        errors = 0

        for w in whiskeys:
            try:
                prompt = build_prompt(w)
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                desc, flavors = parse_response(raw)

                w.description = desc
                if flavors and not w.flavor_profile:
                    w.flavor_profile = flavors
                db.commit()

                done += 1
                if done % 50 == 0 or done == len(whiskeys):
                    log.info("  Progress: %d / %d (errors: %d)", done, len(whiskeys), errors)

            except Exception as exc:
                errors += 1
                log.warning("  Error for id=%d '%s': %s", w.id, w.name, exc)
                db.rollback()

            time.sleep(args.delay)

        log.info("Done. Generated: %d | Errors: %d", done, errors)

    finally:
        db.close()


if __name__ == "__main__":
    main()
