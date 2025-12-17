#!/usr/bin/env python3
"""
Production database migration: Add standard_activity_types table with FK constraints
Creates backups, handles orphaned data, and validates results
"""

import sys
import os
import sqlite3
import shutil
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def backup_database(db_path):
    """Create timestamped backup before migration"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"✓ Backup created: {backup_path}")
    return backup_path

def verify_integrity(db_path):
    """Run SQLite integrity check"""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute('PRAGMA integrity_check')
    result = cursor.fetchone()[0]
    conn.close()
    return result == 'ok'

def migrate_database(db_path):
    """Main migration function"""
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    cursor = conn.cursor()

    try:
        # Check if migration already completed
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='standard_activity_types'")
        if cursor.fetchone():
            print("⚠️  Migration already completed (standard_activity_types exists)")
            return False

        print("\n" + "="*60)
        print("STARTING MIGRATION")
        print("="*60 + "\n")

        # STEP 1: Create standard_activity_types table
        print("Step 1: Creating standard_activity_types table...")
        cursor.execute('''
            CREATE TABLE standard_activity_types (
                name TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                display_name TEXT NOT NULL,
                icon TEXT,
                color TEXT,
                description TEXT,
                is_official INTEGER DEFAULT 1,
                display_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX idx_standard_types_category ON standard_activity_types(category)')
        print("✓ Table created")

        # STEP 2: Populate standard types
        print("\nStep 2: Populating standard activity types...")
        standard_types = [
            # FOOT SPORTS
            ('Run', 'Foot', 'Run', 'person-running', 'badge-sport-run', 'Running', 1, 10),
            ('TrailRun', 'Foot', 'Trail Run', 'person-hiking', 'badge-sport-run', 'Trail running', 1, 11),
            ('Walk', 'Foot', 'Walk', 'person-walking', 'badge-sport-walk', 'Walking', 1, 12),
            ('Hike', 'Foot', 'Hike', 'mountain', 'badge-sport-hike', 'Hiking', 1, 13),
            ('VirtualRun', 'Foot', 'Virtual Run', 'tv', 'badge-sport-run', 'Virtual/treadmill run', 1, 14),

            # CYCLE SPORTS
            ('Ride', 'Cycle', 'Ride', 'person-biking', 'badge-sport-ride', 'Road cycling', 1, 20),
            ('MountainBikeRide', 'Cycle', 'Mountain Bike Ride', 'mountain', 'badge-sport-ride', 'Mountain biking', 1, 21),
            ('GravelRide', 'Cycle', 'Gravel Ride', 'road', 'badge-sport-ride', 'Gravel cycling', 1, 22),
            ('EBikeRide', 'Cycle', 'E-Bike Ride', 'bolt', 'badge-sport-ride', 'Electric bike', 1, 23),
            ('EMountainBikeRide', 'Cycle', 'E-Mountain Bike Ride', 'bolt', 'badge-sport-ride', 'E-mountain bike', 1, 24),
            ('Velomobile', 'Cycle', 'Velomobile', 'car-side', 'badge-sport-ride', 'Velomobile', 1, 25),
            ('VirtualRide', 'Cycle', 'Virtual Ride', 'tv', 'badge-sport-ride', 'Virtual/trainer ride', 1, 26),
            ('Handcycle', 'Cycle', 'Handcycle', 'wheelchair', 'badge-sport-ride', 'Hand cycling', 1, 27),

            # WATER SPORTS
            ('Swim', 'Water', 'Swim', 'person-swimming', 'badge-sport-swim', 'Swimming', 1, 30),
            ('Canoe', 'Water', 'Canoe', 'water', 'badge-sport-water', 'Canoeing', 1, 31),
            ('Kayaking', 'Water', 'Kayaking', 'water', 'badge-sport-water', 'Kayaking', 1, 32),
            ('Kitesurf', 'Water', 'Kitesurf', 'wind', 'badge-sport-water', 'Kitesurfing', 1, 33),
            ('Rowing', 'Water', 'Rowing', 'water', 'badge-sport-water', 'Rowing', 1, 34),
            ('StandUpPaddling', 'Water', 'Stand Up Paddling', 'water', 'badge-sport-water', 'SUP', 1, 35),
            ('Surfing', 'Water', 'Surfing', 'water', 'badge-sport-water', 'Surfing', 1, 36),
            ('Windsurf', 'Water', 'Windsurf', 'wind', 'badge-sport-water', 'Windsurfing', 1, 37),
            ('Sail', 'Water', 'Sail', 'sailboat', 'badge-sport-water', 'Sailing', 1, 38),
            ('VirtualRow', 'Water', 'Virtual Row', 'tv', 'badge-sport-water', 'Indoor rowing', 1, 39),

            # WINTER SPORTS
            ('IceSkate', 'Winter', 'Ice Skate', 'snowflake', 'badge-sport-winter', 'Ice skating', 1, 40),
            ('AlpineSki', 'Winter', 'Alpine Ski', 'person-skiing', 'badge-sport-winter', 'Downhill skiing', 1, 41),
            ('BackcountrySki', 'Winter', 'Backcountry Ski', 'mountain', 'badge-sport-winter', 'Backcountry skiing', 1, 42),
            ('NordicSki', 'Winter', 'Nordic Ski', 'person-skiing-nordic', 'badge-sport-winter', 'Cross-country skiing', 1, 43),
            ('Snowboard', 'Winter', 'Snowboard', 'person-snowboarding', 'badge-sport-winter', 'Snowboarding', 1, 44),
            ('Snowshoe', 'Winter', 'Snowshoe', 'shoe-prints', 'badge-sport-winter', 'Snowshoeing', 1, 45),

            # FITNESS & GYM
            ('WeightTraining', 'Fitness', 'Weight Training', 'dumbbell', 'badge-sport-weighttraining', 'Weight training', 1, 50),
            ('Workout', 'Fitness', 'Workout', 'heart-pulse', 'badge-sport-workout', 'General workout', 1, 51),
            ('HIIT', 'Fitness', 'HIIT', 'fire', 'badge-sport-hiit', 'High-intensity intervals', 1, 52),
            ('Crossfit', 'Fitness', 'CrossFit', 'dumbbell', 'badge-sport-crossfit', 'CrossFit', 1, 53),
            ('Yoga', 'Fitness', 'Yoga', 'spa', 'badge-sport-yoga', 'Yoga', 1, 54),
            ('Pilates', 'Fitness', 'Pilates', 'spa', 'badge-sport-pilates', 'Pilates', 1, 55),
            ('Elliptical', 'Fitness', 'Elliptical', 'circle-dot', 'badge-sport-elliptical', 'Elliptical trainer', 1, 56),
            ('StairStepper', 'Fitness', 'Stair Stepper', 'stairs', 'badge-sport-stairs', 'Stair stepper', 1, 57),

            # RACKET SPORTS
            ('Tennis', 'Racket', 'Tennis', 'table-tennis-paddle-ball', 'badge-sport-tennis', 'Tennis', 1, 60),
            ('Pickleball', 'Racket', 'Pickleball', 'table-tennis-paddle-ball', 'badge-sport-pickleball', 'Pickleball', 1, 61),
            ('Badminton', 'Racket', 'Badminton', 'shuttlecock', 'badge-sport-badminton', 'Badminton', 1, 62),
            ('TableTennis', 'Racket', 'Table Tennis', 'table-tennis-paddle-ball', 'badge-sport-tabletennis', 'Table tennis', 1, 63),
            ('Squash', 'Racket', 'Squash', 'square', 'badge-sport-squash', 'Squash', 1, 64),
            ('Racquetball', 'Racket', 'Racquetball', 'circle', 'badge-sport-racquetball', 'Racquetball', 1, 65),

            # OTHER SPORTS
            ('RockClimbing', 'Other', 'Rock Climbing', 'mountain', 'badge-sport-climbing', 'Rock climbing', 1, 70),
            ('InlineSkate', 'Other', 'Inline Skate', 'shoe-prints', 'badge-sport-inlineskate', 'Inline skating', 1, 71),
            ('RollerSki', 'Other', 'Roller Ski', 'person-skiing', 'badge-sport-rollerski', 'Roller skiing', 1, 72),
            ('Golf', 'Other', 'Golf', 'golf-ball-tee', 'badge-sport-golf', 'Golf', 1, 73),
            ('Skateboard', 'Other', 'Skateboard', 'person-skating', 'badge-sport-skateboard', 'Skateboarding', 1, 74),
            ('Soccer', 'Other', 'Soccer', 'futbol', 'badge-sport-soccer', 'Soccer/Football', 1, 75),
            ('Wheelchair', 'Other', 'Wheelchair', 'wheelchair', 'badge-sport-wheelchair', 'Wheelchair activity', 1, 76),
        ]

        cursor.executemany('''
            INSERT INTO standard_activity_types
            (name, category, display_name, icon, color, description, is_official, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', standard_types)
        print(f"✓ Added {len(standard_types)} standard activity types")

        # STEP 3: Handle orphaned sport types from existing activities
        print("\nStep 3: Checking for orphaned sport types...")
        cursor.execute('''
            SELECT DISTINCT sport_type FROM activities
            WHERE sport_type NOT IN (SELECT name FROM standard_activity_types)
            AND sport_type IS NOT NULL
        ''')
        orphaned = [row[0] for row in cursor.fetchall()]

        if orphaned:
            print(f"⚠️  Found {len(orphaned)} orphaned sport types: {orphaned}")
            for sport_type in orphaned:
                cursor.execute('''
                    INSERT INTO standard_activity_types
                    (name, category, display_name, icon, color, is_official, display_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (sport_type, 'Other', sport_type, 'circle-question', 'badge-other', 0, 999))
                print(f"  ✓ Auto-created: {sport_type}")
        else:
            print("✓ No orphaned sport types found")

        # STEP 4: Recreate activities table with FK constraint
        print("\nStep 4: Recreating activities table with FK constraint...")
        cursor.execute('ALTER TABLE activities RENAME TO activities_old')

        cursor.execute('''
            CREATE TABLE activities (
                id INTEGER PRIMARY KEY,
                resource_state INTEGER,
                external_id TEXT,
                upload_id INTEGER,
                start_date TEXT NOT NULL,
                start_date_local TEXT NOT NULL,
                timezone TEXT,
                utc_offset INTEGER,
                elapsed_time INTEGER NOT NULL,
                moving_time INTEGER,
                start_latlng TEXT,
                end_latlng TEXT,
                location_city TEXT,
                location_state TEXT,
                location_country TEXT,
                map TEXT,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT,
                sport_type TEXT NOT NULL,
                workout_type INTEGER,
                distance REAL,
                total_elevation_gain REAL,
                average_speed REAL,
                max_speed REAL,
                average_cadence REAL,
                average_watts REAL,
                weighted_average_watts REAL,
                kilojoules REAL,
                device_watts INTEGER,
                max_watts INTEGER,
                average_heartrate REAL,
                max_heartrate INTEGER,
                has_heartrate INTEGER DEFAULT 0,
                average_temp INTEGER,
                calories REAL,
                elev_high REAL,
                elev_low REAL,
                kudos_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                athlete_count INTEGER DEFAULT 1,
                photo_count INTEGER DEFAULT 0,
                total_photo_count INTEGER DEFAULT 0,
                pr_count INTEGER DEFAULT 0,
                achievement_count INTEGER DEFAULT 0,
                trainer INTEGER DEFAULT 0,
                commute INTEGER DEFAULT 0,
                manual INTEGER DEFAULT 0,
                private INTEGER DEFAULT 0,
                flagged INTEGER DEFAULT 0,
                has_kudoed INTEGER DEFAULT 0,
                segment_leaderboard_opt_out INTEGER DEFAULT 0,
                leaderboard_opt_out INTEGER DEFAULT 0,
                device_name TEXT,
                athlete_id INTEGER,
                gear_id TEXT,
                segment_efforts TEXT,
                splits_metric TEXT,
                splits_standard TEXT,
                laps TEXT,
                best_efforts TEXT,
                gear TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                feeling_before_text TEXT,
                feeling_before_pain INTEGER,
                feeling_during_text TEXT,
                feeling_during_pain INTEGER,
                feeling_after_text TEXT,
                feeling_after_pain INTEGER,
                coach_comment TEXT,
                extended_type_id INTEGER,
                day_date TEXT,
                FOREIGN KEY (sport_type) REFERENCES standard_activity_types(name) ON DELETE RESTRICT,
                FOREIGN KEY (extended_type_id) REFERENCES extended_activity_types(id) ON DELETE SET NULL,
                FOREIGN KEY (day_date) REFERENCES days(date)
            )
        ''')

        # Copy data
        cursor.execute('INSERT INTO activities SELECT * FROM activities_old')

        # Recreate indexes
        cursor.execute('CREATE INDEX idx_start_date ON activities(start_date)')
        cursor.execute('CREATE INDEX idx_sport_type ON activities(sport_type)')
        cursor.execute('CREATE INDEX idx_type ON activities(type)')
        cursor.execute('CREATE INDEX idx_day_date ON activities(day_date)')
        cursor.execute('CREATE INDEX idx_gear_id ON activities(gear_id)')
        cursor.execute('CREATE INDEX idx_activities_extended_type ON activities(extended_type_id)')

        cursor.execute('DROP TABLE activities_old')
        print("✓ Activities table recreated with FK constraint")

        # STEP 5: Recreate extended_activity_types table with FK constraint
        print("\nStep 5: Recreating extended_activity_types table with FK constraint...")
        cursor.execute('ALTER TABLE extended_activity_types RENAME TO extended_activity_types_old')

        cursor.execute('''
            CREATE TABLE extended_activity_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_sport_type TEXT NOT NULL,
                custom_name TEXT NOT NULL UNIQUE,
                description TEXT,
                icon_override TEXT,
                color_class TEXT,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (base_sport_type) REFERENCES standard_activity_types(name) ON DELETE RESTRICT,
                CHECK (base_sport_type IS NOT NULL AND base_sport_type != '')
            )
        ''')

        cursor.execute('INSERT INTO extended_activity_types SELECT * FROM extended_activity_types_old')

        cursor.execute('CREATE INDEX idx_extended_types_base ON extended_activity_types(base_sport_type)')
        cursor.execute('CREATE INDEX idx_extended_types_active ON extended_activity_types(is_active)')

        cursor.execute('DROP TABLE extended_activity_types_old')
        print("✓ Extended activity types table recreated with FK constraint")

        # STEP 6: Add new extended types
        print("\nStep 6: Adding new extended activity types...")
        new_extended_types = [
            # HIIT
            ('HIIT', 'Tabata', '20s work / 10s rest intervals', 'stopwatch', 'badge-sport-hiit', 100),
            ('HIIT', 'EMOM', 'Every minute on the minute', 'clock', 'badge-sport-hiit', 101),
            ('HIIT', 'AMRAP', 'As many rounds as possible', 'fire', 'badge-sport-hiit', 102),
            ('HIIT', 'Circuit Training', 'Multi-station circuit', 'circle-nodes', 'badge-sport-hiit', 103),
            ('HIIT', 'Interval Sprint', 'Short maximum effort', 'bolt', 'badge-sport-hiit', 104),

            # CROSSFIT
            ('Crossfit', 'WOD', 'Workout of the day', 'calendar-day', 'badge-sport-crossfit', 110),
            ('Crossfit', 'MetCon', 'Metabolic conditioning', 'heart-pulse', 'badge-sport-crossfit', 111),
            ('Crossfit', 'Strength WOD', 'Strength-focused session', 'dumbbell', 'badge-sport-crossfit', 112),
            ('Crossfit', 'Olympic Lifting', 'Clean, snatch, etc.', 'weight-hanging', 'badge-sport-crossfit', 113),
            ('Crossfit', 'Hero WOD', 'Named hero workout', 'medal', 'badge-sport-crossfit', 114),
            ('Crossfit', 'Girls WOD', 'Classic benchmark', 'trophy', 'badge-sport-crossfit', 115),

            # YOGA
            ('Yoga', 'Vinyasa Yoga', 'Dynamic flow yoga', 'water', 'badge-sport-yoga', 120),
            ('Yoga', 'Hatha Yoga', 'Traditional gentle yoga', 'spa', 'badge-sport-yoga', 121),
            ('Yoga', 'Power Yoga', 'Athletic fitness yoga', 'fire', 'badge-sport-yoga', 122),
            ('Yoga', 'Restorative Yoga', 'Relaxing passive stretching', 'bed', 'badge-sport-yoga', 123),
            ('Yoga', 'Yin Yoga', 'Deep long-held stretches', 'moon', 'badge-sport-yoga', 124),
            ('Yoga', 'Hot Yoga', 'Heated room yoga', 'temperature-high', 'badge-sport-yoga', 125),
            ('Yoga', 'Ashtanga Yoga', 'Structured sequence', 'list-ol', 'badge-sport-yoga', 126),

            # SWIMMING
            ('Swim', 'Pool Swim', 'Swimming in pool', 'person-swimming', 'badge-sport-swim', 130),
            ('Swim', 'Open Water Swim', 'Ocean/lake swimming', 'water', 'badge-sport-swim', 131),
            ('Swim', 'Technique Work', 'Drills and form practice', 'graduation-cap', 'badge-sport-swim', 132),
            ('Swim', 'Endurance Swim', 'Long continuous swim', 'gauge-high', 'badge-sport-swim', 133),
            ('Swim', 'Interval Swim', 'Interval training', 'stopwatch', 'badge-sport-swim', 134),
            ('Swim', 'Recovery Swim', 'Easy recovery swim', 'heart', 'badge-sport-swim', 135),

            # PICKLEBALL
            ('Pickleball', 'Singles Pickleball', 'One-on-one match', 'user', 'badge-sport-pickleball', 140),
            ('Pickleball', 'Doubles Pickleball', 'Two-on-two match', 'user-group', 'badge-sport-pickleball', 141),
            ('Pickleball', 'Pickleball Drills', 'Skills practice', 'bullseye', 'badge-sport-pickleball', 142),
            ('Pickleball', 'Tournament Pickleball', 'Competitive play', 'trophy', 'badge-sport-pickleball', 143),

            # ROCK CLIMBING
            ('RockClimbing', 'Bouldering', 'Short powerful climbing', 'mountain', 'badge-sport-climbing', 150),
            ('RockClimbing', 'Sport Climbing', 'Lead with bolted routes', 'link', 'badge-sport-climbing', 151),
            ('RockClimbing', 'Top Rope', 'Anchor at top', 'arrow-up', 'badge-sport-climbing', 152),
            ('RockClimbing', 'Trad Climbing', 'Traditional gear-protected', 'tools', 'badge-sport-climbing', 153),
            ('RockClimbing', 'Indoor Climbing', 'Gym climbing', 'building', 'badge-sport-climbing', 154),
            ('RockClimbing', 'Outdoor Climbing', 'Natural rock', 'tree', 'badge-sport-climbing', 155),

            # TENNIS
            ('Tennis', 'Singles Tennis', 'One-on-one match', 'user', 'badge-sport-tennis', 160),
            ('Tennis', 'Doubles Tennis', 'Two-on-two match', 'user-group', 'badge-sport-tennis', 161),
            ('Tennis', 'Tennis Practice', 'Drills and practice', 'bullseye', 'badge-sport-tennis', 162),
            ('Tennis', 'Tennis Match', 'Competitive match', 'trophy', 'badge-sport-tennis', 163),

            # WEIGHT TRAINING
            ('WeightTraining', 'Upper Body', 'Upper body strength', 'hand-fist', 'badge-sport-weighttraining', 170),
            ('WeightTraining', 'Lower Body', 'Lower body strength', 'shoe-prints', 'badge-sport-weighttraining', 171),
            ('WeightTraining', 'Full Body', 'Full body session', 'person', 'badge-sport-weighttraining', 172),
            ('WeightTraining', 'Powerlifting', 'Squat, bench, deadlift', 'weight-hanging', 'badge-sport-weighttraining', 173),
            ('WeightTraining', 'Bodybuilding', 'Hypertrophy training', 'dumbbell', 'badge-sport-weighttraining', 174),
        ]

        added_count = 0
        for base_type, name, desc, icon, color, order in new_extended_types:
            try:
                cursor.execute('''
                    INSERT INTO extended_activity_types
                    (base_sport_type, custom_name, description, icon_override, color_class, display_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (base_type, name, desc, icon, color, order))
                added_count += 1
            except sqlite3.IntegrityError:
                # Skip if already exists
                pass

        print(f"✓ Added {added_count} new extended types")

        # Commit all changes
        conn.commit()

        # Verification
        print("\n" + "="*60)
        print("MIGRATION COMPLETED - VERIFYING RESULTS")
        print("="*60 + "\n")

        cursor.execute('SELECT COUNT(*) FROM standard_activity_types')
        std_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM extended_activity_types')
        ext_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM activities')
        act_count = cursor.fetchone()[0]

        print(f"Standard activity types: {std_count}")
        print(f"Extended activity types: {ext_count}")
        print(f"Activities preserved: {act_count}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    """Main execution"""
    # Determine database path
    db_path = os.environ.get('DATABASE_PATH', 'instance/activities.db')

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print(f"   Set DATABASE_PATH environment variable or ensure database exists")
        sys.exit(1)

    print("="*60)
    print("PRODUCTION DATABASE MIGRATION")
    print("Standard Activity Types + FK Constraints")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print()

    # Integrity check
    print("Running pre-migration integrity check...")
    if not verify_integrity(db_path):
        print("❌ Database failed integrity check!")
        sys.exit(1)
    print("✓ Database integrity OK")

    # Show current state
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM activities')
    activity_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT sport_type) FROM activities')
    sport_type_count = cursor.fetchone()[0]
    conn.close()

    print(f"\nCurrent state:")
    print(f"  Activities: {activity_count}")
    print(f"  Unique sport types: {sport_type_count}")

    # Confirmation
    print("\n" + "⚠️ "*20)
    print("This migration will:")
    print("  1. Create standard_activity_types table")
    print("  2. Add FK constraints to activities.sport_type")
    print("  3. Add FK constraints to extended_activity_types.base_sport_type")
    print("  4. Add 70+ new extended activity types")
    print("\nA backup will be created automatically.")
    print("⚠️ "*20 + "\n")

    response = input("Proceed with migration? (type 'yes' to continue): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        sys.exit(0)

    # Create backup
    print("\nCreating backup...")
    backup_path = backup_database(db_path)

    # Verify backup
    if not verify_integrity(backup_path):
        print("❌ Backup failed integrity check!")
        sys.exit(1)

    # Run migration
    try:
        success = migrate_database(db_path)

        if success:
            # Final integrity check
            print("\nRunning post-migration integrity check...")
            if not verify_integrity(db_path):
                print("❌ Database failed post-migration integrity check!")
                print(f"   Restore from: {backup_path}")
                sys.exit(1)
            print("✓ Database integrity OK")

            print("\n" + "="*60)
            print("✅ MIGRATION SUCCESSFUL!")
            print("="*60)
            print(f"\nBackup location: {backup_path}")
            print(f"Rollback command: mv {backup_path} {db_path}")
            print("\nYou can now restart your application.")

    except Exception as e:
        print("\n" + "="*60)
        print("❌ MIGRATION FAILED!")
        print("="*60)
        print(f"\nError: {e}")
        print(f"\nRestoring from backup: {backup_path}")
        shutil.copy2(backup_path, db_path)
        print("✓ Database restored from backup")
        print("\nPlease investigate the error before retrying.")
        sys.exit(1)

if __name__ == '__main__':
    main()
