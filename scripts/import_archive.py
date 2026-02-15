"""Import Strava archive data into the Activity Manager database.

Usage:
    python scripts/import_archive.py [--archive-dir ./archive] [--data-dir ./data]

Reads activities.csv from the Strava data export, extends existing activities
with archive-only fields (weather, grades, etc.), and copies FIT files and media.
"""

import csv
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# Add project root to path so we can import app modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ---------- Configuration ----------

ARCHIVE_DIR = os.path.join(PROJECT_ROOT, 'archive')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(PROJECT_ROOT, 'activities.db')

# German sport type → English Strava sport type
SPORT_TYPE_MAP = {
    'Lauf': 'Run',
    'Radfahrt': 'Ride',
    'Wandern': 'Hike',
    'Spaziergang': 'Walk',
    'Gewichtstraining': 'WeightTraining',
    'Training': 'Workout',
    'Schwimmen': 'Swim',
    'Ski Alpin': 'AlpineSki',
    'Skitouren': 'BackcountrySki',
    'Snowboarden': 'Snowboard',
    'Crossfit': 'Crossfit',
    'Virtuelle Radfahrt': 'VirtualRide',
    'Virtueller Lauf': 'VirtualRun',
    'Mountainbikefahrt': 'MountainBikeRide',
    'Gravelfahrt': 'GravelRide',
    'E-Bike-Fahrt': 'EBikeRide',
    'Traillauf': 'TrailRun',
    'Yoga': 'Yoga',
    'HIIT': 'HIIT',
    'Rudern': 'Rowing',
    'Kanufahrt': 'Canoe',
    'Kajakfahren': 'Kayaking',
    'Eislaufen': 'IceSkate',
    'Langlauf': 'NordicSki',
    'Schneeschuhwanderung': 'Snowshoe',
    'Ellipsentrainer': 'Elliptical',
    'Tennis': 'Tennis',
    'Pickleball': 'Pickleball',
    'Klettern': 'RockClimbing',
    'Inlineskaten': 'InlineSkate',
    'Golf': 'Golf',
    'Skateboard': 'Skateboard',
    'Fußball': 'Soccer',
    'Pilates': 'Pilates',
    'Stand Up Paddling': 'StandUpPaddling',
    'Surfen': 'Surfing',
    'Windsurfen': 'Windsurf',
    'Kitesurfen': 'Kitesurf',
    'Segeln': 'Sail',
}

# Index-based column mapping (because some headers are duplicated).
# Maps CSV column index → (db_column_name, parse_type)
# parse_type: 'int', 'float', 'str', 'bool', 'german_float', 'datetime', 'weather_*', 'skip'
COLUMN_MAP = {
    0: ('id', 'int'),                          # Aktivitäts-ID
    1: ('_date_raw', 'str'),                   # Aktivitätsdatum (DD.MM.YYYY, HH:MM:SS)
    2: ('name', 'str'),                        # Name der Aktivität
    3: ('_sport_type_de', 'str'),              # Aktivitätsart (German)
    4: ('description', 'str'),                 # Aktivitätsbeschreibung
    # 5: summary elapsed time (skip — use index 15)
    # 6: summary distance in km (skip — use index 17 in meters)
    # 7: summary max HR (skip — use index 30)
    # 8: summary relative effort (skip — use index 37)
    # 9: summary commute text (skip — use index 50)
    12: ('_fit_filename', 'str'),              # Dateiname
    13: ('athlete_weight', 'float'),           # Sportlergewicht
    14: ('bike_weight', 'float'),              # Fahrradgewicht
    15: ('elapsed_time', 'float'),             # Verstrichene Zeit (detailed)
    16: ('moving_time', 'float'),              # Bewegungszeit
    17: ('distance', 'float'),                 # Distanz (meters, detailed)
    18: ('max_speed', 'float'),                # Höchstgeschw.
    19: ('average_speed', 'float'),            # Durchschnittliche Geschwindigkeit
    20: ('total_elevation_gain', 'float'),     # Höhenzunahme
    21: ('elevation_loss', 'float'),           # Höhenunterschied
    22: ('elev_low', 'float'),                 # Min. Höhe
    23: ('elev_high', 'float'),                # Max. Höhe
    24: ('max_grade', 'float'),                # Max. Steigung
    25: ('average_grade', 'float'),            # Durchschnittliche Steigung
    26: ('average_positive_grade', 'float'),   # Durchschnittliche positive Steigung
    27: ('average_negative_grade', 'float'),   # Durchschnittliche negative Steigung
    28: ('max_cadence', 'float'),              # Max. Tritt-/Schrittfrequenz
    29: ('average_cadence', 'float'),          # Durchschnittliche Trittfrequenz
    30: ('max_heartrate', 'float'),            # Max. Herzfrequenz (detailed)
    31: ('average_heartrate', 'float'),        # Durchschnittliche Herzfrequenz
    # 32: Max. Watt (skip — rarely populated)
    33: ('average_watts', 'float'),            # Durchschnittliche Watt
    34: ('calories', 'float'),                 # Kalorien
    # 35: Max. Temperatur (skip — rarely populated)
    36: ('average_temp', 'float'),             # Durchschnittliche Temperatur
    37: ('relative_effort', 'float'),          # Relative Leistung (detailed)
    38: ('total_work', 'float'),               # Gesamtarbeit
    # 39: Anzahl Läufe — rarely used
    40: ('uphill_time', 'float'),              # Bergaufzeit
    41: ('downhill_time', 'float'),            # Bergabzeit
    42: ('other_time', 'float'),               # Andere Zeit
    43: ('perceived_exertion', 'float'),       # Gefühlte Anstrengung
    # 44: Art — skip (redundant with sport_type)
    # 45: Startzeit — skip (we derive from date)
    46: ('weighted_average_watts', 'float'),   # Gewichtete durchschnittliche Leistung
    47: ('_power_number', 'float'),            # Leistungszahl (not in DB — skip or use as device_watts proxy)
    48: ('prefer_perceived_exertion', 'float'),  # Gefühlte Anstrengung verwenden
    49: ('perceived_relative_effort', 'float'),  # Gefühlte relative Leistung
    50: ('commute', 'float'),                  # Pendeln (detailed, numeric)
    51: ('total_weight_lifted', 'float'),      # Insgesamt gestemmtes Gewicht
    52: ('from_upload', 'float'),              # Von Upload
    53: ('grade_adjusted_distance', 'float'),  # Auf Steigung angepasste Distanz
    # Weather fields → packed into JSON
    54: ('_weather_observation_time', 'float'),
    55: ('_weather_condition', 'float'),
    56: ('_weather_temperature', 'float'),
    57: ('_weather_apparent_temp', 'float'),
    58: ('_weather_dewpoint', 'float'),
    59: ('_weather_humidity', 'float'),
    60: ('_weather_pressure', 'float'),
    61: ('_weather_wind_speed', 'float'),
    62: ('_weather_wind_gust', 'float'),
    63: ('_weather_wind_direction', 'float'),
    64: ('_weather_precipitation_intensity', 'float'),
    65: ('_weather_sunrise', 'float'),
    66: ('_weather_sunset', 'float'),
    67: ('_weather_moon_phase', 'float'),
    # 68: Fahrrad — skip (gear handled separately)
    69: ('_gear_name', 'str'),                 # Ausrüstung
    70: ('_weather_precipitation_probability', 'float'),
    71: ('_weather_precipitation_type', 'float'),
    72: ('_weather_cloud_cover', 'float'),
    73: ('_weather_visibility', 'float'),
    74: ('_weather_uv_index', 'float'),
    75: ('_weather_ozone', 'float'),
    # 76: Sprunganzahl — rarely used
    # 77: Schwierigkeit insgesamt — rarely used
    # 78: Durchschnittlicher Flow — rarely used
    79: ('flagged', 'float'),                  # Markiert
    80: ('average_elapsed_speed', 'float'),    # Durchschnittsgeschwindigkeit im Aufzeichnungszeitraum
    81: ('gravel_distance', 'float'),          # Auf Schotter zurückgelegte Distanz
    # 82: Neu getestete Distanz — skip
    # 83: Neu getestete Schotterdistanz — skip
    # 84: Aktivitätsanzahl — skip
    85: ('total_steps', 'float'),              # Schritte insgesamt
    86: ('carbon_saved', 'float'),             # Eingesparte CO₂-Emissionen
    87: ('pool_length', 'float'),              # Pool-Länge
    88: ('training_load', 'float'),            # Trainingsbelastung
    89: ('intensity', 'float'),                # Intensität
    90: ('average_grade_adjusted_pace', 'float'),  # Durchschnittliches auf Steigung angepasstes Tempo
    91: ('stopwatch_time', 'float'),           # Stoppuhr-Zeit
    92: ('total_cycles', 'float'),             # Zyklen gesamt
    # 93: Regeneration — rarely used
    94: ('with_pet', 'float'),                 # Mit Haustier
    95: ('race', 'float'),                     # Wettbewerb
    96: ('long_run', 'float'),                 # Langer Lauf
    97: ('charity', 'float'),                  # Für einen guten Zweck
    98: ('with_child', 'float'),               # Mit Kind
    # 99: Abfahrtsdistanz — skip
    100: ('_media', 'str'),                    # Medien
}

# Weather field keys (internal name → JSON key)
WEATHER_FIELDS = {
    '_weather_observation_time': 'observation_time',
    '_weather_condition': 'condition',
    '_weather_temperature': 'temperature',
    '_weather_apparent_temp': 'apparent_temp',
    '_weather_dewpoint': 'dewpoint',
    '_weather_humidity': 'humidity',
    '_weather_pressure': 'pressure',
    '_weather_wind_speed': 'wind_speed',
    '_weather_wind_gust': 'wind_gust',
    '_weather_wind_direction': 'wind_direction',
    '_weather_precipitation_intensity': 'precipitation_intensity',
    '_weather_sunrise': 'sunrise',
    '_weather_sunset': 'sunset',
    '_weather_moon_phase': 'moon_phase',
    '_weather_precipitation_probability': 'precipitation_probability',
    '_weather_precipitation_type': 'precipitation_type',
    '_weather_cloud_cover': 'cloud_cover',
    '_weather_visibility': 'visibility',
    '_weather_uv_index': 'uv_index',
    '_weather_ozone': 'ozone',
}


# ---------- Helpers ----------

def parse_value(raw, parse_type):
    """Parse a raw CSV string into the appropriate Python type."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    if parse_type == 'str':
        return raw
    elif parse_type == 'int':
        # Handle German format with dots as thousands separators
        raw = raw.replace('.', '').replace(',', '.')
        return int(float(raw))
    elif parse_type == 'float':
        raw = raw.replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            return None
    elif parse_type == 'german_float':
        raw = raw.replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            return None
    elif parse_type == 'bool':
        return raw.lower() in ('true', '1', 'yes')
    return raw


def parse_date(raw):
    """Convert 'DD.MM.YYYY, HH:MM:SS' → ISO 8601 'YYYY-MM-DDTHH:MM:SS'"""
    if not raw or not raw.strip():
        return None, None
    raw = raw.strip()
    try:
        dt = datetime.strptime(raw, '%d.%m.%Y, %H:%M:%S')
        iso = dt.strftime('%Y-%m-%dT%H:%M:%S')
        day_date = dt.strftime('%Y-%m-%d')
        return iso, day_date
    except ValueError:
        # Try without time
        try:
            dt = datetime.strptime(raw, '%d.%m.%Y')
            iso = dt.strftime('%Y-%m-%dT00:00:00')
            day_date = dt.strftime('%Y-%m-%d')
            return iso, day_date
        except ValueError:
            return None, None


def build_weather_json(parsed):
    """Build weather JSON blob from parsed weather fields."""
    weather = {}
    for internal_key, json_key in WEATHER_FIELDS.items():
        val = parsed.get(internal_key)
        if val is not None:
            weather[json_key] = val
    return json.dumps(weather) if weather else None


def map_sport_type(german_type):
    """Map German sport type to English Strava sport type."""
    return SPORT_TYPE_MAP.get(german_type, german_type)


# ---------- Schema migration ----------

def _ensure_archive_columns(db):
    """Add archive-specific columns if they don't exist yet."""
    cursor = db.execute("PRAGMA table_info(activities)")
    existing = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ('max_cadence', 'REAL'), ('relative_effort', 'REAL'),
        ('total_work', 'REAL'), ('training_load', 'REAL'),
        ('intensity', 'REAL'), ('perceived_exertion', 'REAL'),
        ('perceived_relative_effort', 'REAL'), ('prefer_perceived_exertion', 'INTEGER'),
        ('elevation_loss', 'REAL'), ('max_grade', 'REAL'),
        ('average_grade', 'REAL'), ('average_positive_grade', 'REAL'),
        ('average_negative_grade', 'REAL'), ('grade_adjusted_distance', 'REAL'),
        ('gravel_distance', 'REAL'), ('average_grade_adjusted_pace', 'REAL'),
        ('average_elapsed_speed', 'REAL'), ('athlete_weight', 'REAL'),
        ('bike_weight', 'REAL'), ('total_steps', 'INTEGER'),
        ('total_weight_lifted', 'REAL'), ('pool_length', 'REAL'),
        ('total_cycles', 'INTEGER'), ('uphill_time', 'REAL'),
        ('downhill_time', 'REAL'), ('other_time', 'REAL'),
        ('stopwatch_time', 'REAL'), ('weather', 'TEXT'),
        ('carbon_saved', 'REAL'), ('from_upload', 'INTEGER'),
        ('with_pet', 'INTEGER'), ('race', 'INTEGER'),
        ('long_run', 'INTEGER'), ('charity', 'INTEGER'),
        ('with_child', 'INTEGER'), ('fit_file_path', 'TEXT'),
    ]

    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing:
            db.execute(f'ALTER TABLE activities ADD COLUMN {col_name} {col_type}')
            added += 1

    # Ensure activity_media table exists
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

    db.commit()
    if added:
        print(f"Schema migration: added {added} new columns to activities table")


# ---------- Main import logic ----------

def import_archive(archive_dir=None, data_dir=None, db_path=None):
    """Import Strava archive into the database."""
    archive_dir = archive_dir or ARCHIVE_DIR
    data_dir = data_dir or DATA_DIR
    db_path = db_path or DB_PATH

    csv_path = os.path.join(archive_dir, 'activities.csv')
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found")
        return

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        print("Start the app first to initialize the database, then run this script.")
        return

    # Create data directories
    fit_dir = os.path.join(data_dir, 'fit_files')
    media_dir = os.path.join(data_dir, 'media')
    os.makedirs(fit_dir, exist_ok=True)
    os.makedirs(media_dir, exist_ok=True)

    # Backup database
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"Database backed up to {backup_path}")

    # Connect to database
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    # Run schema migration to ensure archive columns exist
    _ensure_archive_columns(db)

    # Read CSV
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)

    print(f"Found {len(rows)} activities in CSV")

    created = 0
    updated = 0
    skipped = 0
    errors = []
    media_count = 0
    fit_count = 0

    for row_num, row in enumerate(rows, 1):
        try:
            # Parse all mapped columns
            parsed = {}
            for idx, (col_name, parse_type) in COLUMN_MAP.items():
                if idx < len(row):
                    parsed[col_name] = parse_value(row[idx], parse_type)

            activity_id = parsed.get('id')
            if not activity_id:
                skipped += 1
                continue

            # Parse date
            date_raw = parsed.get('_date_raw', '')
            start_date_local, day_date = parse_date(date_raw)
            if not start_date_local:
                print(f"  WARNING: Skipping activity {activity_id} — invalid date: {date_raw}")
                skipped += 1
                continue

            # Map sport type
            sport_type_de = parsed.get('_sport_type_de', 'Workout')
            sport_type = map_sport_type(sport_type_de)

            # Ensure sport type exists in standard_activity_types
            cursor = db.execute(
                'SELECT COUNT(*) FROM standard_activity_types WHERE name = ?',
                (sport_type,)
            )
            if cursor.fetchone()[0] == 0:
                db.execute('''
                    INSERT INTO standard_activity_types
                    (name, category, display_name, icon, color, is_official, display_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (sport_type, 'Other', sport_type, 'circle-question', 'badge-other', 0, 999))

            # Build weather JSON
            weather_json = build_weather_json(parsed)

            # Build activity record
            activity = {
                'id': int(activity_id),
                'name': parsed.get('name', 'Untitled'),
                'description': parsed.get('description'),
                'sport_type': sport_type,
                'type': sport_type,
                'start_date': start_date_local,
                'start_date_local': start_date_local,
                'day_date': day_date,
                'elapsed_time': int(parsed.get('elapsed_time') or parsed.get('moving_time') or 0),
                'moving_time': int(parsed['moving_time']) if parsed.get('moving_time') else None,
                'distance': parsed.get('distance'),
                'total_elevation_gain': parsed.get('total_elevation_gain'),
                'elevation_loss': parsed.get('elevation_loss'),
                'elev_high': parsed.get('elev_high'),
                'elev_low': parsed.get('elev_low'),
                'max_speed': parsed.get('max_speed'),
                'average_speed': parsed.get('average_speed'),
                'max_cadence': parsed.get('max_cadence'),
                'average_cadence': parsed.get('average_cadence'),
                'max_heartrate': int(parsed['max_heartrate']) if parsed.get('max_heartrate') else None,
                'average_heartrate': parsed.get('average_heartrate'),
                'has_heartrate': 1 if parsed.get('average_heartrate') else 0,
                'average_watts': parsed.get('average_watts'),
                'weighted_average_watts': parsed.get('weighted_average_watts'),
                'calories': parsed.get('calories'),
                'average_temp': int(parsed['average_temp']) if parsed.get('average_temp') else None,
                'commute': int(parsed['commute']) if parsed.get('commute') else 0,
                'flagged': int(parsed['flagged']) if parsed.get('flagged') else 0,
                'relative_effort': parsed.get('relative_effort'),
                'total_work': parsed.get('total_work'),
                'training_load': parsed.get('training_load'),
                'intensity': parsed.get('intensity'),
                'perceived_exertion': parsed.get('perceived_exertion'),
                'perceived_relative_effort': parsed.get('perceived_relative_effort'),
                'prefer_perceived_exertion': int(parsed['prefer_perceived_exertion']) if parsed.get('prefer_perceived_exertion') else None,
                'max_grade': parsed.get('max_grade'),
                'average_grade': parsed.get('average_grade'),
                'average_positive_grade': parsed.get('average_positive_grade'),
                'average_negative_grade': parsed.get('average_negative_grade'),
                'grade_adjusted_distance': parsed.get('grade_adjusted_distance'),
                'gravel_distance': parsed.get('gravel_distance'),
                'average_grade_adjusted_pace': parsed.get('average_grade_adjusted_pace'),
                'average_elapsed_speed': parsed.get('average_elapsed_speed'),
                'athlete_weight': parsed.get('athlete_weight'),
                'bike_weight': parsed.get('bike_weight'),
                'total_steps': int(parsed['total_steps']) if parsed.get('total_steps') else None,
                'total_weight_lifted': parsed.get('total_weight_lifted'),
                'pool_length': parsed.get('pool_length'),
                'total_cycles': int(parsed['total_cycles']) if parsed.get('total_cycles') else None,
                'uphill_time': parsed.get('uphill_time'),
                'downhill_time': parsed.get('downhill_time'),
                'other_time': parsed.get('other_time'),
                'stopwatch_time': parsed.get('stopwatch_time'),
                'carbon_saved': parsed.get('carbon_saved'),
                'from_upload': int(parsed['from_upload']) if parsed.get('from_upload') else None,
                'with_pet': int(parsed['with_pet']) if parsed.get('with_pet') else None,
                'race': int(parsed['race']) if parsed.get('race') else None,
                'long_run': int(parsed['long_run']) if parsed.get('long_run') else None,
                'charity': int(parsed['charity']) if parsed.get('charity') else None,
                'with_child': int(parsed['with_child']) if parsed.get('with_child') else None,
                'weather': weather_json,
            }

            # Handle FIT file
            fit_filename = parsed.get('_fit_filename')
            if fit_filename:
                src_fit = os.path.join(archive_dir, fit_filename)
                if os.path.exists(src_fit):
                    fit_basename = os.path.basename(fit_filename)
                    dst_fit = os.path.join(fit_dir, fit_basename)
                    if not os.path.exists(dst_fit):
                        shutil.copy2(src_fit, dst_fit)
                        fit_count += 1
                    activity['fit_file_path'] = fit_basename

            # Remove None values
            activity = {k: v for k, v in activity.items() if v is not None}

            # Check if activity exists
            existing = db.execute('SELECT id FROM activities WHERE id = ?', (activity['id'],)).fetchone()

            if existing:
                # Merge archive fields into existing record without overwriting
                # user annotations (feelings, coach comments, extended_type_id)
                preserve_fields = {
                    'feeling_before_text', 'feeling_before_pain',
                    'feeling_during_text', 'feeling_during_pain',
                    'feeling_after_text', 'feeling_after_pain',
                    'coach_comment', 'extended_type_id',
                }

                # Get existing data to check what's already set
                existing_row = db.execute('SELECT * FROM activities WHERE id = ?', (activity['id'],)).fetchone()
                existing_dict = dict(existing_row)

                # Only update fields that are NULL in existing record (don't overwrite)
                # Exception: always update archive-only fields that existing records wouldn't have
                archive_only_fields = {
                    'weather', 'relative_effort', 'training_load', 'intensity',
                    'perceived_exertion', 'perceived_relative_effort', 'prefer_perceived_exertion',
                    'elevation_loss', 'max_grade', 'average_grade', 'average_positive_grade',
                    'average_negative_grade', 'grade_adjusted_distance', 'gravel_distance',
                    'average_grade_adjusted_pace', 'average_elapsed_speed',
                    'athlete_weight', 'bike_weight', 'total_steps', 'total_weight_lifted',
                    'pool_length', 'total_cycles', 'uphill_time', 'downhill_time',
                    'other_time', 'stopwatch_time', 'carbon_saved', 'from_upload',
                    'with_pet', 'race', 'long_run', 'charity', 'with_child',
                    'fit_file_path', 'max_cadence',
                }

                update_fields = {}
                for key, val in activity.items():
                    if key == 'id':
                        continue
                    if key in preserve_fields:
                        continue
                    if key in archive_only_fields:
                        update_fields[key] = val
                    elif existing_dict.get(key) is None:
                        update_fields[key] = val

                if update_fields:
                    update_fields['updated_at'] = datetime.now().isoformat()
                    set_clause = ', '.join(f'{k} = ?' for k in update_fields)
                    values = list(update_fields.values()) + [activity['id']]
                    db.execute(f'UPDATE activities SET {set_clause} WHERE id = ?', values)
                    updated += 1
                else:
                    skipped += 1
            else:
                # Insert new activity
                activity['created_at'] = datetime.now().isoformat()
                activity['updated_at'] = activity['created_at']

                columns = ', '.join(activity.keys())
                placeholders = ', '.join(['?'] * len(activity))
                db.execute(
                    f'INSERT INTO activities ({columns}) VALUES ({placeholders})',
                    list(activity.values())
                )
                created += 1

            # Ensure day entry exists
            day_exists = db.execute('SELECT date FROM days WHERE date = ?', (day_date,)).fetchone()
            if not day_exists:
                db.execute('INSERT INTO days (date) VALUES (?)', (day_date,))

            # Handle media
            media_str = parsed.get('_media', '')
            if media_str:
                media_files = media_str.split('|')
                for sort_idx, media_path in enumerate(media_files):
                    media_path = media_path.strip()
                    if not media_path:
                        continue

                    # Copy media file
                    src_media = os.path.join(archive_dir, media_path)
                    media_basename = os.path.basename(media_path)
                    dst_media = os.path.join(media_dir, media_basename)

                    if os.path.exists(src_media) and not os.path.exists(dst_media):
                        shutil.copy2(src_media, dst_media)

                    # Insert media record (check for duplicates)
                    existing_media = db.execute(
                        'SELECT id FROM activity_media WHERE activity_id = ? AND file_path = ?',
                        (activity['id'], media_basename)
                    ).fetchone()

                    if not existing_media:
                        db.execute(
                            'INSERT INTO activity_media (activity_id, file_path, sort_order) VALUES (?, ?, ?)',
                            (activity['id'], media_basename, sort_idx)
                        )
                        media_count += 1

            # Progress
            if row_num % 100 == 0:
                db.commit()
                print(f"  Progress: {row_num}/{len(rows)} activities processed...")

        except Exception as e:
            errors.append((row_num, str(e)))
            if len(errors) <= 10:
                print(f"  ERROR row {row_num}: {e}")

    # Final commit
    db.commit()
    db.close()

    # Summary
    print(f"\n{'='*50}")
    print(f"Import complete!")
    print(f"  Created:  {created}")
    print(f"  Updated:  {updated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Media:    {media_count} records")
    print(f"  FIT files copied: {fit_count}")
    if errors:
        print(f"\nFirst errors:")
        for row_num, err in errors[:10]:
            print(f"  Row {row_num}: {err}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Import Strava archive')
    parser.add_argument('--archive-dir', default=ARCHIVE_DIR)
    parser.add_argument('--data-dir', default=DATA_DIR)
    parser.add_argument('--db-path', default=DB_PATH)
    args = parser.parse_args()

    import_archive(args.archive_dir, args.data_dir, args.db_path)
