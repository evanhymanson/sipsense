"""
Batch-generate flavor profiles for whiskeys that have a description but no flavor tags.

Also runs on whiskeys with neither — using name/category/region alone.

Run from the backend/ directory:
    python -m scripts.generate_flavor_profiles

Options:
    --limit N       Only process N whiskeys (default: all)
    --delay SECS    Seconds between API calls (default: 0.3)
    --dry-run       Print targets without calling API
    --batch N       Send N whiskeys per API call to reduce cost/time (default: 5)
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

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

VALID_FLAVORS = {
    "vanilla", "caramel", "honey", "sweet", "oak", "woody", "smoky", "peaty",
    "medicinal", "fruity", "citrus", "orange", "lemon", "apple", "pear",
    "cherry", "plum", "raisin", "tropical", "banana", "mango", "spicy",
    "pepper", "cinnamon", "nutmeg", "clove", "herbal", "mint", "anise",
    "floral", "rose", "lavender", "chocolate", "coffee", "malty", "grainy",
    "nutty", "almond", "walnut", "leather", "tobacco", "earthy", "brine",
    "sea salt", "coastal", "buttery", "cream", "toffee", "butterscotch",
}


def build_batch_prompt(whiskeys: list) -> str:
    lines = []
    for i, w in enumerate(whiskeys, 1):
        desc_line = f'  Description: "{w.description[:200]}"' if w.description else ""
        age_line = f"  Age: {w.age}yr" if w.age else ""
        lines.append(
            f"{i}. {w.name} | {w.category} | {w.distillery or 'Unknown'} | "
            f"{w.region or ''}{age_line}\n{desc_line}"
        )

    return (
        "For each whiskey below, return 4-8 flavor tags as a comma-separated list.\n"
        "Use only common, specific flavor words (e.g. vanilla, caramel, smoky, peaty, "
        "citrus, oak, honey, spicy, fruity, floral, malty, chocolate, leather).\n"
        "Do not use vague words like 'complex' or 'smooth'.\n\n"
        + "\n\n".join(lines)
        + "\n\nRespond with exactly this format — one line per whiskey, number then colon then tags:\n"
        + "\n".join(f"{i}. <tags>" for i in range(1, len(whiskeys) + 1))
    )


def parse_batch_response(raw: str, count: int) -> list[str | None]:
    results = [None] * count
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if ". " in line[:4]:
            try:
                idx_str, _, tags = line.partition(". ")
                idx = int(idx_str.strip()) - 1
                if 0 <= idx < count:
                    results[idx] = tags.strip()
            except (ValueError, IndexError):
                pass
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=5)
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        log.error("ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    import anthropic
    from app.database import SessionLocal
    from app import models
    from sqlalchemy import or_

    db = SessionLocal()
    client = anthropic.Anthropic(api_key=api_key) if not args.dry_run else None

    try:
        query = db.query(models.Whiskey).filter(
            or_(
                models.Whiskey.flavor_profile.is_(None),
                models.Whiskey.flavor_profile == "",
            )
        ).order_by(models.Whiskey.id)

        total = query.count()
        limit = args.limit if args.limit > 0 else total
        whiskeys = query.limit(limit).all()

        log.info("Whiskeys missing flavor profiles: %d | will process: %d", total, len(whiskeys))

        if args.dry_run:
            for w in whiskeys[:20]:
                log.info("  [dry-run] id=%d  %s", w.id, w.name)
            if len(whiskeys) > 20:
                log.info("  ... and %d more", len(whiskeys) - 20)
            return

        done = 0
        errors = 0
        batch_size = args.batch

        for i in range(0, len(whiskeys), batch_size):
            batch = whiskeys[i:i + batch_size]
            try:
                prompt = build_batch_prompt(batch)
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = message.content[0].text.strip()
                flavor_list = parse_batch_response(raw, len(batch))

                for w, flavors in zip(batch, flavor_list):
                    if flavors:
                        w.flavor_profile = flavors
                        done += 1
                    else:
                        errors += 1

                db.commit()

                if (i // batch_size + 1) % 20 == 0 or i + batch_size >= len(whiskeys):
                    log.info("  Progress: %d / %d (errors: %d)", done, len(whiskeys), errors)

            except Exception as exc:
                errors += len(batch)
                log.warning("  Batch error at i=%d: %s", i, exc)
                db.rollback()

            time.sleep(args.delay)

        log.info("Done. Flavors written: %d | Errors: %d", done, errors)

    finally:
        db.close()


if __name__ == "__main__":
    main()
