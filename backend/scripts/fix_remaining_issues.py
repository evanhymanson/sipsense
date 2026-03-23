"""
Fix remaining database consistency issues:

1. Delete 'New Make' spirit entries (unaged distillate, not legally whiskey)
2. Fill missing regions for single malts using distillery→region mapping
3. Infer distillery from whiskey names for 'Unknown' entries using known distillery names

Run:  python3 -m scripts.fix_remaining_issues
"""

import sqlite3
import os
import re
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sipsense.db")

# ── Distillery → Region mapping for known world distilleries ──
# Used to fill missing regions on single malt entries.
# Only includes distilleries whose region can be confidently determined.
DISTILLERY_REGION = {
    # Taiwan
    "Kavalan": "Taiwan",
    "Omar": "Taiwan",
    "Yushan": "Taiwan",
    "Nantou Distillery": "Taiwan",
    # India
    "Amrut": "India",
    "Paul John": "India",
    "Paul John Whisky": "India",
    "Rampur": "India",
    "Indri": "India",
    "Kamet": "India",
    "Single Malts of India": "India",
    "John Distilleries": "India",
    # Australia
    "Overeem": "Australia",
    "Limeburners": "Australia",
    "Hellyers Road": "Australia",
    "Nant": "Australia",
    "Nant Distilling Company": "Australia",
    "Sullivans Cove": "Australia",
    "Lark": "Australia",
    "Starward": "Australia",
    "Heartwood": "Australia",
    "Bakery Hill": "Australia",
    "Great Outback": "Australia",
    "New World Projects": "Australia",
    "New World Whisky": "Australia",
    "Smith's Angaston": "Australia",
    "Three Capes": "Australia",
    "Cradle Mountain": "Australia",
    "Black Gate Distillery": "Australia",
    "Adams Distillery": "Australia",
    # Wales
    "Penderyn": "Wales",
    "Aber Falls": "Wales",
    "Aber Falls Whisky Distillery": "Wales",
    # England
    "Cotswolds": "England",
    "Cotswolds Distillery": "England",
    "The English": "England",
    "English Whisky Co.": "England",
    "Adnams": "England",
    "Bimber": "England",
    # Iceland
    "Flóki": "Iceland",
    "Eimverk Distillery": "Iceland",
    # Switzerland
    "Säntis Malt": "Switzerland",
    "Brauerei Locher": "Switzerland",
    "Johnett": "Switzerland",
    # France
    "G. Rozelieures": "France",
    "Armorik": "France",
    "Kornog": "France",
    "Brenne": "France",
    "P&M": "France",
    "Distilérka Svach": "France",
    # Israel
    "Milk & Honey": "Israel",
    # Sweden
    "Mackmyra": "Sweden",
    "Smögen": "Sweden",
    "Agitator": "Sweden",
    "Agitator Whiskymakare": "Sweden",
    "High Coast Distillery": "Sweden",
    # USA
    "Westland": "USA",
    "Old Potrero": "USA",
    "StillTheOne Distillery": "USA",
    "Hillrock Estate": "USA",
    "Four Walls": "USA",
    # New Zealand
    "New Zealand Whisky Collection": "New Zealand",
    "Thomson Whisky": "New Zealand",
    "Milford": "New Zealand",
    # Netherlands
    "Millstone": "Netherlands",
    "Filliers": "Netherlands",
    # Belgium
    "Het Anker": "Belgium",
    "The Owl Distillery": "Belgium",
    "Radermacher": "Belgium",
    # Denmark
    "Braunstein": "Denmark",
    "Stauning": "Denmark",
    "Fary Lochan": "Denmark",
    # Finland
    "Teerenpeli": "Finland",
    # Ireland
    "West Cork": "Ireland",
    # Czech Republic
    "Goldcock": "Czech Republic",
    "Hammerhead": "Czech Republic",
    # Japan
    "Pōkeno": "New Zealand",
    # Germany
    "SLYRS": "Germany",
    # Scotland (for those missing region)
    "Scorpions": "Scotland",
    "Ballantine's": "Scotland",
    "GlenTaite": "Scotland",
    "Muirhead's": "Scotland",
    "Glen Breton": "Canada",
    "Glenora": "Canada",
    "Glenora Distillery": "Canada",
    "Audny": "Norway",
    "Vicomte": "France",
    "Trader Joe's": "Scotland",
    "Two Brewers": "Canada",
    "Yukon Brewing Company": "Canada",
    "Crown Royal": "Canada",
    "pür spirits": "Germany",
}


def backup_db():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH + f".backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")


def delete_new_make(cur):
    """
    Delete 'New Make' spirit entries. New make is unaged distillate —
    legally not whiskey in most jurisdictions.
    """
    cur.execute("""
        DELETE FROM whiskeys
        WHERE name LIKE '%New Make%' OR name LIKE '%new make%'
    """)
    print(f"  Deleted New Make entries: {cur.rowcount} rows")


def fill_missing_regions(cur):
    """Fill missing regions for single malts using the distillery→region mapping."""
    total = 0
    for distillery, region in DISTILLERY_REGION.items():
        cur.execute("""
            UPDATE whiskeys
            SET region = ?
            WHERE distillery = ? AND (region IS NULL OR region = '')
        """, (region, distillery))
        total += cur.rowcount

    print(f"  Filled missing regions from distillery mapping: {total} rows")

    # Report remaining
    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE category = 'single malt' AND (region IS NULL OR region = '')")
    remaining = cur.fetchone()[0]
    print(f"  Single malts still missing region: {remaining}")


def infer_distillery_from_name(cur):
    """
    For entries with distillery='Unknown', try to match the whiskey name
    against known distillery names from the database.

    Strategy: get all known distillery names (that have >=3 entries),
    then for each Unknown entry, check if its name starts with a known
    distillery name. Match longest name first to avoid partial matches
    (e.g., "Glen Moray" before "Glen").
    """
    # Build list of known distillery names from the database
    cur.execute("""
        SELECT distillery, COUNT(*) as cnt
        FROM whiskeys
        WHERE distillery <> 'Unknown'
        GROUP BY distillery
        HAVING cnt >= 3
        ORDER BY LENGTH(distillery) DESC
    """)
    known_distilleries = [row[0] for row in cur.fetchall()]
    print(f"  Known distillery names to match against: {len(known_distilleries)}")

    # Also build a distillery→region mapping from existing data (most common region per distillery)
    cur.execute("""
        SELECT distillery, region, COUNT(*) as cnt
        FROM whiskeys
        WHERE distillery <> 'Unknown' AND region IS NOT NULL AND region <> ''
        GROUP BY distillery, region
        ORDER BY distillery, cnt DESC
    """)
    distillery_region_map = {}
    for row in cur.fetchall():
        dist, region, cnt = row
        if dist not in distillery_region_map:
            distillery_region_map[dist] = region

    # Get all Unknown distillery entries
    cur.execute("SELECT id, name, region FROM whiskeys WHERE distillery = 'Unknown'")
    unknowns = cur.fetchall()
    print(f"  Entries with Unknown distillery: {len(unknowns)}")

    updated = 0
    region_filled = 0
    for wid, name, current_region in unknowns:
        name_lower = name.lower()
        matched_distillery = None

        for dist in known_distilleries:
            dist_lower = dist.lower()
            # Check if name starts with the distillery name
            if name_lower.startswith(dist_lower):
                # Make sure it's a word boundary (next char is space, digit, or end)
                next_pos = len(dist_lower)
                if next_pos >= len(name_lower) or name_lower[next_pos] in (' ', "'", '\u2019', '-', ','):
                    matched_distillery = dist
                    break

        if matched_distillery:
            # Also fill region if missing
            new_region = current_region
            if not current_region and matched_distillery in distillery_region_map:
                new_region = distillery_region_map[matched_distillery]
                region_filled += 1

            if new_region and new_region != current_region:
                cur.execute(
                    "UPDATE whiskeys SET distillery = ?, region = ? WHERE id = ?",
                    (matched_distillery, new_region, wid)
                )
            else:
                cur.execute(
                    "UPDATE whiskeys SET distillery = ? WHERE id = ?",
                    (matched_distillery, wid)
                )
            updated += 1

    print(f"  Distillery inferred from name: {updated} rows")
    print(f"  Regions also filled during distillery inference: {region_filled} rows")

    # Report remaining
    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE distillery = 'Unknown'")
    remaining = cur.fetchone()[0]
    print(f"  Entries still with Unknown distillery: {remaining}")


def add_new_make_to_normalizer():
    """Add 'new make' to the normalizer rejection list to prevent future imports."""
    normalizer_path = os.path.join(os.path.dirname(__file__), "..", "scraper", "normalizer.py")
    with open(normalizer_path, "r") as f:
        content = f.read()

    if "new.?make" in content or "new_make" in content:
        print("  Normalizer already rejects 'new make' — skipping")
        return

    # Add new make to the rejection regex
    old = r'|protein|supplement|powder'
    new = r'|new\s*make|protein|supplement|powder'

    if old in content:
        content = content.replace(old, new)
        with open(normalizer_path, "w") as f:
            f.write(content)
        print("  Added 'new make' to normalizer rejection list")
    else:
        print("  WARNING: Could not find normalizer rejection list to update")


def main():
    print(f"SipSense Database — Fix Remaining Issues")
    print(f"Database: {DB_PATH}")
    print(f"{'=' * 60}")

    if not os.path.exists(DB_PATH):
        print("ERROR: Database not found!")
        return

    backup_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM whiskeys")
    print(f"\nInitial record count: {cur.fetchone()[0]}")
    print(f"\nApplying fixes...")

    # 1. Delete New Make spirits
    delete_new_make(cur)

    # 2. Fill missing regions
    fill_missing_regions(cur)

    # 3. Infer distillery from name
    infer_distillery_from_name(cur)

    conn.commit()
    print(f"\nAll fixes committed.")

    # 4. Update normalizer to reject new make in future
    add_new_make_to_normalizer()

    # Final stats
    cur.execute("SELECT COUNT(*) FROM whiskeys")
    print(f"\n  Total whiskeys after cleanup: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE distillery = 'Unknown'")
    print(f"  Remaining Unknown distillery: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE category = 'single malt' AND (region IS NULL OR region = '')")
    print(f"  Remaining single malts without region: {cur.fetchone()[0]}")

    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
