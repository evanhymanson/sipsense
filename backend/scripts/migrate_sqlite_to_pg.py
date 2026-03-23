"""Migrate whiskey data from local SQLite DB to production PostgreSQL."""
import os
import sqlite3
import sys

# Ensure app module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be run from backend/ directory or provide path to sipsense.db
SQLITE_PATH = os.environ.get("SQLITE_PATH", "sipsense.db")
PG_URL = os.environ.get("DATABASE_URL")

if not PG_URL:
    print("ERROR: DATABASE_URL not set. Run this inside the Docker container.")
    sys.exit(1)

if not os.path.exists(SQLITE_PATH):
    print(f"ERROR: SQLite file not found at {SQLITE_PATH}")
    sys.exit(1)

import sqlalchemy as sa

# Connect to both databases
sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
pg_engine = sa.create_engine(PG_URL)

# Tables to migrate (order matters for foreign keys)
TABLES = [
    "whiskeys",
    "badges",
]


def get_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return [row["name"] for row in cursor.fetchall()]


def migrate_table(table):
    cursor = sqlite_conn.cursor()
    columns = get_columns(cursor, table)

    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()

    if not rows:
        print(f"  {table}: no rows to migrate")
        return

    print(f"  {table}: migrating {len(rows)} rows...")

    with pg_engine.begin() as conn:
        # Check which columns exist in PG
        inspector = sa.inspect(pg_engine)
        pg_columns = {c["name"] for c in inspector.get_columns(table)}
        # Only use columns that exist in both
        shared_cols = [c for c in columns if c in pg_columns]

        # SQLite boolean columns store 0/1, PostgreSQL needs True/False
        bool_cols = set()
        for col_info in inspector.get_columns(table):
            if str(col_info["type"]) == "BOOLEAN":
                bool_cols.add(col_info["name"])

        for row in rows:
            values = {}
            for c in shared_cols:
                v = row[c]
                if c in bool_cols and v is not None:
                    v = bool(v)
                values[c] = v
            placeholders = ", ".join(f":{c}" for c in shared_cols)
            col_names = ", ".join(shared_cols)
            # Use ON CONFLICT DO NOTHING to skip duplicates
            stmt = sa.text(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT DO NOTHING"
            )
            conn.execute(stmt, values)

    print(f"  {table}: done")


if __name__ == "__main__":
    print(f"Migrating from {SQLITE_PATH} to PostgreSQL...")
    print(f"DATABASE_URL: {PG_URL[:30]}...")

    # Ensure tables exist
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)

    for table in TABLES:
        try:
            migrate_table(table)
        except Exception as e:
            print(f"  {table}: ERROR - {e}")

    # Reset sequences so new inserts get correct IDs
    with pg_engine.begin() as conn:
        for table in TABLES:
            try:
                conn.execute(sa.text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                ))
            except Exception:
                pass  # badges uses slug as PK, not id

    total = sqlite_conn.execute("SELECT COUNT(*) FROM whiskeys").fetchone()[0]
    pg_count = pg_engine.execute(sa.text("SELECT COUNT(*) FROM whiskeys")).scalar() if hasattr(pg_engine, 'execute') else None
    with pg_engine.connect() as c:
        pg_count = c.execute(sa.text("SELECT COUNT(*) FROM whiskeys")).scalar()
    print(f"\nDone! SQLite had {total} whiskeys, PostgreSQL now has {pg_count}")
    sqlite_conn.close()
