#!/usr/bin/env python3
"""
Database Migration Script for Activity Manager

This script safely migrates an existing database to add:
- strava_tokens table for persistent OAuth tokens
- coach_comment column to the days table
- coach_comment column to the activities table
- feeling annotation columns to the activities table (if missing)

Usage:
    python migrate_db.py [database_path]

If no database path is provided, it defaults to 'activities.db' in the current directory.

This script is idempotent - safe to run multiple times without data loss.
"""

import sqlite3
import sys
import os
from datetime import datetime


def get_existing_columns(cursor, table_name):
    """Get set of existing column names for a table"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_activities_table(cursor, conn):
    """Add new columns to the activities table"""
    if not table_exists(cursor, 'activities'):
        print("  [SKIP] activities table does not exist")
        return False

    existing_columns = get_existing_columns(cursor, 'activities')

    # Define columns to add
    new_columns = [
        ('feeling_before_text', 'TEXT'),
        ('feeling_before_pain', 'INTEGER'),
        ('feeling_during_text', 'TEXT'),
        ('feeling_during_pain', 'INTEGER'),
        ('feeling_after_text', 'TEXT'),
        ('feeling_after_pain', 'INTEGER'),
        ('day_date', 'TEXT'),
        ('coach_comment', 'TEXT'),
    ]

    added = []
    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            print(f"  [ADD] Adding column '{column_name}' to activities table...")
            cursor.execute(f'ALTER TABLE activities ADD COLUMN {column_name} {column_type}')
            added.append(column_name)
        else:
            print(f"  [OK] Column '{column_name}' already exists")

    # Populate day_date for existing activities that don't have it set
    if 'day_date' in added or 'day_date' in existing_columns:
        cursor.execute('''
            UPDATE activities
            SET day_date = substr(start_date_local, 1, 10)
            WHERE day_date IS NULL AND start_date_local IS NOT NULL
        ''')
        updated_count = cursor.rowcount
        if updated_count > 0:
            print(f"  [UPDATE] Populated day_date for {updated_count} activities")

    conn.commit()
    return len(added) > 0


def migrate_days_table(cursor, conn):
    """Add coach_comment column to the days table"""
    if not table_exists(cursor, 'days'):
        print("  [SKIP] days table does not exist - will be created on app startup")
        return False

    existing_columns = get_existing_columns(cursor, 'days')

    if 'coach_comment' not in existing_columns:
        print("  [ADD] Adding column 'coach_comment' to days table...")
        cursor.execute('ALTER TABLE days ADD COLUMN coach_comment TEXT')
        conn.commit()
        return True
    else:
        print("  [OK] Column 'coach_comment' already exists")
        return False


def create_strava_tokens_table(cursor, conn):
    """Create the strava_tokens table for persistent OAuth tokens"""
    if table_exists(cursor, 'strava_tokens'):
        print("  [OK] strava_tokens table already exists")
        return False

    print("  [CREATE] Creating strava_tokens table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strava_tokens (
            id INTEGER PRIMARY KEY DEFAULT 1,
            athlete_id INTEGER,
            athlete_name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CHECK (id = 1)
        )
    ''')
    conn.commit()
    return True


def create_gear_table(cursor, conn):
    """Create the gear table for equipment (bikes, shoes, etc.)"""
    if table_exists(cursor, 'gear'):
        print("  [OK] gear table already exists")
        return False

    print("  [CREATE] Creating gear table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gear (
            id TEXT PRIMARY KEY,
            name TEXT,
            brand_name TEXT,
            model_name TEXT,
            gear_type TEXT,
            description TEXT,
            distance REAL DEFAULT 0,
            converted_distance REAL DEFAULT 0,
            primary_gear INTEGER DEFAULT 0,
            retired INTEGER DEFAULT 0,
            resource_state INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return True


def create_days_table_if_missing(cursor, conn):
    """Create the days table if it doesn't exist"""
    if table_exists(cursor, 'days'):
        return False

    print("  [CREATE] Creating days table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY,
            feeling_text TEXT,
            feeling_pain INTEGER,
            coach_comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return True


def create_indexes(cursor, conn):
    """Create indexes for common queries if they don't exist"""
    indexes = [
        ('idx_start_date', 'activities', 'start_date'),
        ('idx_sport_type', 'activities', 'sport_type'),
        ('idx_type', 'activities', 'type'),
        ('idx_day_date', 'activities', 'day_date'),
        ('idx_gear_id', 'activities', 'gear_id'),
    ]

    created = []
    for idx_name, table_name, column_name in indexes:
        if not table_exists(cursor, table_name):
            continue

        # Check if index exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
            (idx_name,)
        )
        if cursor.fetchone():
            print(f"  [OK] Index '{idx_name}' already exists")
        else:
            print(f"  [CREATE] Creating index '{idx_name}'...")
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({column_name})')
            created.append(idx_name)

    if created:
        conn.commit()
    return len(created) > 0


def get_database_info(cursor):
    """Get information about the current database state"""
    info = {}

    # Get table list
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    info['tables'] = [row[0] for row in cursor.fetchall()]

    # Get row counts for relevant tables
    for table in ['activities', 'days', 'strava_tokens', 'gear']:
        if table in info['tables']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            info[f'{table}_count'] = cursor.fetchone()[0]
        else:
            info[f'{table}_count'] = 0

    return info


def run_migration(db_path):
    """Run all database migrations"""
    print(f"\n{'='*60}")
    print("Activity Manager Database Migration")
    print(f"{'='*60}")
    print(f"\nDatabase: {db_path}")
    print(f"Started: {datetime.now().isoformat()}")

    if not os.path.exists(db_path):
        print(f"\n[ERROR] Database file not found: {db_path}")
        print("Please provide the correct path to your database file.")
        return False

    # Create backup reminder
    print(f"\n[WARNING] Always backup your database before running migrations!")
    print(f"  Backup command: cp {db_path} {db_path}.backup.$(date +%Y%m%d_%H%M%S)")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get initial state
        print("\n" + "-"*40)
        print("Current Database State:")
        print("-"*40)
        info = get_database_info(cursor)
        print(f"  Tables: {', '.join(info['tables']) or 'None'}")
        print(f"  Activities: {info['activities_count']} rows")
        print(f"  Days: {info['days_count']} rows")
        print(f"  Strava Tokens: {info['strava_tokens_count']} rows")
        print(f"  Gear: {info['gear_count']} rows")

        # Run migrations
        print("\n" + "-"*40)
        print("Running Migrations:")
        print("-"*40)

        changes = []

        print("\n1. Strava Tokens Table:")
        if create_strava_tokens_table(cursor, conn):
            changes.append("Created strava_tokens table")

        print("\n2. Days Table:")
        if create_days_table_if_missing(cursor, conn):
            changes.append("Created days table")
        if migrate_days_table(cursor, conn):
            changes.append("Added coach_comment to days table")

        print("\n3. Activities Table:")
        if migrate_activities_table(cursor, conn):
            changes.append("Added new columns to activities table")

        print("\n4. Gear Table:")
        if create_gear_table(cursor, conn):
            changes.append("Created gear table")

        print("\n5. Indexes:")
        if create_indexes(cursor, conn):
            changes.append("Created missing indexes")

        # Get final state
        print("\n" + "-"*40)
        print("Final Database State:")
        print("-"*40)
        info = get_database_info(cursor)
        print(f"  Tables: {', '.join(info['tables'])}")
        print(f"  Activities: {info['activities_count']} rows")
        print(f"  Days: {info['days_count']} rows")
        print(f"  Strava Tokens: {info['strava_tokens_count']} rows")
        print(f"  Gear: {info['gear_count']} rows")

        # Summary
        print("\n" + "="*60)
        print("Migration Summary:")
        print("="*60)
        if changes:
            print(f"  Changes made: {len(changes)}")
            for change in changes:
                print(f"    - {change}")
        else:
            print("  No changes needed - database is up to date!")

        print(f"\nCompleted: {datetime.now().isoformat()}")
        print("[SUCCESS] Migration completed successfully!\n")

        conn.close()
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Default paths to check
        default_paths = [
            'activities.db',
            '/opt/activity-manager/activities.db',
            os.path.join(os.path.dirname(__file__), 'activities.db'),
        ]

        db_path = None
        for path in default_paths:
            if os.path.exists(path):
                db_path = path
                break

        if not db_path:
            print("Usage: python migrate_db.py [database_path]")
            print("\nNo database file found at default locations:")
            for path in default_paths:
                print(f"  - {path}")
            print("\nPlease provide the path to your database file.")
            sys.exit(1)

    success = run_migration(db_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
