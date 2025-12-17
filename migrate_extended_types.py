#!/usr/bin/env python3
"""
Migration Script for Extended Activity Types

This script adds the new gym-related extended activity types to the database:
- HYROX
- Weight Training
- LAG (Laufausgleichgymnastik)
- Stretching

Usage:
    python migrate_extended_types.py [database_path]

If no database path is provided, it defaults to 'activities.db' in the current directory.

This script is idempotent - safe to run multiple times without creating duplicates.
"""

import sqlite3
import sys
import os
from datetime import datetime


def table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def extended_type_exists(cursor, base_sport_type, custom_name):
    """Check if an extended activity type already exists"""
    cursor.execute(
        "SELECT id FROM extended_activity_types WHERE base_sport_type = ? AND custom_name = ?",
        (base_sport_type, custom_name)
    )
    return cursor.fetchone() is not None


def add_extended_types(cursor, conn):
    """Add new extended activity types for gym activities"""
    if not table_exists(cursor, 'extended_activity_types'):
        print("  [ERROR] extended_activity_types table does not exist")
        return False

    # Define the new extended types to add
    new_types = [
        {
            'base_sport_type': 'WeightTraining',
            'custom_name': 'HYROX',
            'description': 'High-intensity fitness competition combining running and functional exercises',
            'color_class': 'badge-interval',
            'display_order': 1
        },
        {
            'base_sport_type': 'WeightTraining',
            'custom_name': 'Weight Training',
            'description': 'Traditional strength and resistance training',
            'color_class': 'badge-base',
            'display_order': 2
        },
        {
            'base_sport_type': 'WeightTraining',
            'custom_name': 'LAG',
            'description': 'Laufausgleichgymnastik - Running complementary exercises for injury prevention',
            'color_class': 'badge-recovery',
            'display_order': 3
        },
        {
            'base_sport_type': 'WeightTraining',
            'custom_name': 'Stretching',
            'description': 'Flexibility and mobility work',
            'color_class': 'badge-easy',
            'display_order': 4
        }
    ]

    added_count = 0
    skipped_count = 0

    for ext_type in new_types:
        if extended_type_exists(cursor, ext_type['base_sport_type'], ext_type['custom_name']):
            print(f"  [SKIP] {ext_type['custom_name']} already exists")
            skipped_count += 1
        else:
            cursor.execute('''
                INSERT INTO extended_activity_types
                (base_sport_type, custom_name, description, color_class, display_order, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (
                ext_type['base_sport_type'],
                ext_type['custom_name'],
                ext_type['description'],
                ext_type['color_class'],
                ext_type['display_order']
            ))
            print(f"  [ADD] {ext_type['custom_name']} ({ext_type['color_class']})")
            added_count += 1

    if added_count > 0:
        conn.commit()
        print(f"\n✓ Added {added_count} new extended activity type(s)")

    if skipped_count > 0:
        print(f"✓ Skipped {skipped_count} existing extended activity type(s)")

    return True


def main():
    """Main migration function"""
    # Get database path from command line or use default
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'activities.db'

    # Check if database exists
    if not os.path.exists(db_path):
        print(f"ERROR: Database file '{db_path}' not found")
        print("\nUsage: python migrate_extended_types.py [database_path]")
        sys.exit(1)

    print(f"Starting migration for: {db_path}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 60)

    # Create backup recommendation
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\nRECOMMENDATION: Create a backup first:")
    print(f"  cp {db_path} {backup_path}")
    print()

    response = input("Continue with migration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled")
        sys.exit(0)

    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print("\nAdding extended activity types...")
        add_extended_types(cursor, conn)

        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)

    except sqlite3.Error as e:
        print(f"\nERROR: Database error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Unexpected error occurred: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    main()
