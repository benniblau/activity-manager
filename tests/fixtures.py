"""Test data fixtures for activities and types"""

from datetime import datetime, timedelta


def get_sample_activity(activity_id=1, sport_type='Run', **overrides):
    """Get a sample activity dictionary

    Args:
        activity_id: Activity ID
        sport_type: Sport type
        **overrides: Override any default values

    Returns:
        Dictionary with activity data
    """
    base_date = datetime(2026, 1, 10, 8, 0, 0)

    activity = {
        'id': activity_id,
        'name': f'Morning {sport_type}',
        'sport_type': sport_type,
        'start_date': base_date.isoformat(),
        'start_date_local': base_date.isoformat(),
        'day_date': base_date.date().isoformat(),
        'timezone': 'Europe/Berlin',
        'elapsed_time': 3600,
        'moving_time': 3500,
        'distance': 10000.0,
        'total_elevation_gain': 100.0,
        'average_speed': 2.86,
        'max_speed': 4.2,
        'average_heartrate': 145.0,
        'max_heartrate': 165,
        'calories': 650.0,
        'trainer': False,
        'commute': False,
        'manual': False,
        'description': f'Great {sport_type.lower()} workout',
        'extended_type_id': None
    }

    activity.update(overrides)
    return activity


def get_sample_extended_type(type_id=1, base_sport_type='Run', custom_name='Easy Run', **overrides):
    """Get a sample extended activity type

    Args:
        type_id: Type ID
        base_sport_type: Base sport type
        custom_name: Custom type name
        **overrides: Override any default values

    Returns:
        Dictionary with extended type data
    """
    ext_type = {
        'id': type_id,
        'base_sport_type': base_sport_type,
        'custom_name': custom_name,
        'description': f'{custom_name} type',
        'icon_override': 'person-running',
        'color_class': 'badge-sport-run',
        'display_order': 0,
        'is_active': True
    }

    ext_type.update(overrides)
    return ext_type


def get_sample_standard_type(name='Run', category='Foot', **overrides):
    """Get a sample standard activity type

    Args:
        name: Type name
        category: Category name
        **overrides: Override any default values

    Returns:
        Dictionary with standard type data
    """
    standard_type = {
        'name': name,
        'category': category,
        'display_name': name,
        'icon': 'person-running',
        'color': 'badge-sport-run',
        'description': f'{name} activity',
        'is_official': True,
        'display_order': 0
    }

    standard_type.update(overrides)
    return standard_type


def get_sample_strava_activity(activity_id=123456789):
    """Get a sample Strava API activity response

    Args:
        activity_id: Strava activity ID

    Returns:
        Mock Strava activity object (as dict)
    """
    from datetime import timezone

    base_date = datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc)

    return {
        'id': activity_id,
        'name': 'Morning Run',
        'type': 'Run',
        'sport_type': 'Run',
        'start_date': base_date.isoformat(),
        'start_date_local': base_date.replace(tzinfo=None).isoformat(),
        'timezone': 'Europe/Berlin',
        'utc_offset': 3600,
        'elapsed_time': 3600,
        'moving_time': 3500,
        'distance': 10000.0,
        'total_elevation_gain': 100.0,
        'average_speed': 2.86,
        'max_speed': 4.2,
        'average_cadence': 85.0,
        'average_heartrate': 145.0,
        'max_heartrate': 165,
        'calories': 650.0,
        'description': 'Great morning run',
        'trainer': False,
        'commute': False,
        'manual': False,
        'start_latlng': [52.5200, 13.4050],
        'end_latlng': [52.5210, 13.4060],
        'map': {'summary_polyline': 'encoded_polyline_here'}
    }


# Sample data sets for bulk testing

SAMPLE_ACTIVITIES = [
    get_sample_activity(1, 'Run', name='Morning Run', distance=10000),
    get_sample_activity(2, 'Ride', name='Evening Ride', distance=30000),
    get_sample_activity(3, 'Swim', name='Pool Swim', distance=2000),
]

SAMPLE_EXTENDED_TYPES = [
    get_sample_extended_type(101, 'Run', 'Easy Run'),
    get_sample_extended_type(102, 'Run', 'Tempo Run'),
    get_sample_extended_type(103, 'Ride', 'Recovery Ride'),
    get_sample_extended_type(104, 'HIIT', 'Tabata'),
]

