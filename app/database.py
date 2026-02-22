import sqlite3
import os
from datetime import datetime
import json
import shutil
from flask import g, current_app
from app.utils.database_helpers import db_row_to_dict, dict_to_db_values


def get_db():
    """Get database connection from Flask g object"""
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row  # Return rows as dictionaries
    return g.db


def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def backup_database(db_path=None):
    """Create timestamped backup of the database

    Args:
        db_path: Path to database file. If None, uses current_app config.

    Returns:
        Path to the backup file
    """
    if db_path is None:
        db_path = current_app.config['DATABASE_PATH']

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def init_db():
    """Initialize the database with schema"""
    # Ensure the directory containing the database exists
    db_path = current_app.config['DATABASE_PATH']
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    db = get_db()

    # Create activities table with full Strava data model
    db.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY,
            resource_state INTEGER,
            external_id TEXT,
            upload_id INTEGER,

            -- Temporal Information
            start_date TEXT NOT NULL,
            start_date_local TEXT NOT NULL,
            timezone TEXT,
            utc_offset INTEGER,
            elapsed_time INTEGER NOT NULL,
            moving_time INTEGER,

            -- Location & Route (JSON fields)
            start_latlng TEXT,
            end_latlng TEXT,
            location_city TEXT,
            location_state TEXT,
            location_country TEXT,
            map TEXT,

            -- Descriptive Content
            name TEXT NOT NULL,
            description TEXT,
            type TEXT,
            sport_type TEXT NOT NULL,
            workout_type INTEGER,

            -- Performance Metrics
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

            -- Social & Engagement
            kudos_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            athlete_count INTEGER DEFAULT 1,
            photo_count INTEGER DEFAULT 0,
            total_photo_count INTEGER DEFAULT 0,
            pr_count INTEGER DEFAULT 0,
            achievement_count INTEGER DEFAULT 0,

            -- Flags & Settings
            trainer INTEGER DEFAULT 0,
            commute INTEGER DEFAULT 0,
            manual INTEGER DEFAULT 0,
            private INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            has_kudoed INTEGER DEFAULT 0,
            segment_leaderboard_opt_out INTEGER DEFAULT 0,
            leaderboard_opt_out INTEGER DEFAULT 0,

            -- Device Information
            device_name TEXT,

            -- Related Objects
            athlete_id INTEGER,
            gear_id TEXT,

            -- Complex nested data (JSON fields)
            segment_efforts TEXT,
            splits_metric TEXT,
            splits_standard TEXT,
            laps TEXT,
            best_efforts TEXT,
            gear TEXT,

            -- Timestamps
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            -- User Annotations (feelings before/during/after exercise)
            feeling_before_text TEXT,
            feeling_before_pain INTEGER,
            feeling_during_text TEXT,
            feeling_during_pain INTEGER,
            feeling_after_text TEXT,
            feeling_after_pain INTEGER,

            -- Coach comment for this activity
            coach_comment TEXT,

            -- Foreign key to days table
            day_date TEXT REFERENCES days(date)
        )
    ''')

    # Run migrations to add new columns to existing databases
    _migrate_add_feeling_columns(db)

    # Create days table for daily overall feelings
    db.execute('''
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY,
            feeling_text TEXT,
            feeling_pain INTEGER,
            coach_comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Run migration to add coach_comment columns
    _migrate_add_coach_comment_columns(db)

    # Run migration to add extended activity types and planned activities
    _migrate_add_extended_activity_types(db)

    # Run migration to add standard activity types with FK constraints
    _migrate_add_standard_activity_types(db)

    # Run migration to remove planned_activities table
    _migrate_remove_planned_activities(db)

    # Run migration to add planning feature
    _migrate_add_planning_feature(db)

    # Run migration to add archive-specific columns
    _migrate_add_archive_columns(db)

    # Run migration to add invitations table
    _migrate_add_invitations_table(db)

    # Create activity_media table for photos linked to activities
    db.execute('''
        CREATE TABLE IF NOT EXISTS activity_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            caption TEXT,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_activity_media_activity ON activity_media(activity_id)')

    # Create indexes for common queries
    db.execute('CREATE INDEX IF NOT EXISTS idx_start_date ON activities(start_date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_sport_type ON activities(sport_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_type ON activities(type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_day_date ON activities(day_date)')

    # Create strava_tokens table for persistent OAuth tokens
    db.execute('''
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

    # Create gear table for equipment (bikes, shoes, etc.)
    db.execute('''
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

    # Create index on gear_id for efficient joins
    db.execute('CREATE INDEX IF NOT EXISTS idx_gear_id ON activities(gear_id)')

    db.commit()


def _migrate_add_feeling_columns(db):
    """Add feeling annotation columns and day_date to existing databases"""
    # Get existing columns
    cursor = db.execute("PRAGMA table_info(activities)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define new columns to add
    new_columns = [
        ('feeling_before_text', 'TEXT'),
        ('feeling_before_pain', 'INTEGER'),
        ('feeling_during_text', 'TEXT'),
        ('feeling_during_pain', 'INTEGER'),
        ('feeling_after_text', 'TEXT'),
        ('feeling_after_pain', 'INTEGER'),
        ('day_date', 'TEXT REFERENCES days(date)'),
        ('coach_comment', 'TEXT'),
    ]

    # Add missing columns
    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            db.execute(f'ALTER TABLE activities ADD COLUMN {column_name} {column_type}')

    # Populate day_date for existing activities that don't have it set
    db.execute('''
        UPDATE activities
        SET day_date = substr(start_date_local, 1, 10)
        WHERE day_date IS NULL AND start_date_local IS NOT NULL
    ''')

    db.commit()


def _migrate_add_coach_comment_columns(db):
    """Add coach_comment column to days table for existing databases"""
    # Check if coach_comment column exists in days table
    cursor = db.execute("PRAGMA table_info(days)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if 'coach_comment' not in existing_columns:
        db.execute('ALTER TABLE days ADD COLUMN coach_comment TEXT')
        db.commit()


def _migrate_add_extended_activity_types(db):
    """Add extended activity types and planned activities support"""

    # 1. Create extended_activity_types table
    db.execute('''
        CREATE TABLE IF NOT EXISTS extended_activity_types (
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
            CHECK (base_sport_type IS NOT NULL AND base_sport_type != '')
        )
    ''')

    db.execute('CREATE INDEX IF NOT EXISTS idx_extended_types_base ON extended_activity_types(base_sport_type)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_extended_types_active ON extended_activity_types(is_active)')

    # 2. Add extended_type_id to activities table (migration-safe)
    cursor = db.execute("PRAGMA table_info(activities)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if 'extended_type_id' not in existing_columns:
        db.execute('ALTER TABLE activities ADD COLUMN extended_type_id INTEGER REFERENCES extended_activity_types(id) ON DELETE SET NULL')
        db.execute('CREATE INDEX IF NOT EXISTS idx_activities_extended_type ON activities(extended_type_id)')

    # 4. Seed with common extended types (optional - only on first run)
    cursor = db.execute("SELECT COUNT(*) FROM extended_activity_types")
    if cursor.fetchone()[0] == 0:
        seed_types = [
            ('Run', 'Recovery Run', 'Easy pace recovery run', None, 'badge-recovery', 1),
            ('Run', 'Easy Run', 'Conversational pace easy run', None, 'badge-easy', 2),
            ('Run', 'Tempo Run', 'Comfortably hard sustained effort', None, 'badge-tempo', 3),
            ('Run', 'Interval Run', 'High-intensity interval training', None, 'badge-interval', 4),
            ('Run', 'Long Run', 'Extended duration endurance run', None, 'badge-long', 5),
            ('Ride', 'Zone 2 Ride', 'Aerobic base building ride', None, 'badge-zone2', 10),
            ('Ride', 'Threshold Ride', 'FTP/threshold interval work', None, 'badge-threshold', 11),
            ('Ride', 'Recovery Ride', 'Active recovery spin', None, 'badge-recovery', 12),
        ]

        for base, name, desc, icon, color, order in seed_types:
            db.execute('''
                INSERT INTO extended_activity_types
                (base_sport_type, custom_name, description, icon_override, color_class, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (base, name, desc, icon, color, order))

    db.commit()


def _migrate_add_standard_activity_types(db):
    """Add standard_activity_types table and FK constraints

    This is a comprehensive migration that:
    1. Creates standard_activity_types table with all 50+ Strava types
    2. Handles orphaned sport types from existing activities
    3. Recreates activities table with FK constraint to standard types
    4. Recreates extended_activity_types table with FK constraint
    5. Adds 70+ new extended types for trend sports
    """

    # Check if migration already completed (table exists AND has data)
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='standard_activity_types'"
    )
    if cursor.fetchone():
        # Table exists, check if it has data
        cursor = db.execute("SELECT COUNT(*) FROM standard_activity_types")
        count = cursor.fetchone()[0]
        if count > 0:
            # Migration already completed
            return
        # Table exists but is empty, drop it and recreate
        db.execute('DROP TABLE IF EXISTS standard_activity_types')

    # STEP 1: Create standard_activity_types table
    db.execute('''
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
    db.execute('CREATE INDEX idx_standard_types_category ON standard_activity_types(category)')

    # STEP 2: Populate standard types (all 50+ Strava sport types)
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

    db.executemany('''
        INSERT INTO standard_activity_types
        (name, category, display_name, icon, color, description, is_official, display_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', standard_types)

    # STEP 3: Handle orphaned sport types from existing activities
    cursor = db.execute('''
        SELECT DISTINCT sport_type FROM activities
        WHERE sport_type NOT IN (SELECT name FROM standard_activity_types)
        AND sport_type IS NOT NULL
    ''')
    orphaned = [row[0] for row in cursor.fetchall()]

    for sport_type in orphaned:
        db.execute('''
            INSERT INTO standard_activity_types
            (name, category, display_name, icon, color, is_official, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sport_type, 'Other', sport_type, 'circle-question', 'badge-other', 0, 999))

    # STEP 4: Recreate activities table with FK constraint
    # Check if activities table already has extended_type_id column
    cursor = db.execute("PRAGMA table_info(activities)")
    has_extended_type_id = any(col[1] == 'extended_type_id' for col in cursor.fetchall())

    db.execute('ALTER TABLE activities RENAME TO activities_old')

    # Build CREATE TABLE statement dynamically
    create_statement = '''
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
    '''
    db.execute(create_statement)

    # Copy data
    db.execute('INSERT INTO activities SELECT * FROM activities_old')

    # Drop old indexes if they exist (they may be associated with the old table)
    for index_name in ['idx_start_date', 'idx_sport_type', 'idx_type', 'idx_day_date', 'idx_gear_id', 'idx_activities_extended_type']:
        db.execute(f'DROP INDEX IF EXISTS {index_name}')

    # Recreate indexes
    db.execute('CREATE INDEX idx_start_date ON activities(start_date)')
    db.execute('CREATE INDEX idx_sport_type ON activities(sport_type)')
    db.execute('CREATE INDEX idx_type ON activities(type)')
    db.execute('CREATE INDEX idx_day_date ON activities(day_date)')
    db.execute('CREATE INDEX idx_gear_id ON activities(gear_id)')
    db.execute('CREATE INDEX idx_activities_extended_type ON activities(extended_type_id)')

    db.execute('DROP TABLE activities_old')

    # STEP 5: Recreate extended_activity_types table with FK constraint
    db.execute('ALTER TABLE extended_activity_types RENAME TO extended_activity_types_old')

    db.execute('''
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

    db.execute('INSERT INTO extended_activity_types SELECT * FROM extended_activity_types_old')

    # Drop old indexes if they exist
    db.execute('DROP INDEX IF EXISTS idx_extended_types_base')
    db.execute('DROP INDEX IF EXISTS idx_extended_types_active')

    db.execute('CREATE INDEX idx_extended_types_base ON extended_activity_types(base_sport_type)')
    db.execute('CREATE INDEX idx_extended_types_active ON extended_activity_types(is_active)')

    db.execute('DROP TABLE extended_activity_types_old')

    # STEP 6: Add new extended types (70+ types for trend sports)
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

    for base_type, name, desc, icon, color, order in new_extended_types:
        try:
            db.execute('''
                INSERT INTO extended_activity_types
                (base_sport_type, custom_name, description, icon_override, color_class, display_order)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (base_type, name, desc, icon, color, order))
        except Exception:
            # Skip if already exists (UNIQUE constraint on custom_name)
            pass

    db.commit()


def _migrate_remove_planned_activities(db):
    """Remove old planned_activities table if it has the legacy schema (no user_id column).

    The original table lacked user_id and other columns needed by the current planning
    feature. If the new schema is already in place, this migration is a no-op so that
    existing data is preserved across app restarts and deployments.
    """
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='planned_activities'"
    )
    if not cursor.fetchone():
        return  # table doesn't exist yet — nothing to do

    cursor = db.execute("PRAGMA table_info(planned_activities)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'user_id' not in columns:
        # Old schema without user_id — drop so _migrate_add_planning_feature can recreate
        db.execute('DROP TABLE planned_activities')
        db.commit()


def _migrate_add_planning_feature(db):
    """Add planned_activities table for training plan feature"""
    db.execute('''
        CREATE TABLE IF NOT EXISTS planned_activities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            day_date    TEXT NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            sport_type  TEXT REFERENCES standard_activity_types(name) ON DELETE SET NULL,
            extended_type_id INTEGER REFERENCES extended_activity_types(id) ON DELETE SET NULL,
            planned_distance REAL,
            planned_duration INTEGER,
            notes       TEXT,
            matched_activity_id INTEGER REFERENCES activities(id) ON DELETE SET NULL,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_planned_user_date ON planned_activities(user_id, day_date)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_planned_sort ON planned_activities(day_date, sort_order)')
    db.commit()


def _migrate_add_archive_columns(db):
    """Add columns for Strava archive import data (weather, grades, etc.)"""
    cursor = db.execute("PRAGMA table_info(activities)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        # Performance extras
        ('max_cadence', 'REAL'),
        ('relative_effort', 'REAL'),
        ('total_work', 'REAL'),
        ('training_load', 'REAL'),
        ('intensity', 'REAL'),
        ('perceived_exertion', 'REAL'),
        ('perceived_relative_effort', 'REAL'),
        ('prefer_perceived_exertion', 'INTEGER'),
        # Elevation extras
        ('elevation_loss', 'REAL'),
        ('max_grade', 'REAL'),
        ('average_grade', 'REAL'),
        ('average_positive_grade', 'REAL'),
        ('average_negative_grade', 'REAL'),
        # Distance extras
        ('grade_adjusted_distance', 'REAL'),
        ('gravel_distance', 'REAL'),
        ('average_grade_adjusted_pace', 'REAL'),
        ('average_elapsed_speed', 'REAL'),
        # Athlete/body
        ('athlete_weight', 'REAL'),
        ('bike_weight', 'REAL'),
        ('total_steps', 'INTEGER'),
        ('total_weight_lifted', 'REAL'),
        ('pool_length', 'REAL'),
        ('total_cycles', 'INTEGER'),
        # Timing extras
        ('uphill_time', 'REAL'),
        ('downhill_time', 'REAL'),
        ('other_time', 'REAL'),
        ('stopwatch_time', 'REAL'),
        # Weather (JSON blob)
        ('weather', 'TEXT'),
        # Tags/flags
        ('carbon_saved', 'REAL'),
        ('from_upload', 'INTEGER'),
        ('with_pet', 'INTEGER'),
        ('race', 'INTEGER'),
        ('long_run', 'INTEGER'),
        ('charity', 'INTEGER'),
        ('with_child', 'INTEGER'),
        # Linked files
        ('fit_file_path', 'TEXT'),
    ]

    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            db.execute(f'ALTER TABLE activities ADD COLUMN {column_name} {column_type}')

    db.commit()


def _migrate_add_invitations_table(db):
    """Add invitations table for token-based invitation-only registration"""
    db.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL UNIQUE,
            inviter_id INTEGER NOT NULL,
            invited_email TEXT NOT NULL,
            invited_role TEXT NOT NULL DEFAULT 'athlete'
                CHECK (invited_role IN ('athlete', 'coach')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'used', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            used_by_user_id INTEGER,
            FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_invitations_inviter ON invitations(inviter_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(invited_email)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_invitations_status ON invitations(status)')
    db.commit()


def get_extended_types(base_sport_type=None):
    """Fetch extended activity types, optionally filtered by base type"""
    db = get_db()

    if base_sport_type:
        cursor = db.execute('''
            SELECT * FROM extended_activity_types
            WHERE base_sport_type = ? AND is_active = 1
            ORDER BY display_order, custom_name
        ''', (base_sport_type,))
    else:
        cursor = db.execute('''
            SELECT * FROM extended_activity_types
            WHERE is_active = 1
            ORDER BY base_sport_type, display_order, custom_name
        ''')

    return [db_row_to_dict(row) for row in cursor.fetchall()]


def get_standard_activity_types(category=None, official_only=True):
    """Fetch standard activity types, optionally filtered by category

    Args:
        category: Filter by category ('Foot', 'Cycle', 'Water', 'Winter', 'Fitness', 'Racket', 'Other')
        official_only: If True, only return official Strava types (is_official=1)

    Returns:
        List of standard activity type dictionaries
    """
    db = get_db()

    # Check if table exists
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='standard_activity_types'"
    )
    if not cursor.fetchone():
        return []

    query = 'SELECT * FROM standard_activity_types WHERE 1=1'
    params = []

    if category:
        query += ' AND category = ?'
        params.append(category)

    if official_only:
        query += ' AND is_official = 1'

    query += ' ORDER BY display_order, display_name'

    cursor = db.execute(query, params)
    return [db_row_to_dict(row) for row in cursor.fetchall()]


def get_standard_types_by_category():
    """Get standard activity types grouped by category

    Returns:
        Dictionary mapping category names to lists of type dictionaries
    """
    from collections import defaultdict

    types_by_category = defaultdict(list)
    all_types = get_standard_activity_types(official_only=True)

    for sport_type in all_types:
        types_by_category[sport_type['category']].append(sport_type)

    return dict(types_by_category)


def validate_sport_type(sport_type):
    """Check if a sport_type value exists in standard_activity_types

    Args:
        sport_type: The sport_type string to validate

    Returns:
        True if valid, False otherwise
    """
    if not sport_type:
        return False

    db = get_db()

    # Check if table exists
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='standard_activity_types'"
    )
    if not cursor.fetchone():
        # If migration hasn't run yet, allow any sport_type
        return True

    cursor = db.execute(
        'SELECT COUNT(*) FROM standard_activity_types WHERE name = ?',
        (sport_type,)
    )
    return cursor.fetchone()[0] > 0


