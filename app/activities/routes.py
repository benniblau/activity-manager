from flask import request, jsonify
from app.activities import activities_bp
from app.repositories import ActivityRepository
from app.services import StravaService
from app.auth.routes import get_strava_client
from app.utils.errors import (
    ActivityNotFoundError,
    ValidationError,
    StravaAPIError,
    AppError
)


@activities_bp.route('/', methods=['GET'])
def get_activities():
    """
    Get all activities with optional filtering.

    Query parameters:
        - sport_type: Filter by sport type (e.g., 'Run', 'Ride')
        - start_date: Filter activities after this date (ISO format)
        - end_date: Filter activities before this date (ISO format)
        - day_date: Filter by specific day
        - gear_id: Filter by gear
        - extended_type_id: Filter by extended type
        - limit: Maximum number of activities to return
        - offset: Number of activities to skip
    """
    activity_repo = ActivityRepository()

    # Build filters from query params
    filters = {}
    if request.args.get('sport_type'):
        filters['sport_type'] = request.args.get('sport_type')
    if request.args.get('day_date'):
        filters['day_date'] = request.args.get('day_date')
    if request.args.get('start_date'):
        filters['start_date'] = request.args.get('start_date')
    if request.args.get('end_date'):
        filters['end_date'] = request.args.get('end_date')
    if request.args.get('gear_id'):
        filters['gear_id'] = request.args.get('gear_id')
    if request.args.get('extended_type_id'):
        filters['extended_type_id'] = request.args.get('extended_type_id', type=int)

    # Pagination
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int, default=0)

    # Get activities
    activities = activity_repo.get_activities(filters=filters, limit=limit, offset=offset)

    return jsonify({
        'count': len(activities),
        'activities': activities
    })


@activities_bp.route('/<int:activity_id>', methods=['GET'])
def get_activity(activity_id):
    """Get a single activity by ID"""
    try:
        activity_repo = ActivityRepository()
        activity = activity_repo.get_activity(activity_id)

        if not activity:
            raise ActivityNotFoundError(activity_id)

        return jsonify(activity)
    except ActivityNotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@activities_bp.route('/', methods=['POST'])
def create_activity():
    """
    Create a new activity.

    Request body should contain activity data (JSON).
    Required fields: name, sport_type, start_date_local, elapsed_time
    """
    try:
        data = request.get_json()

        if not data:
            raise ValidationError('No data provided')

        # Validate required fields
        required_fields = ['name', 'sport_type', 'start_date_local', 'elapsed_time']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise ValidationError(f'Missing required fields: {", ".join(missing_fields)}')

        # Set defaults
        if 'start_date' not in data:
            data['start_date'] = data['start_date_local']
        if 'moving_time' not in data:
            data['moving_time'] = data['elapsed_time']
        if 'manual' not in data:
            data['manual'] = True

        # Create activity
        activity_repo = ActivityRepository()
        activity = activity_repo.create_activity(data)

        return jsonify({
            'message': 'Activity created successfully',
            'activity': activity
        }), 201

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@activities_bp.route('/<int:activity_id>', methods=['PUT'])
def update_activity(activity_id):
    """
    Update an existing activity.

    Request body should contain fields to update (JSON).
    """
    try:
        data = request.get_json()

        if not data:
            raise ValidationError('No data provided')

        # Remove id if present
        data.pop('id', None)

        # Update activity
        activity_repo = ActivityRepository()
        activity = activity_repo.update_activity(activity_id, data)

        return jsonify({
            'message': 'Activity updated successfully',
            'activity': activity
        })

    except ActivityNotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@activities_bp.route('/<int:activity_id>', methods=['DELETE'])
def delete_activity(activity_id):
    """Delete an activity"""
    try:
        activity_repo = ActivityRepository()
        activity_repo.delete_activity(activity_id)

        return jsonify({'message': 'Activity deleted successfully'})

    except ActivityNotFoundError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


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
        # Get authenticated Strava client
        client = get_strava_client()

        # Parse query parameters
        limit = request.args.get('limit', 30, type=int)
        after = request.args.get('after', type=int)
        before = request.args.get('before', type=int)

        if limit > 200:
            limit = 200

        # Use StravaService to perform sync
        strava_service = StravaService(client)
        result = strava_service.sync_activities(limit=limit, after=after, before=before)

        return jsonify(result)

    except StravaAPIError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
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
    try:
        # Build filters from query params
        filters = {}
        if request.args.get('sport_type'):
            filters['sport_type'] = request.args.get('sport_type')
        if request.args.get('start_date'):
            filters['start_date'] = request.args.get('start_date')
        if request.args.get('end_date'):
            filters['end_date'] = request.args.get('end_date')

        # Get stats from repository
        activity_repo = ActivityRepository()
        stats = activity_repo.get_stats(filters=filters)

        return jsonify(stats)

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
