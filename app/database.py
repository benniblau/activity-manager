import sqlite3
import os
from datetime import datetime
import json
from flask import g, current_app


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


def dict_to_db_values(data):
    """Convert dictionary to database-friendly values (serialize JSON fields)"""
    json_fields = ['start_latlng', 'end_latlng', 'map', 'segment_efforts',
                   'splits_metric', 'splits_standard', 'laps', 'best_efforts', 'gear']

    result = {}
    for key, value in data.items():
        if key in json_fields and value is not None:
            result[key] = json.dumps(value)
        elif isinstance(value, bool):
            result[key] = 1 if value else 0
        else:
            result[key] = value

    return result


def db_row_to_dict(row):
    """Convert database row to dictionary with JSON fields parsed"""
    if row is None:
        return None

    json_fields = ['start_latlng', 'end_latlng', 'map', 'segment_efforts',
                   'splits_metric', 'splits_standard', 'laps', 'best_efforts', 'gear']

    result = dict(row)

    # Parse JSON fields
    for field in json_fields:
        if field in result and result[field]:
            try:
                result[field] = json.loads(result[field])
            except:
                pass

    # Convert boolean fields
    bool_fields = ['trainer', 'commute', 'manual', 'private', 'flagged',
                   'has_heartrate', 'has_kudoed', 'segment_leaderboard_opt_out',
                   'leaderboard_opt_out', 'device_watts']
    for field in bool_fields:
        if field in result and result[field] is not None:
            result[field] = bool(result[field])

    return result
