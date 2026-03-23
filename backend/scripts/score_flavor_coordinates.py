"""
Backfill flavor_x and flavor_y for all whiskeys that don't have scores yet.

Uses Claude (Haiku) to score each whiskey on two axes:
  - flavor_x: 0 (sweet) → 100 (smoky)
  - flavor_y: 0 (light) → 100 (bold)

Claude uses the whiskey's name, category, region, ABV, age, and flavor tags
to determine where it falls. This is reliable because Claude has broad
knowledge of whiskey profiles from its training data.

Usage:
    cd backend
    python -m scripts.score_flavor_coordinates          # score all unscored
    python -m scripts.score_flavor_coordinates --all    # re-score everything
    python -m scripts.score_flavor_coordinates --batch 20   # batch size
"""

import os
import sys
import time
import argparse
import logging

# Add parent dir so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are a whiskey expert. Score this whiskey on two axes (integers 0-100).

SWEET_SMOKY: 0 = very sweet/fruity/dessert-like, 50 = balanced, 100 = very smoky/peaty/medicinal
LIGHT_BOLD: 0 = very light/delicate/thin, 50 = medium body, 100 = very bold/rich/full/heavy

Consider the whiskey's category, region, distillery reputation, ABV, age, and any known flavors.
Be precise — don't default to 50 unless the whiskey is truly balanced on that axis.

Name: {name}
Distillery: {distillery}
Category: {category}
Region: {region}
Age: {age}
ABV: {abv}%
Known flavors: {flavors}

Reply with ONLY two lines:
SWEET_SMOKY: <integer>
LIGHT_BOLD: <integer>"""


def parse_scores(text: str):
    """Extract SWEET_SMOKY and LIGHT_BOLD from Claude's response."""
    scores = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        for key in ("SWEET_SMOKY:", "LIGHT_BOLD:"):
            if line.startswith(key):
                try:
                    val = int(line[len(key):].strip())
                    scores[key[:-1]] = max(0, min(100, val))
                except ValueError:
                    pass
    return scores.get("SWEET_SMOKY"), scores.get("LIGHT_BOLD")


def score_batch(whiskeys, client, model):
    """Score a batch of whiskeys using a single multi-turn or sequential calls."""
    results = []
    for w in whiskeys:
        prompt = PROMPT_TEMPLATE.format(
            name=w.name,
            distillery=w.distillery,
            category=w.category,
            region=w.region or "Unknown",
            age=f"{w.age} years" if w.age else "No age statement",
            abv=w.abv,
            flavors=w.flavor_profile or "none listed",
        )
        try:
            message = client.messages.create(
                model=model,
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()
            fx, fy = parse_scores(text)
            results.append((w, fx, fy, text))
        except Exception as e:
            log.error("Failed for %s (id=%d): %s", w.name, w.id, e)
            results.append((w, None, None, str(e)))
            time.sleep(1)  # back off on errors
    return results


def main():
    parser = argparse.ArgumentParser(description="Score whiskeys on flavor axes using Claude")
    parser.add_argument("--all", action="store_true", help="Re-score all whiskeys, not just unscored")
    parser.add_argument("--batch", type=int, default=10, help="How many to score per run")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between API calls")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    model = os.getenv("CLAUDE_MODEL_SMALL", "claude-haiku-4-5-20251001")

    db = SessionLocal()
    try:
        query = db.query(models.Whiskey)
        if not args.all:
            query = query.filter(
                (models.Whiskey.flavor_x.is_(None)) | (models.Whiskey.flavor_y.is_(None))
            )
        whiskeys = query.limit(args.batch).all()

        if not whiskeys:
            log.info("No whiskeys need scoring!")
            return

        total_unscored = db.query(models.Whiskey).filter(
            (models.Whiskey.flavor_x.is_(None)) | (models.Whiskey.flavor_y.is_(None))
        ).count()
        log.info("Scoring %d whiskeys (batch size: %d, %d total unscored)",
                 len(whiskeys), args.batch, total_unscored)

        scored = 0
        failed = 0
        for w in whiskeys:
            prompt = PROMPT_TEMPLATE.format(
                name=w.name,
                distillery=w.distillery,
                category=w.category,
                region=w.region or "Unknown",
                age=f"{w.age} years" if w.age else "No age statement",
                abv=w.abv,
                flavors=w.flavor_profile or "none listed",
            )
            try:
                message = client.messages.create(
                    model=model,
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = message.content[0].text.strip()
                fx, fy = parse_scores(text)
                if fx is not None and fy is not None:
                    w.flavor_x = fx
                    w.flavor_y = fy
                    db.commit()
                    scored += 1
                    log.info("  [%d/%d] %s → x=%d y=%d", scored, len(whiskeys), w.name, fx, fy)
                else:
                    failed += 1
                    log.warning("  Could not parse scores for %s: %s", w.name, text)
            except Exception as e:
                failed += 1
                log.error("  API error for %s: %s", w.name, e)
                time.sleep(1)

            time.sleep(args.delay)

        log.info("Done! Scored %d, failed %d. Remaining unscored: %d",
                 scored, failed, total_unscored - scored)

    finally:
        db.close()


if __name__ == "__main__":
    main()
