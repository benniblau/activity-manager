from flask import render_template, request, jsonify, redirect, url_for, session, flash
from app.planning import planning_bp
from app.database import get_db, db_row_to_dict, get_extended_types, get_planned_activities
from datetime import datetime, timedelta
from collections import defaultdict


@planning_bp.route('/')
def index():
    """Main planning calendar view (daily list)"""
    db = get_db()

    # Get page and per_page parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Calculate date range for planning (default: 30 days forward from today)
    today = datetime.now().date()
    start_date = today - timedelta(days=7)  # Start from 1 week ago
    end_date = today + timedelta(days=60)    # Up to 60 days in future

    # Generate all days in range
    all_days = []
    current_date = start_date
    while current_date <= end_date:
        all_days.append(current_date.strftime('%Y-%m-%d'))
        current_date += timedelta(days=1)

    # Pagination
    total_days = len(all_days)
    total_pages = (total_days + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    sorted_days = all_days[start_idx:end_idx]

    # Fetch planned activities for the displayed days
    if sorted_days:
        planned_activities_list = get_planned_activities(sorted_days[0], sorted_days[-1])
    else:
        planned_activities_list = []

    # Group planned activities by date
    planned_by_day = defaultdict(list)
    for planned in planned_activities_list:
        planned_by_day[planned['date']].append(planned)

    # Fetch actual activities for the same date range (to show for comparison)
    activities_query = '''
        SELECT
            a.*,
            ext.custom_name as extended_name,
            ext.color_class as extended_color,
            ext.icon_override as extended_icon
        FROM activities a
        LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
        WHERE a.day_date >= ? AND a.day_date <= ?
        ORDER BY a.start_date_local
    '''
    cursor = db.execute(activities_query, (sorted_days[0] if sorted_days else today.strftime('%Y-%m-%d'),
                                            sorted_days[-1] if sorted_days else today.strftime('%Y-%m-%d')))
    activities = [db_row_to_dict(row) for row in cursor.fetchall()]

    # Group activities by day using day_date field
    activities_by_day = defaultdict(list)
    for activity in activities:
        day_date = activity.get('day_date')  # Use day_date consistently
        if day_date:
            activities_by_day[day_date].append(activity)

    # Fetch all extended types for dropdowns
    extended_types = get_extended_types()

    # Get distinct sport types for filter
    cursor = db.execute('SELECT DISTINCT sport_type FROM activities ORDER BY sport_type')
    sport_types = [row[0] for row in cursor.fetchall()]

    return render_template('planning.html',
                           sorted_days=sorted_days,
                           planned_by_day=dict(planned_by_day),
                           activities_by_day=dict(activities_by_day),
                           extended_types=extended_types,
                           sport_types=sport_types,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_days=total_days,
                           today=today.strftime('%Y-%m-%d'))


@planning_bp.route('/activity', methods=['POST'])
def create_planned_activity():
    """Create a new planned activity"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Validate required fields
    if not data.get('date') or not data.get('name'):
        return jsonify({'error': 'Date and name are required'}), 400

    # Validate activity type (either extended_type_id or sport_type must be provided)
    extended_type_id = data.get('extended_type_id')
    sport_type = data.get('sport_type')

    if not extended_type_id and not sport_type:
        return jsonify({'error': 'Either extended_type_id or sport_type must be provided'}), 400

    # Insert planned activity
    cursor = db.execute('''
        INSERT INTO planned_activities
        (date, name, description, extended_type_id, sport_type,
         planned_distance, planned_duration, planned_elevation,
         coaching_notes, intensity_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['date'],
        data['name'],
        data.get('description'),
        extended_type_id if extended_type_id else None,
        sport_type if not extended_type_id else None,
        data.get('planned_distance'),
        data.get('planned_duration'),
        data.get('planned_elevation'),
        data.get('coaching_notes'),
        data.get('intensity_level')
    ))

    db.commit()
    planned_id = cursor.lastrowid

    if request.is_json:
        return jsonify({'id': planned_id, 'message': 'Planned activity created successfully'}), 201
    else:
        flash('Planned activity created successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>', methods=['PUT', 'POST'])
def update_planned_activity(planned_id):
    """Update a planned activity"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Check if planned activity exists
    cursor = db.execute('SELECT * FROM planned_activities WHERE id = ?', (planned_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Planned activity not found'}), 404

    # Update planned activity
    db.execute('''
        UPDATE planned_activities
        SET name = ?, description = ?, extended_type_id = ?, sport_type = ?,
            planned_distance = ?, planned_duration = ?, planned_elevation = ?,
            coaching_notes = ?, intensity_level = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        data.get('name'),
        data.get('description'),
        data.get('extended_type_id') if data.get('extended_type_id') else None,
        data.get('sport_type') if not data.get('extended_type_id') else None,
        data.get('planned_distance'),
        data.get('planned_duration'),
        data.get('planned_elevation'),
        data.get('coaching_notes'),
        data.get('intensity_level'),
        planned_id
    ))

    db.commit()

    if request.is_json:
        return jsonify({'message': 'Planned activity updated successfully'}), 200
    else:
        flash('Planned activity updated successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>', methods=['DELETE'])
def delete_planned_activity(planned_id):
    """Delete a planned activity"""
    db = get_db()

    # Check if planned activity exists
    cursor = db.execute('SELECT * FROM planned_activities WHERE id = ?', (planned_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Planned activity not found'}), 404

    # Delete planned activity
    db.execute('DELETE FROM planned_activities WHERE id = ?', (planned_id,))
    db.commit()

    if request.is_json:
        return jsonify({'message': 'Planned activity deleted successfully'}), 200
    else:
        flash('Planned activity deleted successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/copy', methods=['POST'])
def copy_planned_activity(planned_id):
    """Copy a planned activity to other dates"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Fetch the original planned activity
    cursor = db.execute('SELECT * FROM planned_activities WHERE id = ?', (planned_id,))
    original = cursor.fetchone()

    if not original:
        return jsonify({'error': 'Planned activity not found'}), 404

    # Get target dates
    target_dates = data.get('target_dates', [])
    if isinstance(target_dates, str):
        target_dates = [target_dates]

    if not target_dates:
        return jsonify({'error': 'No target dates provided'}), 400

    # Copy to each target date
    copied_count = 0
    for target_date in target_dates:
        db.execute('''
            INSERT INTO planned_activities
            (date, name, description, extended_type_id, sport_type,
             planned_distance, planned_duration, planned_elevation,
             coaching_notes, intensity_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            target_date,
            original['name'],
            original['description'],
            original['extended_type_id'],
            original['sport_type'],
            original['planned_distance'],
            original['planned_duration'],
            original['planned_elevation'],
            original['coaching_notes'],
            original['intensity_level']
        ))
        copied_count += 1

    db.commit()

    if request.is_json:
        return jsonify({'message': f'Copied to {copied_count} dates', 'count': copied_count}), 201
    else:
        flash(f'Copied to {copied_count} dates successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/match/<int:activity_id>', methods=['POST'])
def match_planned_to_actual(planned_id, activity_id):
    """Link a planned activity to an actual activity"""
    db = get_db()

    # Verify planned activity exists and get its date
    cursor = db.execute('SELECT id, date, name FROM planned_activities WHERE id = ?', (planned_id,))
    planned = cursor.fetchone()
    if not planned:
        return jsonify({'error': 'Planned activity not found'}), 404

    # Verify actual activity exists and get its date
    cursor = db.execute('SELECT id, day_date, name FROM activities WHERE id = ?', (activity_id,))
    actual = cursor.fetchone()
    if not actual:
        return jsonify({'error': 'Actual activity not found'}), 404

    # VALIDATION 1: Check dates match
    if planned['date'] != actual['day_date']:
        return jsonify({
            'error': f'Date mismatch: Planned activity is on {planned["date"]} but actual activity is on {actual["day_date"]}'
        }), 400

    # VALIDATION 2: Check if actual activity is already matched to a different planned activity
    cursor = db.execute('''
        SELECT id, name FROM planned_activities
        WHERE matched_activity_id = ? AND id != ?
    ''', (activity_id, planned_id))
    existing_match = cursor.fetchone()

    if existing_match:
        return jsonify({
            'error': f'This activity is already matched to "{existing_match["name"]}". Please unmatch it first.'
        }), 409  # 409 Conflict

    # Update the match
    db.execute('''
        UPDATE planned_activities
        SET matched_activity_id = ?, match_type = 'manual', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (activity_id, planned_id))

    db.commit()

    if request.is_json:
        return jsonify({'message': 'Activities matched successfully'}), 200
    else:
        flash('Activities matched successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/match', methods=['DELETE'])
def unmatch_planned_activity(planned_id):
    """Unlink a planned activity from its matched actual activity"""
    db = get_db()

    # Check if planned activity exists
    cursor = db.execute('SELECT * FROM planned_activities WHERE id = ?', (planned_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Planned activity not found'}), 404

    # Remove the match
    db.execute('''
        UPDATE planned_activities
        SET matched_activity_id = NULL, match_type = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (planned_id,))

    db.commit()

    if request.is_json:
        return jsonify({'message': 'Activities unmatched successfully'}), 200
    else:
        flash('Activities unmatched successfully', 'success')
        return redirect(url_for('planning.index'))


@planning_bp.route('/types')
def manage_types():
    """Extended activity types management page"""
    extended_types = get_extended_types()

    # Group by base_sport_type for display
    types_by_base = defaultdict(list)
    for ext_type in extended_types:
        types_by_base[ext_type['base_sport_type']].append(ext_type)

    return render_template('planning_types.html',
                           types_by_base=dict(types_by_base),
                           all_types=extended_types)


@planning_bp.route('/types', methods=['POST'])
def create_extended_type():
    """Create a new extended activity type"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Validate required fields
    if not data.get('base_sport_type') or not data.get('custom_name'):
        return jsonify({'error': 'Base sport type and custom name are required'}), 400

    try:
        # Insert new extended type
        cursor = db.execute('''
            INSERT INTO extended_activity_types
            (base_sport_type, custom_name, description, icon_override, color_class, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['base_sport_type'],
            data['custom_name'],
            data.get('description'),
            data.get('icon_override'),
            data.get('color_class'),
            data.get('display_order', 0)
        ))

        db.commit()
        type_id = cursor.lastrowid

        if request.is_json:
            return jsonify({'id': type_id, 'message': 'Extended type created successfully'}), 201
        else:
            flash('Extended type created successfully', 'success')
            return redirect(url_for('planning.manage_types'))

    except Exception as e:
        # Handle unique constraint violation (duplicate custom_name)
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'An extended type with this name already exists'}), 409
        return jsonify({'error': str(e)}), 500


@planning_bp.route('/types/<int:type_id>', methods=['PUT', 'POST'])
def update_extended_type(type_id):
    """Update an extended activity type"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Check if type exists
    cursor = db.execute('SELECT * FROM extended_activity_types WHERE id = ?', (type_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Extended type not found'}), 404

    try:
        # Update extended type
        db.execute('''
            UPDATE extended_activity_types
            SET custom_name = ?, description = ?, icon_override = ?,
                color_class = ?, display_order = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            data.get('custom_name'),
            data.get('description'),
            data.get('icon_override'),
            data.get('color_class'),
            data.get('display_order', 0),
            type_id
        ))

        db.commit()

        if request.is_json:
            return jsonify({'message': 'Extended type updated successfully'}), 200
        else:
            flash('Extended type updated successfully', 'success')
            return redirect(url_for('planning.manage_types'))

    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'An extended type with this name already exists'}), 409
        return jsonify({'error': str(e)}), 500


@planning_bp.route('/types/<int:type_id>', methods=['DELETE'])
def delete_extended_type(type_id):
    """Soft delete an extended activity type (set is_active = 0)"""
    db = get_db()

    # Check if type exists
    cursor = db.execute('SELECT * FROM extended_activity_types WHERE id = ?', (type_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Extended type not found'}), 404

    # Soft delete (set is_active = 0)
    db.execute('''
        UPDATE extended_activity_types
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (type_id,))

    db.commit()

    if request.is_json:
        return jsonify({'message': 'Extended type deleted successfully'}), 200
    else:
        flash('Extended type deleted successfully', 'success')
        return redirect(url_for('planning.manage_types'))
