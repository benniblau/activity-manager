from flask import render_template, request, session, redirect, flash, Response
import csv
import io
from datetime import datetime, timedelta
from collections import defaultdict
from app.web import web_bp
from app.database import get_db, db_row_to_dict, dict_to_db_values, get_extended_types
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

        print("Starting to iterate through activities...", file=sys.stderr, flush=True)
        activity_list = list(activities)  # Convert to list to check count
        print(f"Total activities fetched: {len(activity_list)}", file=sys.stderr, flush=True)

        for strava_activity in activity_list:
            try:
                activity_id = strava_activity.id

                # Check if activity already exists and get current data
                cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
                existing_row = cursor.fetchone()

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
                    # Check if it's a Pydantic RootModel (has .root attribute)
                    if hasattr(value, 'root'):
                        return str(value.root)
                    # Check if it's an enum with a .value attribute
                    if hasattr(value, 'value'):
                        inner = value.value
                        # Check if the value itself is a RootModel
                        if hasattr(inner, 'root'):
                            return str(inner.root)
                        return str(inner)
                    # Check if it's an enum with a .name attribute
                    if hasattr(value, 'name'):
                        return str(value.name)
                    return str(value)

                # Extract day_date from start_date_local
                day_date = None
                if getattr(strava_activity, 'start_date_local', None):
                    day_date = strava_activity.start_date_local.strftime('%Y-%m-%d')

                # Convert stravalib activity to dict
                # Use getattr with defaults for attributes that might not exist on SummaryActivity
                activity_data = {
                    'id': activity_id,
                    'name': getattr(strava_activity, 'name', None),
                    'sport_type': enum_to_str(getattr(strava_activity, 'sport_type', None)),
                    'type': enum_to_str(getattr(strava_activity, 'type', None)),
                    'start_date': strava_activity.start_date.isoformat() if getattr(strava_activity, 'start_date', None) else None,
                    'start_date_local': strava_activity.start_date_local.isoformat() if getattr(strava_activity, 'start_date_local', None) else None,
                    'day_date': day_date,
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
                    'gear_id': getattr(strava_activity, 'gear_id', None),
                }

                # Prepare data for database
                db_data = dict_to_db_values(activity_data)

                if existing_row:
                    # Check if any fields have actually changed
                    existing_data = db_row_to_dict(existing_row)
                    update_data = {k: v for k, v in db_data.items() if k != 'id'}

                    # CRITICAL: Never overwrite extended_type_id from Strava sync
                    # This preserves user's custom activity type classifications
                    update_data.pop('extended_type_id', None)

                    # Compare values to detect actual changes
                    has_changes = False
                    for key, new_value in update_data.items():
                        old_value = existing_data.get(key)
                        # Normalize comparison (handle None vs 0, float precision, etc.)
                        if old_value != new_value:
                            # Check if it's just a numeric precision difference
                            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                                if abs(float(old_value or 0) - float(new_value or 0)) > 0.001:
                                    has_changes = True
                                    break
                            else:
                                has_changes = True
                                break

                    if has_changes:
                        # Update existing activity, but preserve feeling annotations
                        update_data['updated_at'] = datetime.utcnow().isoformat()

                        # Build update query
                        set_clause = ', '.join([f'{key} = ?' for key in update_data.keys()])
                        query = f'UPDATE activities SET {set_clause} WHERE id = ?'

                        db.execute(query, list(update_data.values()) + [activity_id])
                        updated_count += 1
                else:
                    # Build insert query for new activity
                    columns = ', '.join(db_data.keys())
                    placeholders = ', '.join(['?' for _ in db_data])
                    query = f'INSERT INTO activities ({columns}) VALUES ({placeholders})'

                    db.execute(query, list(db_data.values()))
                    created_count += 1

            except Exception as e:
                print(f"Error syncing activity {activity_id}: {e}")
                continue

        # Create days entries for all unique dates that don't exist yet
        cursor = db.execute('''
            SELECT DISTINCT day_date FROM activities
            WHERE day_date IS NOT NULL
            AND day_date NOT IN (SELECT date FROM days)
        ''')
        new_dates = [row[0] for row in cursor.fetchall()]

        days_created = 0
        for date in new_dates:
            db.execute('''
                INSERT INTO days (date, created_at, updated_at)
                VALUES (?, ?, ?)
            ''', (date, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
            days_created += 1

        db.commit()

        # Sync gear information for all unique gear_ids not yet in gear table
        cursor = db.execute('''
            SELECT DISTINCT gear_id FROM activities
            WHERE gear_id IS NOT NULL
            AND gear_id NOT IN (SELECT id FROM gear)
        ''')
        new_gear_ids = [row[0] for row in cursor.fetchall()]

        gear_synced = 0
        for gear_id in new_gear_ids:
            try:
                print(f"Fetching gear details for {gear_id}...", file=sys.stderr, flush=True)
                gear = client.get_gear(gear_id)

                # Determine gear type from the ID prefix (b=bike, g=shoes)
                gear_type = 'bike' if gear_id.startswith('b') else 'shoes' if gear_id.startswith('g') else 'unknown'

                db.execute('''
                    INSERT INTO gear (id, name, brand_name, model_name, gear_type, description,
                                     distance, primary_gear, retired, resource_state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    gear_id,
                    getattr(gear, 'name', None),
                    getattr(gear, 'brand_name', None),
                    getattr(gear, 'model_name', None),
                    gear_type,
                    getattr(gear, 'description', None),
                    float(gear.distance) if getattr(gear, 'distance', None) else 0,
                    1 if getattr(gear, 'primary', False) else 0,
                    1 if getattr(gear, 'retired', False) else 0,
                    getattr(gear, 'resource_state', None),
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat()
                ))
                gear_synced += 1
            except Exception as e:
                print(f"Error fetching gear {gear_id}: {e}", file=sys.stderr, flush=True)
                continue

        if gear_synced > 0:
            db.commit()
            print(f"Synced {gear_synced} gear items", file=sys.stderr, flush=True)

        import sys
        print(f"Sync completed: {created_count} created, {updated_count} updated, {days_created} days added, {gear_synced} gear synced", file=sys.stderr, flush=True)
        session['sync_message'] = f"Synced from Strava: {created_count} new, {updated_count} updated, {gear_synced} gear."
        return redirect('/')

    except Exception as e:
        import sys, traceback
        print(f"Sync failed with error: {e}", file=sys.stderr, flush=True)
        print(traceback.format_exc(), file=sys.stderr, flush=True)
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
    overall_completion_rate = (total_activities / total_planned * 100) if total_planned > 0 else None

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
