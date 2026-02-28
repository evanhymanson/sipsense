"""
Migration: Add social columns to user_ratings table.

New tables (toasts, badges, user_badges) are created automatically by
Base.metadata.create_all() — this script only handles ALTER TABLE for
columns added to existing tables.

Usage:
    cd backend
    .venv/bin/python -m scripts.add_social_columns
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

    if not _column_exists(cur, "user_ratings", "serving_style"):
        cur.execute("ALTER TABLE user_ratings ADD COLUMN serving_style VARCHAR")
        added.append("user_ratings.serving_style")

    if not _column_exists(cur, "user_ratings", "location_note"):
        cur.execute("ALTER TABLE user_ratings ADD COLUMN location_note VARCHAR")
        added.append("user_ratings.location_note")

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("All columns already exist — nothing to do.")


if __name__ == "__main__":
    migrate()
