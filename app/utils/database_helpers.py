"""Database utility functions for data transformation and formatting"""

import json
from datetime import datetime


def dict_to_db_values(data):
    """Convert dictionary to database-friendly values (serialize JSON fields)

    Args:
        data: Dictionary with potentially complex values

    Returns:
        Dictionary with JSON-serialized fields and boolean conversions
    """
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
    """Convert database row to dictionary with JSON fields parsed

    Args:
        row: SQLite Row object

    Returns:
        Dictionary with parsed JSON fields and boolean conversions, or None if row is None
    """
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
            except Exception:
                pass

    # Convert boolean fields
    bool_fields = ['trainer', 'commute', 'manual', 'private', 'flagged',
                   'has_heartrate', 'has_kudoed', 'segment_leaderboard_opt_out',
                   'leaderboard_opt_out', 'device_watts', 'is_active', 'is_official']

    for field in bool_fields:
        if field in result and result[field] is not None:
            result[field] = bool(result[field])

    return result


def parse_datetime(value):
    """Parse datetime from various string formats

    Args:
        value: String datetime in ISO format or datetime object

    Returns:
        datetime object or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    # Try ISO format
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        pass

    # Try common formats
    formats = [
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue

    return None


def format_duration(seconds):
    """Format seconds to human-readable duration

    Args:
        seconds: Number of seconds (int or float)

    Returns:
        String like "1h 23m 45s" or "23m 45s" or "45s"
    """
    if seconds is None:
        return "0s"

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_distance(meters):
    """Format meters to human-readable distance

    Args:
        meters: Distance in meters (int or float)

    Returns:
        String like "5.2 km" or "342 m"
    """
    if meters is None:
        return "0 m"

    if meters >= 1000:
        km = meters / 1000
        return f"{km:.1f} km"
    else:
        return f"{int(meters)} m"


def format_elevation(meters):
    """Format elevation gain in meters

    Args:
        meters: Elevation in meters (int or float)

    Returns:
        String like "342 m"
    """
    if meters is None:
        return "0 m"

    return f"{int(meters)} m"


def format_pace(seconds_per_km):
    """Format pace in min/km

    Args:
        seconds_per_km: Seconds per kilometer

    Returns:
        String like "5:23 min/km"
    """
    if seconds_per_km is None or seconds_per_km == 0:
        return "0:00 min/km"

    minutes = int(seconds_per_km // 60)
    seconds = int(seconds_per_km % 60)

    return f"{minutes}:{seconds:02d} min/km"


def format_speed(meters_per_second):
    """Format speed in km/h

    Args:
        meters_per_second: Speed in m/s

    Returns:
        String like "15.2 km/h"
    """
    if meters_per_second is None or meters_per_second == 0:
        return "0.0 km/h"

    kmh = meters_per_second * 3.6
    return f"{kmh:.1f} km/h"


def execute_query(db, query, params=None, fetch_one=False):
    """Execute a database query with optional logging

    Args:
        db: Database connection
        query: SQL query string
        params: Query parameters (tuple or list)
        fetch_one: If True, return single row; if False, return all rows

    Returns:
        Single row dict, list of row dicts, or None
    """
    if params is None:
        params = ()

    cursor = db.execute(query, params)

    if fetch_one:
        row = cursor.fetchone()
        return db_row_to_dict(row)
    else:
        rows = cursor.fetchall()
        return [db_row_to_dict(row) for row in rows]
