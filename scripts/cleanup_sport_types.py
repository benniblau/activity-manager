#!/usr/bin/env python3
"""
Cleanup Sport Types Script

Fixes `root='XYZ'` entries that were created in standard_activity_types when
the Strava API returned raw enum strings (e.g. root='Run') instead of plain
sport type names. The migration treated these as unknown types and stored them
verbatim, which causes them to appear in UI dropdowns.

What this script does:
  1. Finds all standard_activity_types rows whose name matches root='...'
  2. Extracts the clean name (e.g. root='Run' -> Run)
  3. Updates any activities/planned_activities rows that reference the raw name
     to use the clean name instead
  4. Deletes the root='...' rows from standard_activity_types

The operation is wrapped in a transaction and a backup is made first.
Safe to run multiple times (idempotent).

Usage:
    python scripts/cleanup_sport_types.py [database_path]

If database_path is omitted, reads DATABASE_PATH from .env or defaults to
activities.db in the project root.
"""

import sqlite3
import sys
import os
import re
import shutil
from datetime import datetime


def backup_database(db_path):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.pre_cleanup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path


def parse_root_name(raw):
    """Extract clean name from root='XYZ' format, or return None if not that format."""
    m = re.match(r"^root='(.+)'$", raw)
    return m.group(1) if m else None


def cleanup_sport_types(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find all root='...' entries
    cursor.execute(
        "SELECT name FROM standard_activity_types WHERE name LIKE \"root='%'\""
    )
    bad_rows = cursor.fetchall()

    if not bad_rows:
        print("✓ No root='...' entries found — nothing to clean up.")
        return

    print(f"Found {len(bad_rows)} root='...' entries to clean up:\n")

    for row in bad_rows:
        raw_name = row['name']
        clean_name = parse_root_name(raw_name)

        if not clean_name:
            print(f"  SKIP  {raw_name!r} — could not parse clean name")
            continue

        # Check if the clean name already exists in standard_activity_types
        cursor.execute(
            "SELECT name FROM standard_activity_types WHERE name = ?", (clean_name,)
        )
        target_exists = cursor.fetchone() is not None

        if target_exists:
            # Remap activities to the existing clean entry, then delete the bad row
            cursor.execute(
                "UPDATE activities SET sport_type = ? WHERE sport_type = ?",
                (clean_name, raw_name)
            )
            acts_updated = cursor.rowcount

            cursor.execute(
                "UPDATE planned_activities SET sport_type = ? WHERE sport_type = ?",
                (clean_name, raw_name)
            )
            plans_updated = cursor.rowcount

            cursor.execute(
                "DELETE FROM standard_activity_types WHERE name = ?", (raw_name,)
            )
            print(
                f"  FIXED  {raw_name!r} → {clean_name!r}  "
                f"(activities: {acts_updated}, planned: {plans_updated})"
            )

        else:
            # Clean name doesn't exist — rename the row in-place.
            # SQLite has no RENAME COLUMN for the PK, so we update the name
            # and display_name and mark it official if it looks like a known type.
            cursor.execute(
                """UPDATE standard_activity_types
                   SET name = ?, display_name = ?, is_official = 0
                   WHERE name = ?""",
                (clean_name, clean_name, raw_name)
            )
            # Remap any activities that referenced the old raw name
            cursor.execute(
                "UPDATE activities SET sport_type = ? WHERE sport_type = ?",
                (clean_name, raw_name)
            )
            acts_updated = cursor.rowcount

            cursor.execute(
                "UPDATE planned_activities SET sport_type = ? WHERE sport_type = ?",
                (clean_name, raw_name)
            )
            plans_updated = cursor.rowcount

            print(
                f"  RENAMED  {raw_name!r} → {clean_name!r}  "
                f"(activities: {acts_updated}, planned: {plans_updated})"
            )

    conn.commit()
    print("\n✓ Cleanup complete.")


def resolve_db_path(arg=None):
    if arg:
        return arg
    # Try to read from .env
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('DATABASE_PATH='):
                    return line.split('=', 1)[1].strip().strip('"\'')
    # Default
    return os.path.join(os.path.dirname(__file__), '..', 'activities.db')


if __name__ == '__main__':
    db_path = resolve_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    db_path = os.path.abspath(db_path)

    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}")
        sys.exit(1)

    print(f"Database: {db_path}\n")

    backup_database(db_path)

    conn = sqlite3.connect(db_path)
    try:
        cleanup_sport_types(conn)
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        print("Changes rolled back. The backup is safe.")
        sys.exit(1)
    finally:
        conn.close()
