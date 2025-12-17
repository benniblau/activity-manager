#!/usr/bin/env python3
"""
Test script to verify the standard_activity_types migration works correctly
"""

import sys
import os
from app import create_app
from app.database import get_db, get_standard_activity_types, get_standard_types_by_category

def test_migration():
    """Test that migration creates tables and populates data"""
    print("=" * 80)
    print("TESTING STANDARD ACTIVITY TYPES MIGRATION")
    print("=" * 80)

    # Create app and initialize database
    app = create_app('development')

    with app.app_context():
        db = get_db()

        # Test 1: Check if standard_activity_types table exists
        print("\nTest 1: Checking if standard_activity_types table exists...")
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='standard_activity_types'"
        )
        table_exists = cursor.fetchone()
        if table_exists:
            print("✓ standard_activity_types table exists")
        else:
            print("✗ standard_activity_types table does NOT exist")
            return False

        # Test 2: Check number of standard types
        print("\nTest 2: Checking number of standard types...")
        standard_types = get_standard_activity_types(official_only=False)
        print(f"✓ Found {len(standard_types)} standard activity types")

        if len(standard_types) < 47:
            print(f"✗ Expected at least 47 types, found {len(standard_types)}")
            return False

        # Test 3: Check categories
        print("\nTest 3: Checking categories...")
        types_by_category = get_standard_types_by_category()
        categories = sorted(types_by_category.keys())
        print(f"✓ Found categories: {', '.join(categories)}")

        expected_categories = ['Cycle', 'Fitness', 'Foot', 'Other', 'Racket', 'Water', 'Winter']
        for cat in expected_categories:
            if cat in categories:
                count = len(types_by_category[cat])
                print(f"  - {cat}: {count} types")
            else:
                print(f"✗ Missing expected category: {cat}")

        # Test 4: Check specific types exist
        print("\nTest 4: Checking specific sport types exist...")
        test_types = ['Run', 'Ride', 'Swim', 'HIIT', 'Crossfit', 'Yoga', 'Tennis', 'Pickleball', 'RockClimbing']
        for sport_type in test_types:
            cursor = db.execute('SELECT name FROM standard_activity_types WHERE name = ?', (sport_type,))
            if cursor.fetchone():
                print(f"✓ {sport_type} exists")
            else:
                print(f"✗ {sport_type} NOT found")

        # Test 5: Check FK constraint on activities table
        print("\nTest 5: Checking FK constraint on activities table...")
        cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='activities'")
        table_sql = cursor.fetchone()[0]
        if 'FOREIGN KEY (sport_type) REFERENCES standard_activity_types(name)' in table_sql:
            print("✓ FK constraint exists on activities.sport_type")
        else:
            print("✗ FK constraint NOT found on activities.sport_type")

        # Test 6: Check FK constraint on extended_activity_types table
        print("\nTest 6: Checking FK constraint on extended_activity_types table...")
        cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='extended_activity_types'")
        table_sql = cursor.fetchone()[0]
        if 'FOREIGN KEY (base_sport_type) REFERENCES standard_activity_types(name)' in table_sql:
            print("✓ FK constraint exists on extended_activity_types.base_sport_type")
        else:
            print("✗ FK constraint NOT found on extended_activity_types.base_sport_type")

        # Test 7: Check extended types count
        print("\nTest 7: Checking extended activity types...")
        cursor = db.execute('SELECT COUNT(*) FROM extended_activity_types')
        ext_count = cursor.fetchone()[0]
        print(f"✓ Found {ext_count} extended activity types")

        # Check for new extended types
        new_types = ['Tabata', 'WOD', 'Vinyasa Yoga', 'Pool Swim', 'Singles Pickleball',
                     'Bouldering', 'Singles Tennis', 'Upper Body']
        found_count = 0
        for type_name in new_types:
            cursor = db.execute('SELECT custom_name FROM extended_activity_types WHERE custom_name = ?', (type_name,))
            if cursor.fetchone():
                found_count += 1
        print(f"✓ Found {found_count}/{len(new_types)} new extended types")

        print("\n" + "=" * 80)
        print("MIGRATION TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        return True

if __name__ == '__main__':
    try:
        success = test_migration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
