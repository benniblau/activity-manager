#!/usr/bin/env python3
"""
Database cleanup script to fix sport types with 'relax/' prefix

This script updates existing activities and standard_activity_types to use clean
sport type names instead of the Strava enum format.

Example transformations:
  - "relax/weighttraining" -> "WeightTraining"
  - "relax/run" -> "Run"
  - "relax/virtualride" -> "VirtualRide"
"""

import sqlite3
import sys
from pathlib import Path


def clean_sport_type(sport_type):
    """Clean up Strava enum string values

    Handles patterns like:
    - 'relax/weighttraining' -> 'WeightTraining'
    - "root='WeightTraining'" -> 'WeightTraining'

    Args:
        sport_type: Original sport type string

    Returns:
        Cleaned sport type string
    """
    if not sport_type or not isinstance(sport_type, str):
        return sport_type

    # Handle "root='Value'" pattern from XML/enum string representation
    if sport_type.startswith("root='") and sport_type.endswith("'"):
        return sport_type[6:-1]  # Extract 'Value' from "root='Value'"

    # Check if it has the relax/ prefix
    if '/' in sport_type:
        parts = sport_type.split('/')
        if len(parts) == 2:
            sport = parts[1]
            # Convert to PascalCase (e.g., "weighttraining" -> "WeightTraining")
            return ''.join(word.capitalize() for word in sport.replace('(', '').replace(')', '').split())

    return sport_type


def main():
    # Database path
    db_path = Path(__file__).parent / 'activities.db'

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Find all activities with problematic patterns in type or sport_type
        print("\n=== Scanning for activities with problematic type patterns ===")
        cursor.execute("""
            SELECT id, type, sport_type, name
            FROM activities
            WHERE type LIKE '%/%'
               OR sport_type LIKE '%/%'
               OR type LIKE "root='%'"
               OR sport_type LIKE "root='%'"
        """)

        activities_to_fix = cursor.fetchall()

        if not activities_to_fix:
            print("No activities found with problematic patterns. Database is clean!")
        else:
            print(f"Found {len(activities_to_fix)} activities to fix:")

            # Preview changes
            print("\nPreview of changes:")
            for activity in activities_to_fix[:10]:  # Show first 10
                old_type = activity['type']
                new_type_cleaned = clean_sport_type(old_type)
                old_sport = activity['sport_type']
                new_sport_cleaned = clean_sport_type(old_sport)

                print(f"  ID {activity['id']}: ({activity['name']})")
                if '/' in old_type:
                    print(f"    type: '{old_type}' -> '{new_type_cleaned}'")
                if '/' in old_sport:
                    print(f"    sport_type: '{old_sport}' -> '{new_sport_cleaned}'")

            if len(activities_to_fix) > 10:
                print(f"  ... and {len(activities_to_fix) - 10} more")

            # Ask for confirmation
            print("\nThis will update the database. Continue? (y/n): ", end='')
            response = input().strip().lower()

            if response != 'y':
                print("Aborted.")
                sys.exit(0)

            # Update activities
            print("\n=== Updating activities ===")
            updated_count = 0

            for activity in activities_to_fix:
                old_type = activity['type']
                new_type = clean_sport_type(old_type)
                old_sport = activity['sport_type']
                new_sport = clean_sport_type(old_sport)

                # Update both type and sport_type columns
                cursor.execute("""
                    UPDATE activities
                    SET type = ?, sport_type = ?
                    WHERE id = ?
                """, (new_type, new_sport, activity['id']))

                updated_count += 1
                if updated_count % 50 == 0:
                    print(f"  Updated {updated_count} activities...")

            print(f"✓ Updated {updated_count} activities")

        # Find all standard_activity_types with 'relax/' prefix
        print("\n=== Scanning for standard types with 'relax/' names ===")
        cursor.execute("""
            SELECT name, category, icon
            FROM standard_activity_types
            WHERE name LIKE '%/%'
        """)

        types_to_fix = cursor.fetchall()

        if not types_to_fix:
            print("No standard activity types found with 'relax/' prefix.")
        else:
            print(f"Found {len(types_to_fix)} standard types to fix:")

            # Preview changes
            print("\nPreview of changes:")
            for type_row in types_to_fix:
                old_name = type_row['name']
                new_name = clean_sport_type(old_name)
                print(f"  '{old_name}' -> '{new_name}' (category: {type_row['category']})")

            # Update standard_activity_types
            # Note: name is the primary key, so we need to INSERT new row and DELETE old
            print("\n=== Updating standard_activity_types ===")
            type_updated_count = 0

            for type_row in types_to_fix:
                old_name = type_row['name']
                new_name = clean_sport_type(old_name)
                category = type_row['category']
                icon = type_row['icon']

                # Check if new name already exists
                cursor.execute("SELECT name FROM standard_activity_types WHERE name = ?", (new_name,))
                if cursor.fetchone():
                    # Already exists, just delete the old one
                    cursor.execute("DELETE FROM standard_activity_types WHERE name = ?", (old_name,))
                else:
                    # Insert new name, then delete old
                    cursor.execute("""
                        INSERT INTO standard_activity_types (name, category, icon)
                        VALUES (?, ?, ?)
                    """, (new_name, category, icon))
                    cursor.execute("DELETE FROM standard_activity_types WHERE name = ?", (old_name,))

                type_updated_count += 1

            print(f"✓ Updated {type_updated_count} standard types")

        # Commit all changes
        conn.commit()

        print("\n=== Summary ===")
        print(f"✓ Updated {updated_count if activities_to_fix else 0} activities")
        print(f"✓ Updated {type_updated_count if types_to_fix else 0} standard types")
        print("✓ Database cleanup complete!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
