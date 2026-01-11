from flask import render_template, request, session, redirect, flash, Response
import csv
import io
from datetime import datetime, timedelta
from collections import defaultdict
from app.web import web_bp
from app.database import (
    get_db, db_row_to_dict, get_extended_types,
    get_standard_types_by_category, get_planned_activities
)
from app.repositories import (
    ActivityRepository,
    PlanningRepository,
    TypeRepository,
    DayRepository,
    GearRepository
)
from app.utils.errors import ActivityNotFoundError, ValidationError, AppError
from app.auth.routes import get_strava_client, is_authenticated as check_strava_auth


@web_bp.route('/')
def index():
    """Display activities grouped by day with pagination (including rest days)"""

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sport_type = request.args.get('sport_type', '')

    db = get_db()

    # Build query for activities with extended types
    query = '''
        SELECT a.*, ext.custom_name as extended_name, ext.color_class as extended_color
        FROM activities a
        LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
        WHERE 1=1
    '''
    params = []

    if sport_type:
        query += ' AND a.sport_type = ?'
        params.append(sport_type)

    query += ' ORDER BY a.start_date_local DESC'

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

    # Generate all days from today back to earliest activity (or default 30 days)
    all_days = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if activities_by_day:
        activity_dates = sorted(activities_by_day.keys())
        first_date = datetime.strptime(activity_dates[0], '%Y-%m-%d')
        # Start from today, go back to the earliest activity date
        start_date = today
    else:
        # No activities yet, show last 30 days
        start_date = today
        first_date = today - timedelta(days=30)

    # Generate all days from start_date to first_date (descending order)
    current_date = start_date
    while current_date >= first_date:
        all_days.append(current_date.strftime('%Y-%m-%d'))
        current_date -= timedelta(days=1)

    # Paginate by days
    total_days = len(all_days)
    total_pages = (total_days + per_page - 1) // per_page if total_days > 0 else 1

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_days = all_days[start_idx:end_idx]

    # Get activities for paginated days (empty list for rest days)
    paginated_activities = {day: activities_by_day.get(day, []) for day in paginated_days}

    # Get day feelings for paginated days
    day_feelings = {}
    if paginated_days:
        placeholders = ','.join(['?' for _ in paginated_days])
        cursor = db.execute(f'SELECT * FROM days WHERE date IN ({placeholders})', paginated_days)
        for row in cursor.fetchall():
            day_feelings[row['date']] = dict(row)

    # Get unique sport types for filter
    cursor = db.execute('SELECT DISTINCT sport_type FROM activities ORDER BY sport_type')
    sport_types = [row['sport_type'] for row in cursor.fetchall()]

    # Get all extended types for dropdowns
    extended_types = get_extended_types()

    # Get standard types grouped by category
    standard_types_by_category = get_standard_types_by_category()

    # Check authentication status (loads from DB if needed, refreshes if expired)
    is_authenticated = check_strava_auth()
    athlete_name = session.get('athlete_name', '')

    # Get and clear flash messages from session
    auth_success = session.pop('auth_success', None)
    auth_error = session.pop('auth_error', None)
    sync_message = session.pop('sync_message', None)

    return render_template(
        'activities.html',
        activities_by_day=paginated_activities,
        sorted_days=paginated_days,
        day_feelings=day_feelings,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_days=total_days,
        sport_types=sport_types,
        extended_types=extended_types,
        standard_types_by_category=standard_types_by_category,
        current_sport_type=sport_type,
        is_authenticated=is_authenticated,
        athlete_name=athlete_name,
        auth_success=auth_success,
        auth_error=auth_error,
        sync_message=sync_message
    )


def _clean_strava_value(value):
    """Convert Strava API objects to JSON-serializable primitives"""
    # Handle None
    if value is None:
        return None

    # Handle primitives - but check for string patterns first
    if isinstance(value, str):
        # Handle "root='Value'" pattern from XML/enum string representation
        if value.startswith("root='") and value.endswith("'"):
            return value[6:-1]  # Extract 'Value' from "root='Value'"
        return value

    if isinstance(value, (int, float, bool)):
        return value

    # Handle datetime objects
    if hasattr(value, 'isoformat'):
        return value.isoformat()

    # Handle lists
    if isinstance(value, list):
        return [_clean_strava_value(item) for item in value]

    # Handle dicts
    if isinstance(value, dict):
        return {k: _clean_strava_value(v) for k, v in value.items()}

    # Handle Strava API objects with to_dict
    if hasattr(value, 'to_dict'):
        return _clean_strava_value(value.to_dict())

    # Handle enums - try to get the value attribute first
    if hasattr(value, 'value'):
        val = value.value
        # Recursively clean the value (might be another enum or object)
        val = _clean_strava_value(val)

        # Clean up Strava enum string values like "relax/weighttraining" -> "WeightTraining"
        if isinstance(val, str):
            if '/' in val:
                # Extract the part after the slash and capitalize properly
                parts = val.split('/')
                if len(parts) == 2:
                    sport = parts[1]
                    # Convert to PascalCase (e.g., "weighttraining" -> "WeightTraining")
                    return ''.join(word.capitalize() for word in sport.replace('(', '').replace(')', '').split())
            # Handle "root='Value'" pattern
            if val.startswith("root='") and val.endswith("'"):
                return val[6:-1]
        return val
    elif hasattr(value, 'name'):
        name = value.name
        # Clean the name recursively
        return _clean_strava_value(name)

    # Convert everything else to string and clean it
    str_value = str(value)
    # Handle "root='Value'" pattern from string representation
    if str_value.startswith("root='") and str_value.endswith("'"):
        return str_value[6:-1]
    return str_value


@web_bp.route('/sync')
def sync():
    """Sync activities from Strava"""
    try:
        client = get_strava_client()
    except Exception as e:
        session['auth_error'] = 'Please connect to Strava first'
        return redirect('/')

    try:
        from app.utils.database_helpers import dict_to_db_values

        # Fetch activities from Strava (summary data only, no descriptions)
        strava_activities = client.get_activities(limit=200)

        db = get_db()
        created_count = 0
        updated_count = 0

        # Define allowed columns based on activities table schema
        allowed_columns = {
            'id', 'resource_state', 'external_id', 'upload_id',
            'start_date', 'start_date_local', 'timezone', 'utc_offset', 'elapsed_time', 'moving_time',
            'start_latlng', 'end_latlng', 'location_city', 'location_state', 'location_country', 'map',
            'name', 'description', 'type', 'sport_type', 'workout_type',
            'distance', 'total_elevation_gain', 'average_speed', 'max_speed', 'average_cadence',
            'average_watts', 'weighted_average_watts', 'kilojoules', 'device_watts', 'max_watts',
            'average_heartrate', 'max_heartrate', 'has_heartrate', 'average_temp', 'calories',
            'elev_high', 'elev_low',
            'kudos_count', 'comment_count', 'athlete_count', 'photo_count', 'total_photo_count',
            'pr_count', 'achievement_count',
            'trainer', 'commute', 'manual', 'private', 'flagged', 'has_kudoed',
            'segment_leaderboard_opt_out', 'leaderboard_opt_out',
            'device_name', 'athlete_id', 'gear_id',
            'segment_efforts', 'splits_metric', 'splits_standard', 'laps', 'best_efforts', 'gear',
            'day_date', 'extended_type_id'
        }

        for strava_activity in strava_activities:
            # Convert to dict
            if hasattr(strava_activity, 'to_dict'):
                activity_data = strava_activity.to_dict()
            else:
                activity_data = dict(strava_activity)

            # Filter to only include allowed columns (remove internal Strava fields)
            activity_data = {k: v for k, v in activity_data.items() if k in allowed_columns}

            # Clean all Strava API objects/enums to primitives
            activity_data = {k: _clean_strava_value(v) for k, v in activity_data.items()}

            # Ensure sport_type exists
            if 'sport_type' not in activity_data or not activity_data['sport_type']:
                activity_data['sport_type'] = activity_data.get('type', 'Workout')

            # Ensure sport_type is a string
            sport_type = str(activity_data['sport_type'])
            activity_data['sport_type'] = sport_type

            # Check if sport type exists in standard_activity_types
            cursor = db.execute(
                'SELECT name FROM standard_activity_types WHERE name = ?',
                (sport_type,)
            )
            if not cursor.fetchone():
                # Auto-create sport type with minimal data
                db.execute(
                    'INSERT OR IGNORE INTO standard_activity_types (name, category, display_name, icon, color) VALUES (?, ?, ?, ?, ?)',
                    (sport_type, 'Other', sport_type, 'circle-question', 'badge-other')
                )

            # Calculate day_date from start_date_local
            if 'start_date_local' in activity_data:
                try:
                    if isinstance(activity_data['start_date_local'], str):
                        dt = datetime.fromisoformat(
                            activity_data['start_date_local'].replace('Z', '+00:00')
                        )
                    else:
                        dt = activity_data['start_date_local']
                    activity_data['day_date'] = dt.date().isoformat()
                except Exception:
                    pass

            # Check if activity exists
            activity_id = activity_data.get('id')
            cursor = db.execute('SELECT id FROM activities WHERE id = ?', (activity_id,))
            existing = cursor.fetchone()

            # Prepare database values
            columns, values = dict_to_db_values(activity_data)

            if existing:
                # Update existing activity
                set_clause = ', '.join([f"{col} = ?" for col in columns])
                db.execute(
                    f'UPDATE activities SET {set_clause}, updated_at = ? WHERE id = ?',
                    values + [datetime.utcnow().isoformat(), activity_id]
                )
                updated_count += 1
            else:
                # Insert new activity
                placeholders = ', '.join(['?' for _ in columns])
                db.execute(
                    f'INSERT INTO activities ({", ".join(columns)}, created_at, updated_at) VALUES ({placeholders}, ?, ?)',
                    values + [datetime.utcnow().isoformat(), datetime.utcnow().isoformat()]
                )
                created_count += 1

        # Commit all changes at once
        db.commit()

        session['sync_message'] = f"Synced from Strava: {created_count} new, {updated_count} updated"
        return redirect('/')

    except Exception as e:
        session['auth_error'] = f"Sync failed: {str(e)}"
        return redirect('/')


@web_bp.route('/activity/<int:activity_id>')
def activity_detail(activity_id):
    """Display detailed view of a specific activity"""
    db = get_db()

    # Fetch activity with extended type information
    cursor = db.execute('''
        SELECT a.*, ext.custom_name as extended_name, ext.color_class as extended_color
        FROM activities a
        LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
        WHERE a.id = ?
    ''', (activity_id,))
    row = cursor.fetchone()

    if not row:
        session['auth_error'] = 'Activity not found'
        return redirect('/')

    activity = db_row_to_dict(row)

    # Get gear information if activity has gear_id
    if activity.get('gear_id'):
        cursor = db.execute('SELECT * FROM gear WHERE id = ?', (activity['gear_id'],))
        gear_row = cursor.fetchone()
        if gear_row:
            activity['gear_info'] = dict(gear_row)

    # Format the date for display
    if activity.get('start_date_local'):
        try:
            date_obj = datetime.fromisoformat(activity['start_date_local'].replace('Z', '+00:00'))
            activity['formatted_date'] = date_obj.strftime('%A, %B %d, %Y')
            activity['formatted_time'] = date_obj.strftime('%H:%M')
        except (ValueError, AttributeError):
            activity['formatted_date'] = activity['start_date_local']
            activity['formatted_time'] = ''

    # Get extended types for the activity's sport type
    extended_types = get_extended_types(base_sport_type=activity.get('sport_type'))

    # Get and clear flash messages from session
    success_message = session.pop('sync_message', None)

    return render_template('activity_detail.html', activity=activity, extended_types=extended_types, success_message=success_message)


@web_bp.route('/activity/<int:activity_id>/annotations', methods=['POST'])
def save_annotations(activity_id):
    """Save feeling annotations for an activity"""
    db = get_db()

    # Check if activity exists
    cursor = db.execute('SELECT id FROM activities WHERE id = ?', (activity_id,))
    if not cursor.fetchone():
        session['auth_error'] = 'Activity not found'
        return redirect('/')

    # Get form data
    feeling_before_text = request.form.get('feeling_before_text', '').strip() or None
    feeling_before_pain = request.form.get('feeling_before_pain', type=int)
    feeling_during_text = request.form.get('feeling_during_text', '').strip() or None
    feeling_during_pain = request.form.get('feeling_during_pain', type=int)
    feeling_after_text = request.form.get('feeling_after_text', '').strip() or None
    feeling_after_pain = request.form.get('feeling_after_pain', type=int)
    coach_comment = request.form.get('coach_comment', '').strip() or None

    # Update the activity
    db.execute('''
        UPDATE activities SET
            feeling_before_text = ?,
            feeling_before_pain = ?,
            feeling_during_text = ?,
            feeling_during_pain = ?,
            feeling_after_text = ?,
            feeling_after_pain = ?,
            coach_comment = ?,
            updated_at = ?
        WHERE id = ?
    ''', (
        feeling_before_text,
        feeling_before_pain,
        feeling_during_text,
        feeling_during_pain,
        feeling_after_text,
        feeling_after_pain,
        coach_comment,
        datetime.utcnow().isoformat(),
        activity_id
    ))
    db.commit()

    session['sync_message'] = 'Annotations saved successfully'
    return redirect(f'/activity/{activity_id}')


@web_bp.route('/activity/<int:activity_id>/extended-type', methods=['POST'])
def assign_extended_type(activity_id):
    """Assign an extended activity type to an activity"""
    db = get_db()

    # Check if activity exists
    cursor = db.execute('SELECT id, sport_type FROM activities WHERE id = ?', (activity_id,))
    activity_row = cursor.fetchone()

    if not activity_row:
        session['auth_error'] = 'Activity not found'
        return redirect('/')

    activity_sport_type = activity_row['sport_type']

    # Get extended_type_id from form (empty string means clear extended type)
    extended_type_id = request.form.get('extended_type_id', '').strip()

    if extended_type_id:
        # Validate that extended type exists and matches base sport type
        cursor = db.execute(
            'SELECT id, base_sport_type FROM extended_activity_types WHERE id = ? AND is_active = 1',
            (extended_type_id,)
        )
        extended_type = cursor.fetchone()

        if not extended_type:
            session['auth_error'] = 'Extended type not found or inactive'
            return redirect(f'/activity/{activity_id}')

        if extended_type['base_sport_type'] != activity_sport_type:
            session['auth_error'] = f"Extended type '{extended_type['base_sport_type']}' does not match activity type '{activity_sport_type}'"
            return redirect(f'/activity/{activity_id}')

        # Assign extended type
        db.execute(
            'UPDATE activities SET extended_type_id = ?, updated_at = ? WHERE id = ?',
            (extended_type_id, datetime.utcnow().isoformat(), activity_id)
        )
        session['sync_message'] = 'Extended type assigned successfully'
    else:
        # Clear extended type (revert to standard type)
        db.execute(
            'UPDATE activities SET extended_type_id = NULL, updated_at = ? WHERE id = ?',
            (datetime.utcnow().isoformat(), activity_id)
        )
        session['sync_message'] = 'Reverted to standard activity type'

    db.commit()
    return redirect(f'/activity/{activity_id}')


@web_bp.route('/report')
def report():
    """Display holistic report for a selected time frame"""
    db = get_db()

    # Get date range parameters (default to last 30 days)
    end_date_str = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date_str = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

    # Query activities within date range
    cursor = db.execute('''
        SELECT * FROM activities
        WHERE date(start_date_local) >= date(?) AND date(start_date_local) <= date(?)
        ORDER BY start_date_local DESC
    ''', (start_date_str, end_date_str))
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = defaultdict(list)
    for row in rows:
        activity = db_row_to_dict(row)
        date_str = activity['start_date_local']
        if date_str:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            day_key = date_obj.strftime('%Y-%m-%d')
            activities_by_day[day_key].append(activity)

    # Fetch planned activities for date range
    from app.database import get_planned_activities
    planned_activities_list = get_planned_activities(start_date_str, end_date_str)

    # Group planned activities by date
    planned_by_day = defaultdict(list)
    for planned in planned_activities_list:
        planned_by_day[planned['date']].append(planned)

    # Generate all days in range (including days without activities)
    all_days = []
    current_date = end_date
    while current_date >= start_date:
        day_key = current_date.strftime('%Y-%m-%d')
        actual_activities = activities_by_day.get(day_key, [])
        planned_activities = planned_by_day.get(day_key, [])

        # Calculate completion rate for the day
        num_planned = len(planned_activities)
        num_actual = len(actual_activities)
        completion_rate = (num_actual / num_planned * 100) if num_planned > 0 else None

        all_days.append({
            'date': day_key,
            'weekday': current_date.strftime('%A'),
            'activities': actual_activities,
            'planned_activities': planned_activities,
            'num_planned': num_planned,
            'num_actual': num_actual,
            'completion_rate': completion_rate
        })
        current_date -= timedelta(days=1)

    # Calculate summary statistics
    total_activities = len(rows)
    total_planned = len(planned_activities_list)
    total_distance = sum(a.get('distance', 0) or 0 for a in [db_row_to_dict(r) for r in rows])
    total_time = sum(a.get('moving_time', 0) or 0 for a in [db_row_to_dict(r) for r in rows])
    days_with_activities = len([d for d in all_days if d['activities']])
    days_with_planned = len([d for d in all_days if d['planned_activities']])

    # Calculate overall completion rate only for days with planned activities
    # Count actual activities only on days that had a plan
    actual_on_planned_days = sum(d['num_actual'] for d in all_days if d['num_planned'] > 0)
    planned_on_planned_days = sum(d['num_planned'] for d in all_days if d['num_planned'] > 0)
    overall_completion_rate = (actual_on_planned_days / planned_on_planned_days * 100) if planned_on_planned_days > 0 else None

    # Get day feelings for all days in range
    day_feelings = {}
    day_dates = [d['date'] for d in all_days]
    if day_dates:
        placeholders = ','.join(['?' for _ in day_dates])
        cursor = db.execute(f'SELECT * FROM days WHERE date IN ({placeholders})', day_dates)
        for row in cursor.fetchall():
            day_feelings[row['date']] = dict(row)

    return render_template(
        'report.html',
        all_days=all_days,
        day_feelings=day_feelings,
        start_date=start_date_str,
        end_date=end_date_str,
        total_activities=total_activities,
        total_planned=total_planned,
        total_distance=total_distance,
        total_time=total_time,
        days_with_activities=days_with_activities,
        days_with_planned=days_with_planned,
        overall_completion_rate=overall_completion_rate,
        total_days=len(all_days)
    )


@web_bp.route('/report/csv')
def report_csv():
    """Export report data as CSV"""
    db = get_db()

    # Get date range parameters (same logic as report route)
    end_date_str = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    start_date_str = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))

    # Parse dates
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    except ValueError:
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

    # Query activities within date range
    cursor = db.execute('''
        SELECT * FROM activities
        WHERE date(start_date_local) >= date(?) AND date(start_date_local) <= date(?)
        ORDER BY start_date_local DESC
    ''', (start_date_str, end_date_str))
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = defaultdict(list)
    for row in rows:
        activity = db_row_to_dict(row)
        date_str = activity['start_date_local']
        if date_str:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            day_key = date_obj.strftime('%Y-%m-%d')
            activities_by_day[day_key].append(activity)

    # Generate all days in range
    all_days = []
    current_date = end_date
    while current_date >= start_date:
        day_key = current_date.strftime('%Y-%m-%d')
        all_days.append({
            'date': day_key,
            'weekday': current_date.strftime('%A'),
            'activities': activities_by_day.get(day_key, [])
        })
        current_date -= timedelta(days=1)

    # Get day feelings
    day_feelings = {}
    day_dates = [d['date'] for d in all_days]
    if day_dates:
        placeholders = ','.join(['?' for _ in day_dates])
        cursor = db.execute(f'SELECT * FROM days WHERE date IN ({placeholders})', day_dates)
        for row in cursor.fetchall():
            day_feelings[row['date']] = dict(row)

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Date', 'Weekday', 'Day Feeling', 'Day Notes', 'Day Coach Comment',
        'Activity', 'Sport Type', 'Distance (km)', 'Duration',
        'Feeling Before', 'Feeling During', 'Feeling After',
        'Notes Before', 'Notes During', 'Notes After', 'Activity Coach Comment'
    ])

    # Write data rows
    for day in all_days:
        day_feel = day_feelings.get(day['date'], {})
        day_feeling_level = day_feel.get('feeling_pain', '')
        day_notes = day_feel.get('feeling_text', '') or ''
        day_coach = day_feel.get('coach_comment', '') or ''

        if day['activities']:
            for activity in day['activities']:
                # Format duration as H:MM
                moving_time = activity.get('moving_time', 0) or 0
                duration = f"{moving_time // 3600}:{(moving_time % 3600) // 60:02d}" if moving_time else ''

                # Format distance in km
                distance = activity.get('distance', 0) or 0
                distance_km = f"{distance / 1000:.2f}" if distance else ''

                writer.writerow([
                    day['date'],
                    day['weekday'][:3],
                    day_feeling_level if day_feeling_level is not None else '',
                    day_notes,
                    day_coach,
                    activity.get('name', ''),
                    activity.get('sport_type', ''),
                    distance_km,
                    duration,
                    activity.get('feeling_before_pain', '') if activity.get('feeling_before_pain') is not None else '',
                    activity.get('feeling_during_pain', '') if activity.get('feeling_during_pain') is not None else '',
                    activity.get('feeling_after_pain', '') if activity.get('feeling_after_pain') is not None else '',
                    activity.get('feeling_before_text', '') or '',
                    activity.get('feeling_during_text', '') or '',
                    activity.get('feeling_after_text', '') or '',
                    activity.get('coach_comment', '') or ''
                ])
        else:
            # Rest day - still include day feeling info
            writer.writerow([
                day['date'],
                day['weekday'][:3],
                day_feeling_level if day_feeling_level is not None else '',
                day_notes,
                day_coach,
                'Rest day', '', '', '', '', '', '', '', '', '', ''
            ])

    # Prepare response
    output.seek(0)
    filename = f"activity_report_{start_date_str}_to_{end_date_str}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@web_bp.route('/day/<date>/annotations', methods=['POST'])
def save_day_annotations(date):
    """Save feeling annotations for a specific day"""
    db = get_db()

    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        session['auth_error'] = 'Invalid date format'
        return redirect('/')

    # Get form data
    feeling_text = request.form.get('feeling_text', '').strip() or None
    feeling_pain = request.form.get('feeling_pain', type=int)
    coach_comment = request.form.get('coach_comment', '').strip() or None

    # Check if day entry exists
    cursor = db.execute('SELECT date FROM days WHERE date = ?', (date,))
    exists = cursor.fetchone()

    if exists:
        # Update existing day
        db.execute('''
            UPDATE days SET
                feeling_text = ?,
                feeling_pain = ?,
                coach_comment = ?,
                updated_at = ?
            WHERE date = ?
        ''', (feeling_text, feeling_pain, coach_comment, datetime.utcnow().isoformat(), date))
    else:
        # Insert new day
        db.execute('''
            INSERT INTO days (date, feeling_text, feeling_pain, coach_comment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (date, feeling_text, feeling_pain, coach_comment, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))

    db.commit()

    session['sync_message'] = 'Day feeling saved successfully'

    # Redirect back to the referring page
    referer = request.form.get('referer', '/')
    return redirect(referer)
