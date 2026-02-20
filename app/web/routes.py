from flask import render_template, request, session, redirect, flash, Response, send_from_directory, current_app
from flask_login import login_required, current_user
import csv
import io
import os
from datetime import datetime, timedelta
from app.web import web_bp
from app.database import (
    get_db, get_extended_types,
    get_standard_types_by_category
)
from app.utils.database_helpers import db_row_to_dict, group_activities_by_day
from app.repositories import (
    ActivityRepository,
    TypeRepository,
    DayRepository,
    GearRepository
)
from app.utils.errors import ActivityNotFoundError, ValidationError, AppError
from app.auth.routes import get_strava_client, is_authenticated as check_strava_auth
from app.services.access_control_service import get_viewing_user_id, can_view_user_data
from app.auth.decorators import athlete_required


@web_bp.route('/')
@login_required
def index():
    """Display activities grouped by day with pagination (including rest days)"""

    # Get viewing user ID (supports coach viewing athlete data)
    viewing_user_id = get_viewing_user_id()

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    sport_type = request.args.get('sport_type', '')

    db = get_db()

    # Build query for activities with extended types (filtered by user_id)
    query = '''
        SELECT a.*, ext.custom_name as extended_name, ext.color_class as extended_color
        FROM activities a
        LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
        WHERE a.user_id = ?
    '''
    params = [viewing_user_id]

    if sport_type:
        query += ' AND a.sport_type = ?'
        params.append(sport_type)

    query += ' ORDER BY a.start_date_local DESC'

    # Get all activities (we'll paginate by days, not activities)
    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = group_activities_by_day([db_row_to_dict(row) for row in rows])

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

    # Get day feelings for paginated days (filtered by user_id)
    day_repo = DayRepository()
    day_feelings = day_repo.get_feelings_by_dates(paginated_days, user_id=viewing_user_id)

    # Get unique sport types for filter (filtered by user_id)
    cursor = db.execute('SELECT DISTINCT sport_type FROM activities WHERE user_id = ? ORDER BY sport_type', (viewing_user_id,))
    sport_types = [row['sport_type'] for row in cursor.fetchall()]

    # Get all extended types for dropdowns (system + user-specific)
    type_repo = TypeRepository()
    extended_types = type_repo.get_extended_types(is_active=True, user_id=viewing_user_id)

    # Get standard types grouped by category
    standard_types_by_category = get_standard_types_by_category()

    # Check Strava authentication status
    is_strava_authenticated = check_strava_auth()
    strava_athlete_name = session.get('strava_athlete_name', '')

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
        is_strava_authenticated=is_strava_authenticated,
        strava_athlete_name=strava_athlete_name,
        current_user=current_user
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
@login_required
def sync():
    """Sync activities from Strava (fallback for non-JS)"""
    # Redirect to home - actual sync is done via AJAX
    return redirect('/')


@web_bp.route('/api/sync/activities', methods=['POST'])
@login_required
@athlete_required
def api_sync_activities():
    """AJAX: Step 1 - Sync activity summary data"""
    from flask import jsonify

    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    try:
        client = get_strava_client()
    except Exception:
        return jsonify({'error': 'Please connect to Strava first'}), 401

    try:
        from app.services.strava_service import StravaService

        db = get_db()
        strava_service = StravaService(client, db, user_id=viewing_user_id)

        # Fast bulk sync with summary data only
        result = strava_service.sync_activities(limit=200, fetch_details=False)

        # Get count of activities needing descriptions (filtered by user)
        cursor = db.execute('''
            SELECT COUNT(*) as count FROM activities
            WHERE user_id = ? AND (description IS NULL OR description = '')
        ''', (viewing_user_id,))
        needs_descriptions = cursor.fetchone()['count']

        return jsonify({
            'success': True,
            'created': result['created'],
            'updated': result['updated'],
            'needs_descriptions': min(needs_descriptions, 5)  # Cap at 5
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@web_bp.route('/api/sync/description/<int:activity_id>', methods=['POST'])
@login_required
@athlete_required
def api_sync_description(activity_id):
    """AJAX: Step 2 - Fetch description for a single activity"""
    from flask import jsonify

    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    try:
        client = get_strava_client()
    except Exception:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        db = get_db()

        # Verify activity belongs to user
        cursor = db.execute('SELECT user_id FROM activities WHERE id = ?', (activity_id,))
        activity = cursor.fetchone()
        if not activity or activity['user_id'] != viewing_user_id:
            return jsonify({'error': 'Activity not found'}), 404

        detailed = client.get_activity(activity_id)

        description = None
        if hasattr(detailed, 'description') and detailed.description:
            desc = detailed.description
            if hasattr(desc, 'root'):
                desc = desc.root
            if desc and str(desc) not in ('None', ''):
                description = str(desc)

        if not description and hasattr(detailed, 'to_dict'):
            data = detailed.to_dict()
            if data.get('description'):
                desc = data['description']
                if hasattr(desc, 'root'):
                    desc = desc.root
                if desc and str(desc) not in ('None', ''):
                    description = str(desc)

        if description:
            db.execute(
                'UPDATE activities SET description = ?, updated_at = ? WHERE id = ? AND user_id = ?',
                (description, datetime.utcnow().isoformat(), activity_id, viewing_user_id)
            )
            db.commit()
            return jsonify({'success': True, 'has_description': True})

        return jsonify({'success': True, 'has_description': False})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@web_bp.route('/api/sync/activities-needing-descriptions', methods=['GET'])
@login_required
def api_activities_needing_descriptions():
    """AJAX: Get list of activity IDs needing descriptions"""
    from flask import jsonify

    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    db = get_db()
    cursor = db.execute('''
        SELECT id FROM activities
        WHERE user_id = ? AND (description IS NULL OR description = '')
        ORDER BY start_date_local DESC
        LIMIT 5
    ''', (viewing_user_id,))
    activities = [row['id'] for row in cursor.fetchall()]

    return jsonify({'activity_ids': activities})


@web_bp.route('/activity/<int:activity_id>')
@login_required
def activity_detail(activity_id):
    """Display detailed view of a specific activity"""
    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    db = get_db()

    # Fetch activity with extended type information (filtered by user_id)
    cursor = db.execute('''
        SELECT a.*, ext.custom_name as extended_name, ext.color_class as extended_color
        FROM activities a
        LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
        WHERE a.id = ? AND a.user_id = ?
    ''', (activity_id, viewing_user_id))
    row = cursor.fetchone()

    if not row:
        flash('Activity not found', 'danger')
        return redirect('/')

    activity = db_row_to_dict(row)

    # Get gear information if activity has gear_id
    if activity.get('gear_id'):
        cursor = db.execute('SELECT * FROM gear WHERE id = ? AND user_id = ?', (activity['gear_id'], viewing_user_id))
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

    # Get extended types for the activity's sport type (system + user-specific)
    type_repo = TypeRepository()
    extended_types = type_repo.get_extended_types_by_base(activity.get('sport_type'), is_active=True, user_id=viewing_user_id)

    # Get media for this activity
    media_cursor = db.execute(
        'SELECT * FROM activity_media WHERE activity_id = ? ORDER BY sort_order',
        (activity_id,)
    )
    activity_media = [db_row_to_dict(row) for row in media_cursor.fetchall()]

    return render_template('activity_detail.html', activity=activity, extended_types=extended_types, activity_media=activity_media)


@web_bp.route('/activity/<int:activity_id>/annotations', methods=['POST'])
@login_required
@athlete_required
def save_annotations(activity_id):
    """Save feeling annotations for an activity (athlete only)"""
    db = get_db()

    # Check if activity belongs to the logged-in athlete
    cursor = db.execute('SELECT id FROM activities WHERE id = ? AND user_id = ?',
                        (activity_id, current_user.id))
    if not cursor.fetchone():
        flash('Activity not found', 'danger')
        return redirect('/')

    # Get feeling form data only (no coach_comment)
    feeling_before_text = request.form.get('feeling_before_text', '').strip() or None
    feeling_before_pain = request.form.get('feeling_before_pain', type=int)
    feeling_during_text = request.form.get('feeling_during_text', '').strip() or None
    feeling_during_pain = request.form.get('feeling_during_pain', type=int)
    feeling_after_text = request.form.get('feeling_after_text', '').strip() or None
    feeling_after_pain = request.form.get('feeling_after_pain', type=int)

    db.execute('''
        UPDATE activities SET
            feeling_before_text = ?,
            feeling_before_pain = ?,
            feeling_during_text = ?,
            feeling_during_pain = ?,
            feeling_after_text = ?,
            feeling_after_pain = ?,
            updated_at = ?
        WHERE id = ? AND user_id = ?
    ''', (
        feeling_before_text,
        feeling_before_pain,
        feeling_during_text,
        feeling_during_pain,
        feeling_after_text,
        feeling_after_pain,
        datetime.utcnow().isoformat(),
        activity_id,
        current_user.id
    ))
    db.commit()

    flash('Annotations saved successfully', 'success')
    return redirect(f'/activity/{activity_id}')


@web_bp.route('/activity/<int:activity_id>/coach-comment', methods=['POST'])
@login_required
def save_activity_coach_comment(activity_id):
    """Save coach comment for an activity (coach with access only)"""
    db = get_db()

    # Look up the activity owner
    cursor = db.execute('SELECT id, user_id FROM activities WHERE id = ?', (activity_id,))
    row = cursor.fetchone()
    if not row:
        flash('Activity not found', 'danger')
        return redirect('/')

    owner_id = row['user_id']

    if not can_view_user_data(current_user.id, owner_id):
        flash('You do not have permission to comment on this activity.', 'danger')
        return redirect(f'/activity/{activity_id}')

    coach_comment = request.form.get('coach_comment', '').strip() or None

    db.execute(
        'UPDATE activities SET coach_comment = ?, updated_at = ? WHERE id = ?',
        (coach_comment, datetime.utcnow().isoformat(), activity_id)
    )
    db.commit()

    flash('Coach comment saved successfully', 'success')
    return redirect(f'/activity/{activity_id}')


@web_bp.route('/activity/<int:activity_id>/extended-type', methods=['POST'])
@login_required
@athlete_required
def assign_extended_type(activity_id):
    """Assign an extended activity type to an activity"""
    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    db = get_db()

    # Check if activity exists and belongs to user
    cursor = db.execute('SELECT id, sport_type FROM activities WHERE id = ? AND user_id = ?', (activity_id, viewing_user_id))
    activity_row = cursor.fetchone()

    if not activity_row:
        flash('Activity not found', 'danger')
        return redirect('/')

    activity_sport_type = activity_row['sport_type']

    # Get extended_type_id from form (empty string means clear extended type)
    extended_type_id = request.form.get('extended_type_id', '').strip()

    if extended_type_id:
        # Validate that extended type exists, matches base sport type, and user has access
        cursor = db.execute(
            'SELECT id, base_sport_type FROM extended_activity_types WHERE id = ? AND is_active = 1 AND (user_id IS NULL OR user_id = ?)',
            (extended_type_id, viewing_user_id)
        )
        extended_type = cursor.fetchone()

        if not extended_type:
            flash('Extended type not found or inactive', 'danger')
            return redirect(f'/activity/{activity_id}')

        if extended_type['base_sport_type'] != activity_sport_type:
            flash(f"Extended type '{extended_type['base_sport_type']}' does not match activity type '{activity_sport_type}'", 'danger')
            return redirect(f'/activity/{activity_id}')

        # Assign extended type
        db.execute(
            'UPDATE activities SET extended_type_id = ?, updated_at = ? WHERE id = ? AND user_id = ?',
            (extended_type_id, datetime.utcnow().isoformat(), activity_id, viewing_user_id)
        )
        flash('Extended type assigned successfully', 'success')
    else:
        # Clear extended type (revert to standard type)
        db.execute(
            'UPDATE activities SET extended_type_id = NULL, updated_at = ? WHERE id = ? AND user_id = ?',
            (datetime.utcnow().isoformat(), activity_id, viewing_user_id)
        )
        flash('Reverted to standard activity type', 'success')

    db.commit()
    return redirect(f'/activity/{activity_id}')


@web_bp.route('/report')
@login_required
def report():
    """Display holistic report for a selected time frame"""
    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

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

    # Query activities within date range (filtered by user)
    cursor = db.execute('''
        SELECT * FROM activities
        WHERE user_id = ? AND date(start_date_local) >= date(?) AND date(start_date_local) <= date(?)
        ORDER BY start_date_local DESC
    ''', (viewing_user_id, start_date_str, end_date_str))
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = group_activities_by_day([db_row_to_dict(row) for row in rows])

    # Generate all days in range (including days without activities)
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

    # Calculate summary statistics
    total_activities = len(rows)
    total_distance = sum(a.get('distance', 0) or 0 for a in [db_row_to_dict(r) for r in rows])
    total_time = sum(a.get('moving_time', 0) or 0 for a in [db_row_to_dict(r) for r in rows])
    days_with_activities = len([d for d in all_days if d['activities']])

    # Get day feelings for all days in range (filtered by user)
    day_repo = DayRepository()
    day_feelings = day_repo.get_feelings_by_dates([d['date'] for d in all_days], user_id=viewing_user_id)

    return render_template(
        'report.html',
        all_days=all_days,
        day_feelings=day_feelings,
        start_date=start_date_str,
        end_date=end_date_str,
        total_activities=total_activities,
        total_distance=total_distance,
        total_time=total_time,
        days_with_activities=days_with_activities,
        total_days=len(all_days)
    )


@web_bp.route('/report/csv')
@login_required
def report_csv():
    """Export report data as CSV"""
    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

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

    # Query activities within date range (filtered by user)
    cursor = db.execute('''
        SELECT * FROM activities
        WHERE user_id = ? AND date(start_date_local) >= date(?) AND date(start_date_local) <= date(?)
        ORDER BY start_date_local DESC
    ''', (viewing_user_id, start_date_str, end_date_str))
    rows = cursor.fetchall()

    # Group activities by day
    activities_by_day = group_activities_by_day([db_row_to_dict(row) for row in rows])

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

    # Get day feelings (filtered by user)
    day_repo = DayRepository()
    day_feelings = day_repo.get_feelings_by_dates([d['date'] for d in all_days], user_id=viewing_user_id)

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
@login_required
@athlete_required
def save_day_annotations(date):
    """Save feeling annotations for a specific day (athlete only)"""
    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect('/')

    # Get feeling form data only (no coach_comment)
    feeling_text = request.form.get('feeling_text', '').strip() or None
    feeling_pain = request.form.get('feeling_pain', type=int)

    day_repo = DayRepository()
    day_repo.update_day(date, current_user.id, {
        'feeling_text': feeling_text,
        'feeling_pain': feeling_pain,
    })

    flash('Day feeling saved successfully', 'success')

    referer = request.form.get('referer', '/')
    return redirect(referer)


@web_bp.route('/day/<date>/coach-comment', methods=['POST'])
@login_required
def save_day_coach_comment(date):
    """Save coach comment for a day (coach with access only)"""
    # Validate date format
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect('/')

    # The day belongs to whoever the coach is currently viewing
    viewing_user_id = get_viewing_user_id()

    if not can_view_user_data(current_user.id, viewing_user_id):
        flash('You do not have permission to comment on this day.', 'danger')
        return redirect(f'/day/{date}')

    coach_comment = request.form.get('coach_comment', '').strip() or None

    day_repo = DayRepository()
    day_repo.update_day(date, viewing_user_id, {'coach_comment': coach_comment})

    flash('Coach comment saved successfully', 'success')
    return redirect(f'/day/{date}')


@web_bp.route('/day/<date>')
@login_required
def day_detail(date):
    """Display detailed view of a specific day — shareable URL for coach"""
    # Get viewing user ID
    viewing_user_id = get_viewing_user_id()

    # Validate date format
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        flash('Invalid date format. Use YYYY-MM-DD.', 'danger')
        return redirect('/')

    # Fetch day data using repository (filtered by user_id)
    day_repo = DayRepository()
    day_data = day_repo.get_day_with_activities(date, user_id=viewing_user_id)
    day_feeling = day_data['day'] or {}
    activities = day_data['activities']

    # Compute stats
    total_distance = sum((a.get('distance') or 0) for a in activities)
    total_time = sum((a.get('moving_time') or 0) for a in activities)
    total_elevation = sum((a.get('total_elevation_gain') or 0) for a in activities)

    stats = {
        'activity_count': len(activities),
        'total_distance': total_distance,
        'total_time': total_time,
        'total_elevation': total_elevation,
    }

    # Format date for display
    formatted_date = date_obj.strftime('%A, %B %d, %Y')
    weekday = date_obj.strftime('%A')

    # Prev/next day navigation
    prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

    # Flash messages
    success_message = session.pop('sync_message', None)

    # Build share data for JS (avoids inline Jinja2 in JavaScript)
    share_data = {
        'formatted_date': formatted_date,
        'feeling_pain': day_feeling.get('feeling_pain') if day_feeling else None,
        'feeling_text': day_feeling.get('feeling_text') if day_feeling else None,
        'activities': [
            {
                'name': a.get('name'),
                'distance': a.get('distance'),
                'moving_time': a.get('moving_time'),
                'average_speed': a.get('average_speed'),
                'sport_type': a.get('sport_type'),
            }
            for a in activities
        ],
    }

    return render_template(
        'day_detail.html',
        date=date,
        formatted_date=formatted_date,
        weekday=weekday,
        day_feeling=day_feeling,
        activities=activities,
        stats=stats,
        prev_date=prev_date,
        next_date=next_date,
        success_message=success_message,
        share_data=share_data,
    )


@web_bp.route('/data/media/<path:filename>')
@login_required
def serve_media(filename):
    """Serve activity media files (photos)"""
    # TODO: Add verification that the media belongs to the viewing user
    media_dir = os.path.join(current_app.root_path, '..', 'data', 'media')
    return send_from_directory(os.path.abspath(media_dir), filename)


@web_bp.route('/data/fit/<path:filename>')
@login_required
def serve_fit(filename):
    """Serve FIT files for download"""
    # TODO: Add verification that the FIT file belongs to the viewing user
    fit_dir = os.path.join(current_app.root_path, '..', 'data', 'fit_files')
    return send_from_directory(os.path.abspath(fit_dir), filename, as_attachment=True)
