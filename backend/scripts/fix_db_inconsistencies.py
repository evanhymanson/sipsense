"""
Database consistency fix script for SipSense whiskey DB.

Fixes found during thorough audit of 62,602 records:

1. Region: "United States" → "USA" (3,879 entries)
2. Jack Daniel's products miscategorized as scotch/Scotland → bourbon/USA (16 entries)
3. American brands (Jim Beam, Wild Turkey, etc.) miscategorized as scotch/Scotland (~30 entries)
4. Scottish whiskeys miscategorized as "bourbon" because name mentions bourbon cask (55 entries)
5. RTD/non-whiskey products (cola mixes, "Zero Sugar Cola") → DELETE (~10 entries)
6. Garbage entries ("Mat kenn", "blended wisky") → DELETE
7. Non-Scottish brands incorrectly assigned region "Scotland" (German, English, etc.)

Run:  python -m scripts.fix_db_inconsistencies
"""

import sqlite3
import os
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sipsense.db")


def backup_db():
    """Create a timestamped backup before making changes."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH + f".backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Backup created: {backup_path}")
    return backup_path


def fix_region_united_states(cur):
    """Consolidate 'United States' → 'USA'."""
    cur.execute("UPDATE whiskeys SET region = 'USA' WHERE region = 'United States'")
    print(f"  Region 'United States' → 'USA': {cur.rowcount} rows")


def fix_jack_daniels(cur):
    """Jack Daniel's products are Tennessee whiskey, not scotch from Scotland."""
    cur.execute("""
        UPDATE whiskeys
        SET category = 'bourbon', region = 'USA', distillery = 'Jack Daniel''s'
        WHERE name LIKE '%Jack Daniel%' AND category = 'scotch'
    """)
    print(f"  Jack Daniel's scotch → bourbon/USA: {cur.rowcount} rows")


def fix_american_brands_as_scotch(cur):
    """
    Well-known American brands incorrectly categorized as scotch from Scotland.
    Only fix entries where the distillery/brand IS the American brand,
    not scotch that mentions 'American Oak' in the name.
    """
    american_bourbon_brands = [
        ("Jim Beam", "bourbon", "Jim Beam"),
        ("Wild Turkey", "bourbon", "Wild Turkey"),
        ("Buffalo Trace", "bourbon", "Buffalo Trace"),
        ("Maker's Mark", "bourbon", "Maker's Mark"),
        ("Maker''s Mark", "bourbon", "Maker's Mark"),
        ("Woodford Reserve", "bourbon", "Woodford Reserve"),
        ("Knob Creek", "bourbon", "Knob Creek"),
        ("Four Roses", "bourbon", "Four Roses"),
        ("Bulleit", "bourbon", "Bulleit"),
        ("Evan Williams", "bourbon", "Evan Williams"),
        ("Elijah Craig", "bourbon", "Elijah Craig"),
        ("Heaven Hill", "bourbon", "Heaven Hill"),
        ("Copper Fox", "rye", "Copper Fox"),
    ]

    total = 0
    for brand_pattern, new_category, new_distillery in american_bourbon_brands:
        # Match by name starting with or containing the brand, but only if currently scotch/Scotland
        cur.execute(f"""
            UPDATE whiskeys
            SET category = ?, region = 'USA', distillery = ?
            WHERE name LIKE ? AND category = 'scotch' AND region = 'Scotland'
        """, (new_category, new_distillery, f"%{brand_pattern}%"))
        total += cur.rowcount

    # Blackened American Whiskey
    cur.execute("""
        UPDATE whiskeys
        SET category = 'bourbon', region = 'USA'
        WHERE name LIKE '%Blackened American Whiskey%' AND category = 'scotch'
    """)
    total += cur.rowcount

    # Hirsch American Whiskey
    cur.execute("""
        UPDATE whiskeys
        SET category = 'bourbon', region = 'USA'
        WHERE name LIKE '%Hirsch%American%' AND category = 'scotch'
    """)
    total += cur.rowcount

    # Westland (Washington State single malt)
    cur.execute("""
        UPDATE whiskeys
        SET category = 'single malt', region = 'USA', distillery = 'Westland'
        WHERE name LIKE '%Westland%' AND category = 'scotch' AND region = 'Scotland'
    """)
    total += cur.rowcount

    # Exile Single Malt American Whiskey
    cur.execute("""
        UPDATE whiskeys
        SET category = 'single malt', region = 'USA'
        WHERE name LIKE '%Exile Single Malt American%' AND category = 'scotch'
    """)
    total += cur.rowcount

    print(f"  American brands scotch → bourbon/USA: {total} rows")


def fix_scottish_bourbon_cask(cur):
    """
    Scottish whiskeys miscategorized as 'bourbon' because their name or
    category string from whiskybase contained 'bourbon' (e.g., bourbon cask finish).
    These are single malts from Scotland, not bourbon.
    """
    cur.execute("""
        UPDATE whiskeys
        SET category = 'single malt'
        WHERE category = 'bourbon' AND region = 'Scotland'
    """)
    print(f"  Scottish 'bourbon' → 'single malt': {cur.rowcount} rows")


def delete_rtd_and_garbage(cur):
    """
    Remove RTD (ready-to-drink) cocktail products and garbage entries
    that are not actual whiskey bottles.
    """
    ids_to_delete = [
        4158,   # Kentucky Straight Bourbon Whiskey & Cola
        4199,   # Jack Daniel's Lynchburg Lemonade (RTD cocktail)
        4287,   # J&B COLA BLIK (canned mixed drink)
        4304,   # Whisky & Cola
        4372,   # Mat kenn (garbage)
        4405,   # blended wisky (garbage misspelling)
        4422,   # Japenese blended whisky (garbage misspelling)
        4492,   # Tennessee Whiskey & No Sugar Cola
        4497,   # Zero Sugar Cola (not whiskey at all)
        4498,   # Wild Turkey & Zero Sugar Cola
        4500,   # Jack Daniel's Coca-Cola (RTD)
        4524,   # Kentucky Straight Bourbon Whiskey & Cola Zero
        4070,   # Виски ирландский купажированный Джемесон (Russian duplicate of Jameson)
    ]

    placeholders = ",".join("?" * len(ids_to_delete))
    cur.execute(f"DELETE FROM whiskeys WHERE id IN ({placeholders})", ids_to_delete)
    print(f"  Deleted RTD/garbage entries: {cur.rowcount} rows")


def fix_non_scottish_as_scotland(cur):
    """
    Fix entries where non-Scottish distilleries got region='Scotland' from
    whiskybase's default. We can identify these by known distillery/brand names.
    """
    fixes = [
        # German distilleries
        ("Ayrer%", "Germany"),
        ("Nine Springs%", "Germany"),
        ("Fass No.%", "Germany"),
        # English distilleries
        ("Adnams%", "England"),
        # Australian distilleries
        ("Sullivans Cove%", "Australia"),
    ]

    total = 0
    for pattern, region in fixes:
        cur.execute("""
            UPDATE whiskeys SET region = ?
            WHERE name LIKE ? AND region = 'Scotland' AND category = 'scotch'
        """, (region, pattern))
        if cur.rowcount > 0:
            # Also fix category for non-Scottish
            cur.execute("""
                UPDATE whiskeys SET category = 'world'
                WHERE name LIKE ? AND region = ? AND category = 'scotch'
            """, (pattern, region))
        total += cur.rowcount

    print(f"  Non-Scottish brands region fix: {total} rows")


def fix_openfoodfacts_french_regions(cur):
    """
    OpenFoodFacts entries often have region='France' because the product was
    sold in France, not because it was made there. Fix scotch sold in France.
    """
    # "Whisky Ecosse" literally means "Scotch Whisky" in French
    cur.execute("""
        UPDATE whiskeys
        SET region = 'Scotland', category = 'blended'
        WHERE name LIKE '%Whisky Ecosse%blended%' AND region = 'France'
    """)
    ecosse_blended = cur.rowcount

    cur.execute("""
        UPDATE whiskeys
        SET region = 'Scotland'
        WHERE name LIKE '%Whisky Ecosse%' AND region = 'France'
    """)
    ecosse_other = cur.rowcount

    # JOHNNIE WALKER miscategorized from Australia
    cur.execute("""
        UPDATE whiskeys
        SET region = 'Scotland', name = 'Johnnie Walker Red Label'
        WHERE id = 4213
    """)

    print(f"  French region → Scotland (Ecosse): {ecosse_blended + ecosse_other} rows")
    print(f"  Fixed JOHNNIE WALKER entry")


def fix_generic_openfoodfacts_names(cur):
    """
    Fix or delete generic/meaningless names from OpenFoodFacts.
    """
    generic_ids = [
        4256,   # "Bourbon whiskey 40° vol" - too generic
        4076,   # "Whisky Ecosse Blended 40% vol" - too generic
    ]

    placeholders = ",".join("?" * len(generic_ids))
    cur.execute(f"DELETE FROM whiskeys WHERE id IN ({placeholders})", generic_ids)
    print(f"  Deleted generic OpenFoodFacts entries: {cur.rowcount} rows")


def fix_short_cryptic_names(cur):
    """
    Fix entries with very short names that are just age statements like '12Y', '22Y'.
    These are incomplete entries.
    """
    cur.execute("""
        DELETE FROM whiskeys
        WHERE LENGTH(name) <= 3 AND name NOT IN ('SIA')
    """)
    print(f"  Deleted ultra-short name entries: {cur.rowcount} rows")


def report_remaining_issues(cur):
    """Print counts of remaining potential issues for manual review."""
    print("\n--- Remaining items for manual review ---")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE distillery = 'Unknown'")
    print(f"  Distillery = 'Unknown': {cur.fetchone()[0]} entries")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE category = 'single malt' AND (region IS NULL OR region = '')")
    print(f"  Single malt with no region: {cur.fetchone()[0]} entries")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE name LIKE '%New Make%'")
    print(f"  'New Make' spirit entries: {cur.fetchone()[0]} entries")

    cur.execute("SELECT COUNT(*) FROM whiskeys WHERE source = 'openfoodfacts'")
    print(f"  OpenFoodFacts entries remaining: {cur.fetchone()[0]} entries")

    cur.execute("SELECT COUNT(*) FROM whiskeys")
    print(f"\n  Total whiskeys after cleanup: {cur.fetchone()[0]}")


def main():
    print(f"SipSense Database Consistency Fix")
    print(f"Database: {DB_PATH}")
    print(f"{'=' * 60}")

    if not os.path.exists(DB_PATH):
        print("ERROR: Database not found!")
        return

    backup_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get initial count
    cur.execute("SELECT COUNT(*) FROM whiskeys")
    initial_count = cur.fetchone()[0]
    print(f"\nInitial record count: {initial_count}")
    print(f"\nApplying fixes...")

    # Apply all fixes
    fix_region_united_states(cur)
    fix_jack_daniels(cur)
    fix_american_brands_as_scotch(cur)
    fix_scottish_bourbon_cask(cur)
    delete_rtd_and_garbage(cur)
    fix_non_scottish_as_scotland(cur)
    fix_openfoodfacts_french_regions(cur)
    fix_generic_openfoodfacts_names(cur)
    fix_short_cryptic_names(cur)

    conn.commit()
    print(f"\nAll fixes committed.")

    report_remaining_issues(cur)

    conn.close()
    print(f"\nDone!")


if __name__ == "__main__":
    main()
