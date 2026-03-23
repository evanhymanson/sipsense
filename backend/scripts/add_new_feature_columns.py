"""
Migration: Add columns for new consumer features.

- user_ratings.image_path  (photo uploads for tasting journal)
- whiskeys.buy_links       (affiliate retailer links)

New tables (journeys, journey_steps, user_journey_progress) are created
automatically by Base.metadata.create_all() — this script only handles
ALTER TABLE for columns added to existing tables.

Usage:
    cd backend
    .venv/bin/python -m scripts.add_new_feature_columns
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "sipsense.db")
DB_PATH = os.path.abspath(DB_PATH)


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    added = []

    if not _column_exists(cur, "user_ratings", "image_path"):
        cur.execute("ALTER TABLE user_ratings ADD COLUMN image_path VARCHAR")
        added.append("user_ratings.image_path")

    if not _column_exists(cur, "whiskeys", "buy_links"):
        cur.execute("ALTER TABLE whiskeys ADD COLUMN buy_links TEXT")
        added.append("whiskeys.buy_links")

    if not _column_exists(cur, "whiskeys", "image_url"):
        cur.execute("ALTER TABLE whiskeys ADD COLUMN image_url VARCHAR")
        added.append("whiskeys.image_url")

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("All columns already exist -- nothing to do.")


if __name__ == "__main__":
    migrate()
