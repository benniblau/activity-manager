from datetime import datetime
from flask import request, jsonify
from app.activities import activities_bp
from app.database import get_db, dict_to_db_values, db_row_to_dict
from app.auth.routes import get_strava_client


@activities_bp.route('/', methods=['GET'])
def get_activities():
    """
    Get all activities with optional filtering.

    Query parameters:
        - sport_type: Filter by sport type (e.g., 'Run', 'Ride')
        - start_date: Filter activities after this date (ISO format)
        - end_date: Filter activities before this date (ISO format)
        - limit: Maximum number of activities to return
        - offset: Number of activities to skip
    """
    db = get_db()

    # Build query
    query = 'SELECT * FROM activities WHERE 1=1'
    params = []

    # Filter by sport type
    sport_type = request.args.get('sport_type')
    if sport_type:
        query += ' AND sport_type = ?'
        params.append(sport_type)

    # Filter by date range
    start_date = request.args.get('start_date')
    if start_date:
        query += ' AND start_date >= ?'
        params.append(start_date)

    end_date = request.args.get('end_date')
    if end_date:
        query += ' AND start_date <= ?'
        params.append(end_date)

    # Order by start date (most recent first)
    query += ' ORDER BY start_date DESC'

    # Pagination
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int, default=0)

    if limit:
        query += ' LIMIT ?'
        params.append(limit)

    if offset:
        query += ' OFFSET ?'
        params.append(offset)

    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    activities = [db_row_to_dict(row) for row in rows]

    return jsonify({
        'count': len(activities),
        'activities': activities
    })


@activities_bp.route('/<int:activity_id>', methods=['GET'])
def get_activity(activity_id):
    """Get a single activity by ID"""
    db = get_db()
    cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
    row = cursor.fetchone()

    if not row:
        return jsonify({'error': 'Activity not found'}), 404

    return jsonify(db_row_to_dict(row))


@activities_bp.route('/', methods=['POST'])
def create_activity():
    """
    Create a new activity.

    Request body should contain activity data (JSON).
    Required fields: name, sport_type, start_date_local, elapsed_time
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['name', 'sport_type', 'start_date_local', 'elapsed_time']
    missing_fields = [field for field in required_fields if field not in data]

    if missing_fields:
        return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

    try:
        # Prepare data for database
        db_data = dict_to_db_values(data)

        # Set defaults
        if 'start_date' not in db_data:
            db_data['start_date'] = db_data['start_date_local']
        if 'moving_time' not in db_data:
            db_data['moving_time'] = db_data['elapsed_time']
        if 'manual' not in db_data:
            db_data['manual'] = 1

        # Build insert query
        columns = ', '.join(db_data.keys())
        placeholders = ', '.join(['?' for _ in db_data])
        query = f'INSERT INTO activities ({columns}) VALUES ({placeholders})'

        db = get_db()
        cursor = db.execute(query, list(db_data.values()))
        db.commit()

        # Get the created activity
        activity_id = cursor.lastrowid
        cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
        row = cursor.fetchone()

        return jsonify({
            'message': 'Activity created successfully',
            'activity': db_row_to_dict(row)
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@activities_bp.route('/<int:activity_id>', methods=['PUT'])
def update_activity(activity_id):
    """
    Update an existing activity.

    Request body should contain fields to update (JSON).
    """
    db = get_db()

    # Check if activity exists
    cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Activity not found'}), 404

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Prepare data for database
        db_data = dict_to_db_values(data)

        # Remove id if present
        db_data.pop('id', None)

        # Add updated timestamp
        db_data['updated_at'] = datetime.utcnow().isoformat()

        # Build update query
        set_clause = ', '.join([f'{key} = ?' for key in db_data.keys()])
        query = f'UPDATE activities SET {set_clause} WHERE id = ?'

        values = list(db_data.values()) + [activity_id]
        db.execute(query, values)
        db.commit()

        # Get the updated activity
        cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
        row = cursor.fetchone()

        return jsonify({
            'message': 'Activity updated successfully',
            'activity': db_row_to_dict(row)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@activities_bp.route('/<int:activity_id>', methods=['DELETE'])
def delete_activity(activity_id):
    """Delete an activity"""
    db = get_db()

    # Check if activity exists
    cursor = db.execute('SELECT * FROM activities WHERE id = ?', (activity_id,))
    if not cursor.fetchone():
        return jsonify({'error': 'Activity not found'}), 404

    try:
        db.execute('DELETE FROM activities WHERE id = ?', (activity_id,))
        db.commit()

        return jsonify({'message': 'Activity deleted successfully'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@activities_bp.route('/sync', methods=['POST'])
def sync_from_strava():
    """
    Sync activities from Strava API.

    Query parameters:
        - limit: Number of activities to fetch (default: 30, max: 200)
        - after: Fetch activities after this timestamp (Unix epoch)
        - before: Fetch activities before this timestamp (Unix epoch)
    """
    try:
        client = get_strava_client()
    except Exception as e:
        return jsonify({'error': str(e)}), 401

    limit = request.args.get('limit', 30, type=int)
    after = request.args.get('after', type=int)
    before = request.args.get('before', type=int)

    if limit > 200:
        limit = 200

    try:
        # Fetch activities from Strava
        strava_activities = client.get_activities(limit=limit, after=after, before=before)

        db = get_db()
        created_count = 0
        updated_count = 0
        errors = []

        for strava_activity in strava_activities:
            try:
                # Convert to dict
                if hasattr(strava_activity, 'to_dict'):
                    activity_data = strava_activity.to_dict()
                else:
                    activity_data = dict(strava_activity)

                activity_id = activity_data.get('id')

                # Check if activity already exists
                cursor = db.execute('SELECT id FROM activities WHERE id = ?', (activity_id,))
                exists = cursor.fetchone()

                # Prepare data
                db_data = dict_to_db_values(activity_data)

                if exists:
                    # Update existing activity (skip for now)
                    updated_count += 1
                else:
                    # Insert new activity
                    columns = ', '.join(db_data.keys())
                    placeholders = ', '.join(['?' for _ in db_data])
                    query = f'INSERT INTO activities ({columns}) VALUES ({placeholders})'
                    db.execute(query, list(db_data.values()))
                    created_count += 1

            except Exception as e:
                errors.append({
                    'activity_id': activity_id,
                    'error': str(e)
                })

        db.commit()

        return jsonify({
            'message': 'Sync completed',
            'created': created_count,
            'updated': updated_count,
            'errors': errors
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@activities_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Get activity statistics.

    Query parameters:
        - sport_type: Filter by sport type
        - start_date: Start of date range
        - end_date: End of date range
    """
    db = get_db()

    # Build query
    query = '''
        SELECT
            COUNT(*) as total_activities,
            SUM(distance) as total_distance,
            SUM(total_elevation_gain) as total_elevation,
            SUM(moving_time) as total_time
        FROM activities WHERE 1=1
    '''
    params = []

    # Apply filters
    sport_type = request.args.get('sport_type')
    if sport_type:
        query += ' AND sport_type = ?'
        params.append(sport_type)

    start_date = request.args.get('start_date')
    if start_date:
        query += ' AND start_date >= ?'
        params.append(start_date)

    end_date = request.args.get('end_date')
    if end_date:
        query += ' AND start_date <= ?'
        params.append(end_date)

    cursor = db.execute(query, params)
    row = cursor.fetchone()

    total_activities = row['total_activities'] or 0
    total_distance = row['total_distance'] or 0
    total_elevation = row['total_elevation'] or 0
    total_time = row['total_time'] or 0

    return jsonify({
        'total_activities': total_activities,
        'total_distance_meters': total_distance,
        'total_distance_km': round(total_distance / 1000, 2),
        'total_elevation_meters': total_elevation,
        'total_time_seconds': total_time,
        'total_time_hours': round(total_time / 3600, 2),
        'average_distance_km': round(total_distance / 1000 / total_activities, 2) if total_activities > 0 else 0
    })
