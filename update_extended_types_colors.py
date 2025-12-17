#!/usr/bin/env python3
"""
Migration Script to Update Extended Activity Type Colors and Icons

This script updates existing extended activity types to:
- Use colors that match their base sport type
- Add Font Awesome icons that represent each activity type

Usage:
    python update_extended_types_colors.py [database_path]

If no database path is provided, it defaults to 'activities.db' in the current directory.

This script is idempotent - safe to run multiple times.
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


def update_extended_type_styling(cursor, conn):
    """Update extended activity types with correct colors and icons"""
    if not table_exists(cursor, 'extended_activity_types'):
        print("  [ERROR] extended_activity_types table does not exist")
        return False

    # Define the updates for each extended type
    updates = {
        # Run types - Green (#28a745)
        'Easy Run': {
            'icon': 'fa-solid fa-person-walking',
            'color': 'badge-sport-run'
        },
        'Tempo Run': {
            'icon': 'fa-solid fa-person-running',
            'color': 'badge-sport-run'
        },
        'Interval Run': {
            'icon': 'fa-solid fa-person-running-fast',
            'color': 'badge-sport-run'
        },
        'Long Run': {
            'icon': 'fa-solid fa-person-hiking',
            'color': 'badge-sport-run'
        },
        'Recovery Run': {
            'icon': 'fa-solid fa-spa',
            'color': 'badge-sport-run'
        },

        # Ride types - Orange (#fd7e14)
        'Zone 2 Ride': {
            'icon': 'fa-solid fa-bicycle',
            'color': 'badge-sport-ride'
        },
        'Threshold Ride': {
            'icon': 'fa-solid fa-gauge-high',
            'color': 'badge-sport-ride'
        },
        'Recovery Ride': {
            'icon': 'fa-solid fa-heart',
            'color': 'badge-sport-ride'
        },

        # WeightTraining types - Purple (#6f42c1)
        'HYROX': {
            'icon': 'fa-solid fa-fire',
            'color': 'badge-sport-weighttraining'
        },
        'Weight Training': {
            'icon': 'fa-solid fa-dumbbell',
            'color': 'badge-sport-weighttraining'
        },
        'LAG': {
            'icon': 'fa-solid fa-arrows-spin',
            'color': 'badge-sport-weighttraining'
        },
        'Stretching': {
            'icon': 'fa-solid fa-spa',
            'color': 'badge-sport-weighttraining'
        }
    }

    updated_count = 0
    not_found_count = 0

    for custom_name, styling in updates.items():
        # Check if this extended type exists
        cursor.execute(
            "SELECT id FROM extended_activity_types WHERE custom_name = ?",
            (custom_name,)
        )
        result = cursor.fetchone()

        if result:
            cursor.execute('''
                UPDATE extended_activity_types
                SET icon_override = ?, color_class = ?
                WHERE custom_name = ?
            ''', (styling['icon'], styling['color'], custom_name))
            print(f"  [UPDATE] {custom_name} - {styling['icon']} ({styling['color']})")
            updated_count += 1
        else:
            print(f"  [SKIP] {custom_name} - type does not exist")
            not_found_count += 1

    if updated_count > 0:
        conn.commit()
        print(f"\n✓ Updated {updated_count} extended activity type(s)")

    if not_found_count > 0:
        print(f"✓ Skipped {not_found_count} non-existent type(s)")

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
        print("\nUsage: python update_extended_types_colors.py [database_path]")
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

        print("\nUpdating extended activity type colors and icons...")
        update_extended_type_styling(cursor, conn)

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
