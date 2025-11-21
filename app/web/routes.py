from flask import render_template, request, session, redirect, flash
from datetime import datetime, timedelta
from collections import defaultdict
from app.web import web_bp
from app.database import get_db, db_row_to_dict, dict_to_db_values
from app.auth.routes import get_strava_client


@web_bp.route('/')
def index():
    """Display activities grouped by day with pagination"""

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sport_type = request.args.get('sport_type', '')

    db = get_db()

    # Build query for activities
    query = 'SELECT * FROM activities WHERE 1=1'
    params = []

    if sport_type:
        query += ' AND sport_type = ?'
        params.append(sport_type)

    query += ' ORDER BY start_date_local DESC'

    # Get all activities (we'll paginate by days, not activities)
    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = defaultdict(list)
    for row in rows:
        activity = db_row_to_dict(row)
        # Extract date from start_date_local
        date_str = activity['start_date_local']
        if date_str:
            # Parse ISO format date
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            day_key = date_obj.strftime('%Y-%m-%d')
            activities_by_day[day_key].append(activity)

    # Sort days in descending order
    sorted_days = sorted(activities_by_day.keys(), reverse=True)

    # Paginate by days
    total_days = len(sorted_days)
    total_pages = (total_days + per_page - 1) // per_page

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_days = sorted_days[start_idx:end_idx]

    # Get activities for paginated days
    paginated_activities = {day: activities_by_day[day] for day in paginated_days}

    # Get unique sport types for filter
    cursor = db.execute('SELECT DISTINCT sport_type FROM activities ORDER BY sport_type')
    sport_types = [row['sport_type'] for row in cursor.fetchall()]

    # Check authentication status
    is_authenticated = 'access_token' in session
    athlete_name = session.get('athlete_name', '')

    # Get and clear flash messages from session
    auth_success = session.pop('auth_success', None)
    auth_error = session.pop('auth_error', None)
    sync_message = session.pop('sync_message', None)

    return render_template(
        'activities.html',
        activities_by_day=paginated_activities,
        sorted_days=paginated_days,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_days=total_days,
        sport_types=sport_types,
        current_sport_type=sport_type,
        is_authenticated=is_authenticated,
        athlete_name=athlete_name,
        auth_success=auth_success,
        auth_error=auth_error,
        sync_message=sync_message
    )


@web_bp.route('/sync')
def sync():
    """Sync activities from Strava"""
    import sys
    print("=" * 80, file=sys.stderr, flush=True)
    print("SYNC ROUTE CALLED", file=sys.stderr, flush=True)
    print("=" * 80, file=sys.stderr, flush=True)

    try:
        print("Attempting to get Strava client...", file=sys.stderr, flush=True)
        client = get_strava_client()
        print(f"Got Strava client: {client}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Failed to get Strava client: {e}")
        import traceback
        print(traceback.format_exc())
        session['auth_error'] = 'Please connect to Strava first'
        return redirect('/')

    try:
        # Fetch activities from Strava (all activities, max 200)
        # Removing time filter to get all activities
        import sys
        print("Fetching all activities from Strava (up to 200)...", file=sys.stderr, flush=True)
        activities = client.get_activities(limit=200)

        db = get_db()
        created_count = 0
        updated_count = 0
        skipped_count = 0

        print("Starting to iterate through activities...", file=sys.stderr, flush=True)
        activity_list = list(activities)  # Convert to list to check count
        print(f"Total activities fetched: {len(activity_list)}", file=sys.stderr, flush=True)

        for strava_activity in activity_list:
            try:
                activity_id = strava_activity.id

                # Check if activity already exists
                cursor = db.execute('SELECT id FROM activities WHERE id = ?', (activity_id,))
                exists = cursor.fetchone()

                if exists:
                    skipped_count += 1
                    continue

                # Helper function to convert time values (handles both timedelta and Duration objects)
                def to_seconds(time_value):
                    if time_value is None:
                        return 0
                    if hasattr(time_value, 'total_seconds'):
                        return int(time_value.total_seconds())
                    # Handle Duration objects from stravalib 2.4
                    if hasattr(time_value, 'seconds'):
                        return int(time_value.seconds)
                    # Try to convert directly to int
                    return int(time_value) if time_value else 0

                # Helper function to convert enum to string value
                def enum_to_str(value):
                    if value is None:
                        return None
                    # Check if it's an enum with a .value attribute
                    if hasattr(value, 'value'):
                        return str(value.value)
                    return str(value)

                # Convert stravalib activity to dict
                # Use getattr with defaults for attributes that might not exist on SummaryActivity
                activity_data = {
                    'id': activity_id,
                    'name': getattr(strava_activity, 'name', None),
                    'sport_type': enum_to_str(getattr(strava_activity, 'sport_type', None)),
                    'type': enum_to_str(getattr(strava_activity, 'type', None)),
                    'start_date': strava_activity.start_date.isoformat() if getattr(strava_activity, 'start_date', None) else None,
                    'start_date_local': strava_activity.start_date_local.isoformat() if getattr(strava_activity, 'start_date_local', None) else None,
                    'timezone': str(strava_activity.timezone) if getattr(strava_activity, 'timezone', None) else None,
                    'elapsed_time': to_seconds(getattr(strava_activity, 'elapsed_time', None)),
                    'moving_time': to_seconds(getattr(strava_activity, 'moving_time', None)),
                    'distance': float(strava_activity.distance) if getattr(strava_activity, 'distance', None) else 0,
                    'total_elevation_gain': float(strava_activity.total_elevation_gain) if getattr(strava_activity, 'total_elevation_gain', None) else 0,
                    'average_speed': float(strava_activity.average_speed) if getattr(strava_activity, 'average_speed', None) else 0,
                    'max_speed': float(strava_activity.max_speed) if getattr(strava_activity, 'max_speed', None) else 0,
                    'average_cadence': float(strava_activity.average_cadence) if getattr(strava_activity, 'average_cadence', None) else 0,
                    'average_watts': float(strava_activity.average_watts) if getattr(strava_activity, 'average_watts', None) else 0,
                    'average_heartrate': float(strava_activity.average_heartrate) if getattr(strava_activity, 'average_heartrate', None) else 0,
                    'max_heartrate': int(strava_activity.max_heartrate) if getattr(strava_activity, 'max_heartrate', None) else 0,
                    'calories': float(getattr(strava_activity, 'calories', None)) if getattr(strava_activity, 'calories', None) else 0,
                    'description': getattr(strava_activity, 'description', None),
                    'trainer': getattr(strava_activity, 'trainer', None),
                    'commute': getattr(strava_activity, 'commute', None),
                    'manual': getattr(strava_activity, 'manual', None),
                    'private': getattr(strava_activity, 'private', None),
                    'device_name': getattr(strava_activity, 'device_name', None),
                    'kudos_count': getattr(strava_activity, 'kudos_count', 0) or 0,
                    'comment_count': getattr(strava_activity, 'comment_count', 0) or 0,
                }

                # Prepare data for database
                db_data = dict_to_db_values(activity_data)

                # Build insert query
                columns = ', '.join(db_data.keys())
                placeholders = ', '.join(['?' for _ in db_data])
                query = f'INSERT INTO activities ({columns}) VALUES ({placeholders})'

                db.execute(query, list(db_data.values()))
                created_count += 1

            except Exception as e:
                print(f"Error syncing activity {activity_id}: {e}")
                continue

        db.commit()

        import sys
        print(f"Sync completed: {created_count} created, {skipped_count} skipped", file=sys.stderr, flush=True)
        session['sync_message'] = f"Synced {created_count} new activities from Strava. {skipped_count} already existed."
        return redirect('/')

    except Exception as e:
        import sys, traceback
        print(f"Sync failed with error: {e}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        session['auth_error'] = f"Sync failed: {str(e)}"
        return redirect('/')
