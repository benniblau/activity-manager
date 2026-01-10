from flask import render_template, request, jsonify, redirect, url_for, session, flash
from app.planning import planning_bp
from app.repositories import (
    PlanningRepository,
    ActivityRepository,
    TypeRepository,
    DayRepository
)
from app.utils.errors import (
    PlannedActivityNotFoundError,
    ValidationError,
    InvalidOperationError,
    AppError
)
from datetime import datetime, timedelta
from collections import defaultdict


@planning_bp.route('/')
def index():
    """Main planning calendar view (daily list)"""
    # Initialize repositories
    planning_repo = PlanningRepository()
    activity_repo = ActivityRepository()
    type_repo = TypeRepository()

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
        planned_activities_list = planning_repo.get_planned_activities(sorted_days[0], sorted_days[-1])
    else:
        planned_activities_list = []

    # Group planned activities by date
    planned_by_day = defaultdict(list)
    for planned in planned_activities_list:
        planned_by_day[planned['date']].append(planned)

    # Fetch actual activities for the same date range
    if sorted_days:
        filters = {
            'start_date': sorted_days[0],
            'end_date': sorted_days[-1]
        }
        activities = activity_repo.get_activities(filters=filters)
    else:
        activities = []

    # Group activities by day using day_date field
    activities_by_day = defaultdict(list)
    for activity in activities:
        day_date = activity.get('day_date')
        if day_date:
            activities_by_day[day_date].append(activity)

    # Fetch all extended types for dropdowns
    extended_types = type_repo.get_extended_types()

    # Get standard types grouped by category
    standard_types_by_category = type_repo.get_types_by_category()

    # Get distinct sport types for filter
    all_activities = activity_repo.get_activities()
    sport_types = sorted(set(act['sport_type'] for act in all_activities if act.get('sport_type')))

    return render_template('planning.html',
                           sorted_days=sorted_days,
                           planned_by_day=dict(planned_by_day),
                           activities_by_day=dict(activities_by_day),
                           extended_types=extended_types,
                           standard_types_by_category=standard_types_by_category,
                           sport_types=sport_types,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_days=total_days,
                           today=today.strftime('%Y-%m-%d'))


@planning_bp.route('/activity', methods=['POST'])
def create_planned_activity():
    """Create a new planned activity"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Create planned activity using repository
        planning_repo = PlanningRepository()
        planned = planning_repo.create_planned_activity(data)

        if request.is_json:
            return jsonify({
                'id': planned['id'],
                'message': 'Planned activity created successfully'
            }), 201
        else:
            flash('Planned activity created successfully', 'success')
            return redirect(url_for('planning.index'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>', methods=['PUT', 'POST'])
def update_planned_activity(planned_id):
    """Update a planned activity"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Update planned activity using repository
        planning_repo = PlanningRepository()
        planning_repo.update_planned_activity(planned_id, data)

        if request.is_json:
            return jsonify({'message': 'Planned activity updated successfully'}), 200
        else:
            flash('Planned activity updated successfully', 'success')
            return redirect(url_for('planning.index'))

    except PlannedActivityNotFoundError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>', methods=['DELETE'])
def delete_planned_activity(planned_id):
    """Delete a planned activity"""
    try:
        planning_repo = PlanningRepository()
        planning_repo.delete_planned_activity(planned_id)

        if request.is_json:
            return jsonify({'message': 'Planned activity deleted successfully'}), 200
        else:
            flash('Planned activity deleted successfully', 'success')
            return redirect(url_for('planning.index'))

    except PlannedActivityNotFoundError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/copy', methods=['POST'])
def copy_planned_activity(planned_id):
    """Copy a planned activity to other dates"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Get target dates
        target_dates = data.get('target_dates', [])

        # Copy using repository
        planning_repo = PlanningRepository()
        copied_count = planning_repo.copy_planned_activity(planned_id, target_dates)

        if request.is_json:
            return jsonify({
                'message': f'Copied to {copied_count} dates',
                'count': copied_count
            }), 201
        else:
            flash(f'Copied to {copied_count} dates successfully', 'success')
            return redirect(url_for('planning.index'))

    except PlannedActivityNotFoundError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/match/<int:activity_id>', methods=['POST'])
def match_planned_to_actual(planned_id, activity_id):
    """Link a planned activity to an actual activity"""
    try:
        planning_repo = PlanningRepository()
        planning_repo.match_to_actual(planned_id, activity_id)

        if request.is_json:
            return jsonify({'message': 'Activities matched successfully'}), 200
        else:
            flash('Activities matched successfully', 'success')
            return redirect(url_for('planning.index'))

    except PlannedActivityNotFoundError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except InvalidOperationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/activity/<int:planned_id>/match', methods=['DELETE'])
def unmatch_planned_activity(planned_id):
    """Unlink a planned activity from its matched actual activity"""
    try:
        planning_repo = PlanningRepository()
        planning_repo.unmatch_activity(planned_id)

        if request.is_json:
            return jsonify({'message': 'Activities unmatched successfully'}), 200
        else:
            flash('Activities unmatched successfully', 'success')
            return redirect(url_for('planning.index'))

    except PlannedActivityNotFoundError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.index'))


@planning_bp.route('/types')
def manage_types():
    """Extended activity types management page"""
    type_repo = TypeRepository()

    # Get extended types grouped by base sport type
    types_by_base = type_repo.get_extended_types_grouped_by_base()
    all_types = type_repo.get_extended_types()

    return render_template('planning_types.html',
                           types_by_base=types_by_base,
                           all_types=all_types)


@planning_bp.route('/types', methods=['POST'])
def create_extended_type():
    """Create a new extended activity type"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Create extended type using repository
        type_repo = TypeRepository()
        extended_type = type_repo.create_extended_type(data)

        if request.is_json:
            return jsonify({
                'id': extended_type['id'],
                'message': 'Extended type created successfully'
            }), 201
        else:
            flash('Extended type created successfully', 'success')
            return redirect(url_for('planning.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))


@planning_bp.route('/types/<int:type_id>', methods=['PUT', 'POST'])
def update_extended_type(type_id):
    """Update an extended activity type"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Update extended type using repository
        type_repo = TypeRepository()
        type_repo.update_extended_type(type_id, data)

        if request.is_json:
            return jsonify({'message': 'Extended type updated successfully'}), 200
        else:
            flash('Extended type updated successfully', 'success')
            return redirect(url_for('planning.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))


@planning_bp.route('/types/<int:type_id>', methods=['DELETE'])
def delete_extended_type(type_id):
    """Soft delete an extended activity type (set is_active = 0)"""
    try:
        type_repo = TypeRepository()
        type_repo.delete_extended_type(type_id)

        if request.is_json:
            return jsonify({'message': 'Extended type deleted successfully'}), 200
        else:
            flash('Extended type deleted successfully', 'success')
            return redirect(url_for('planning.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('planning.manage_types'))
