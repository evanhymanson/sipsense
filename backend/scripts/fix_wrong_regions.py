"""
Fix entries where known single-location distilleries have wrong region/category.

The whiskycom source defaulted everything to scotch/Scotland. This script
uses a curated list of distilleries where we're confident about the correct
region and category to fix these misattributions.

We deliberately SKIP parent companies and distributors (Pernod Ricard, Sazerac,
Brown-Forman, etc.) that own distilleries in multiple countries — those need
manual review.

Also deletes confirmed non-whiskey products that slipped through.

Run:  python3 -m scripts.fix_wrong_regions
"""

import sqlite3
import os
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sipsense.db")

# ── Curated distillery fixes ──
# (distillery_name, correct_region, correct_category)
# Only single-location distilleries where we're 100% confident.
DISTILLERY_FIXES = [
    # India
    ("Amrut", "India", "indian"),
    ("Paul John", "India", "indian"),
    ("Paul John Whisky", "India", "indian"),
    ("Rampur", "India", "indian"),
    ("Indri", "India", "indian"),
    ("John Distilleries", "India", "indian"),

    # Taiwan
    ("Kavalan", "Taiwan", "single malt"),

    # Japan
    ("Nikka", "Japan", "japanese"),
    ("Chichibu", "Japan", "japanese"),
    ("Karuizawa", "Japan", "japanese"),
    ("Chugoku Jozo", "Japan", "japanese"),
    ("Ichiro's Malt", "Japan", "japanese"),
    ("Eigashima Shuzo", "Japan", "japanese"),
    ("Akkeshi Distillery", "Japan", "japanese"),

    # Ireland (Northern Ireland counts as Irish whiskey)
    ("Bushmills", "Ireland", "irish"),
    ("Teeling", "Ireland", "irish"),
    ("Glendalough", "Ireland", "irish"),
    ("Dingle", "Ireland", "irish"),
    ("Connemara", "Ireland", "irish"),
    ("Knappogue Castle", "Ireland", "irish"),
    ("Midleton", "Ireland", "irish"),
    ("Cooley", "Ireland", "irish"),

    # Germany
    ("Glen Els", "Germany", "world"),
    ("Blaue Maus", "Germany", "world"),
    ("Alt Enderle", "Germany", "world"),
    ("Drexler", "Germany", "world"),
    ("Hercynian Distilling Co.", "Germany", "world"),
    ("Eifel Destillate", "Germany", "world"),
    ("Finch Whiskydestillerie", "Germany", "world"),
    ("SLYRS", "Germany", "world"),
    ("Brennerei Liebl", "Germany", "world"),
    ("Hausbrauerei Altstadthof", "Germany", "world"),
    ("Brennerei Höhler", "Germany", "world"),
    ("Brennerei Ziegler", "Germany", "world"),
    ("Habbel's Destillerie & Brennerei", "Germany", "world"),
    ("Birkenhof-Brennerei GmbH", "Germany", "world"),
    ("Dresdner Whisky Manufaktur", "Germany", "world"),
    ("Geiger Destillerie & Imkerei", "Germany", "world"),
    ("fesslermill 1396", "Germany", "world"),

    # USA — actual distilleries
    ("Balcones", "USA", "bourbon"),
    ("Balcones Distilling", "USA", "bourbon"),
    ("Jack Daniel's", "USA", "bourbon"),
    ("Old Forester", "USA", "bourbon"),
    ("Cats Eye Distillery", "USA", "world"),
    ("Hillrock Estate Distillery", "USA", "single malt"),
    ("WhistlePig", "USA", "rye"),
    ("Angel's Envy", "USA", "bourbon"),
    ("Basil Hayden's", "USA", "bourbon"),
    ("Bernheim", "USA", "bourbon"),
    ("Bib & Tucker", "USA", "bourbon"),
    ("Buffalo Trace", "USA", "bourbon"),
    ("Bulleit", "USA", "bourbon"),
    ("Burnside", "USA", "bourbon"),
    ("Eagle Rare", "USA", "bourbon"),
    ("Ezra Brooks", "USA", "bourbon"),
    ("Garrison Brothers", "USA", "bourbon"),
    ("Heaven's Door", "USA", "bourbon"),
    ("Jim Beam", "USA", "bourbon"),
    ("Lost Lantern", "USA", "single malt"),
    ("Michter's", "USA", "bourbon"),
    ("Milam & Greene", "USA", "bourbon"),
    ("Orphan Barrel Whisky Co.", "USA", "bourbon"),
    ("Rebel", "USA", "bourbon"),
    ("Rossville Union", "USA", "rye"),
    ("Stagg Jr", "USA", "bourbon"),
    ("Templeton", "USA", "rye"),
    ("Thomas H. Handy", "USA", "rye"),
    ("Widow Jane", "USA", "bourbon"),
    ("Willett", "USA", "bourbon"),

    # Canada
    ("Crown Royal", "Canada", "canadian"),

    # England
    ("Cotswolds", "England", "world"),
    ("Cotswolds Distillery", "England", "world"),
    ("Bimber", "England", "world"),

    # Wales
    ("Penderyn", "Wales", "world"),

    # Australia
    ("Hellyers Road", "Australia", "world"),
    ("Hellyers Road Distillery", "Australia", "world"),

    # Norway
    ("Brennevinsgrova", "Norway", "world"),

    # Switzerland
    ("Brauerei Locher", "Switzerland", "world"),
    ("Säntis Malt", "Switzerland", "world"),

    # Denmark
    ("Stauning", "Denmark", "world"),
    ("Fary Lochan", "Denmark", "world"),
    ("Braunstein", "Denmark", "world"),

    # Sweden
    ("Mackmyra", "Sweden", "world"),
    ("High Coast Distillery", "Sweden", "world"),
    ("Agitator Whiskymakare", "Sweden", "world"),
    ("Smögen", "Sweden", "world"),
    ("Gammelstilla Whisky", "Sweden", "world"),
    ("Gotland Whisky", "Sweden", "world"),

    # Finland
    ("Kyrö", "Finland", "world"),

    # Czech Republic
    ("Destilerka Svach", "Czech Republic", "world"),

    # Hungary
    ("Gemenc", "Hungary", "world"),

    # Israel
    ("Milk & Honey", "Israel", "world"),

    # South Africa
    ("James Sedgwick", "South Africa", "world"),

    # New Zealand
    ("Thomson Whisky", "New Zealand", "world"),

    # Iceland
    ("Eimverk Distillery", "Iceland", "world"),

    # Belgium
    ("Braeckman Distillery", "Belgium", "world"),
    ("Brugse Whisky Company", "Belgium", "world"),
    ("Graanstokerij Filliers", "Belgium", "world"),

    # Netherlands
    ("Cley Distillery", "Netherlands", "world"),

    # France
    ("Domaine des Hautes Glaces", "France", "world"),
    ("Distillerie Grallet-Dupic", "France", "world"),
    ("Celtic Whisky Distillerie", "France", "world"),
    ("Distillerie Castan", "France", "world"),
    ("Distillerie des Menhirs", "France", "world"),
    ("Distilérka Svach", "France", "world"),
    ("Glann ar Mor", "France", "world"),
    ("Distillerie Mavela", "France", "world"),
]

# Non-whiskey products to delete
NON_WHISKEY_IDS = [
    9471,    # Lazy Dodo (rum from Mauritius)
    11516,   # Captain Cane Rumspirituose (rum spirit)
]


def backup_db():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH + f".backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")


def fix_distillery_regions(cur):
    """Fix region and category for known single-location distilleries."""
    total = 0
    for distillery, correct_region, correct_category in DISTILLERY_FIXES:
        cur.execute("""
            UPDATE whiskeys
            SET region = ?, category = ?
            WHERE distillery = ? AND region = 'Scotland' AND category = 'scotch'
        """, (correct_region, correct_category, distillery))
        count = cur.rowcount
        if count > 0:
            total += count

        # Also fix single malt entries from Scotland
        cur.execute("""
            UPDATE whiskeys
            SET region = ?
            WHERE distillery = ? AND region = 'Scotland' AND category = 'single malt'
        """, (correct_region, distillery))
        count2 = cur.rowcount
        if count2 > 0:
            total += count2

    print(f"  Fixed distillery region/category mismatches: {total} rows")


def delete_non_whiskey(cur):
    """Delete confirmed non-whiskey products."""
    if NON_WHISKEY_IDS:
        placeholders = ",".join("?" * len(NON_WHISKEY_IDS))
        cur.execute(f"DELETE FROM whiskeys WHERE id IN ({placeholders})", NON_WHISKEY_IDS)
        print(f"  Deleted non-whiskey products: {cur.rowcount} rows")


def fix_remaining_single_malt_regions(cur):
    """
    For single malts still missing region, try to get it from the most common
    region for that distillery across all entries.
    """
    cur.execute("""
        UPDATE whiskeys
        SET region = (
            SELECT w2.region
            FROM whiskeys w2
            WHERE w2.distillery = whiskeys.distillery
              AND w2.region IS NOT NULL AND w2.region <> ''
            GROUP BY w2.region
            ORDER BY COUNT(*) DESC
            LIMIT 1
        )
        WHERE category = 'single malt'
          AND (region IS NULL OR region = '')
          AND distillery <> 'Unknown'
    """)
    print(f"  Filled remaining single malt regions from sibling entries: {cur.rowcount} rows")


def report(cur):
    """Print final stats."""
    print("\n--- Final stats ---")
    cur.execute("SELECT COUNT(*) FROM whiskeys")
    print(f"  Total whiskeys: {cur.fetchone()[0]}")

    cur.execute("SELECT category, COUNT(*) FROM whiskeys GROUP BY category ORDER BY COUNT(*) DESC")
    print("\n  Categories:")
    for row in cur.fetchall():
        print(f"    {row[0]}: {row[1]}")

    cur.execute("SELECT region, COUNT(*) FROM whiskeys GROUP BY region ORDER BY COUNT(*) DESC LIMIT 20")
    print("\n  Top regions:")
    for row in cur.fetchall():
        print(f"    {row[0] or '(empty)'}: {row[1]}")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE distillery = 'Unknown'")
    print(f"\n  Remaining Unknown distillery: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE category = 'single malt' AND (region IS NULL OR region = '')")
    print(f"  Remaining single malts without region: {cur.fetchone()[0]}")


def main():
    print(f"SipSense Database — Fix Wrong Regions")
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

    fix_distillery_regions(cur)
    delete_non_whiskey(cur)
    fix_remaining_single_malt_regions(cur)

    conn.commit()
    print(f"\nAll fixes committed.")

    report(cur)
    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
