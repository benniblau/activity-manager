#!/usr/bin/env python3
"""
Debug script to see what's happening during migration
"""

import sys
import os
from app import create_app

def debug_migration():
    """Debug the migration process"""
    print("=" * 80)
    print("DEBUGGING MIGRATION")
    print("=" * 80)

    # Create app
    print("\n1. Creating app...")
    app = create_app('development')
    print(f"✓ App created: {app}")
    print(f"✓ Database path: {app.config['DATABASE_PATH']}")

    with app.app_context():
        from app.database import get_db

        print("\n2. Getting database connection...")
        db = get_db()
        print("✓ Database connection obtained")

        print("\n3. Checking tables...")
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✓ Tables in database: {tables}")

        if 'standard_activity_types' in tables:
            print("\n4. Checking standard_activity_types content...")
            cursor = db.execute("SELECT COUNT(*) FROM standard_activity_types")
            count = cursor.fetchone()[0]
            print(f"✓ Number of standard types: {count}")

            if count > 0:
                cursor = db.execute("SELECT name, category FROM standard_activity_types LIMIT 5")
                print("  Sample types:")
                for row in cursor.fetchall():
                    print(f"    - {row[0]} ({row[1]})")
        else:
            print("✗ standard_activity_types table does not exist")

        if 'activities' in tables:
            print("\n5. Checking activities table schema...")
            cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='activities'")
            schema = cursor.fetchone()[0]
            if 'FOREIGN KEY (sport_type) REFERENCES standard_activity_types' in schema:
                print("✓ FK constraint on sport_type EXISTS")
            else:
                print("✗ FK constraint on sport_type MISSING")

        if 'extended_activity_types' in tables:
            print("\n6. Checking extended_activity_types table schema...")
            cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='extended_activity_types'")
            schema = cursor.fetchone()[0]
            if 'FOREIGN KEY (base_sport_type) REFERENCES standard_activity_types' in schema:
                print("✓ FK constraint on base_sport_type EXISTS")
            else:
                print("✗ FK constraint on base_sport_type MISSING")

            cursor = db.execute("SELECT COUNT(*) FROM extended_activity_types")
            count = cursor.fetchone()[0]
            print(f"✓ Number of extended types: {count}")

if __name__ == '__main__':
    try:
        debug_migration()
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
