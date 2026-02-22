"""REST API endpoints for planned activities (training plan feature)"""

from flask import request, jsonify
from flask_login import login_required
from app.api import api_bp
from app.repositories import PlannedActivityRepository
from app.services.access_control_service import get_viewing_user_id
from app.utils.errors import DatabaseError


@api_bp.route('/plan/', methods=['POST'])
@login_required
def create_plan():
    """Create a new planned activity"""
    viewing_user_id = get_viewing_user_id()
    if not viewing_user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}

    day_date = data.get('day_date', '').strip()
    if not day_date:
        return jsonify({'error': 'day_date is required'}), 400

    plan_data = {
        'user_id': viewing_user_id,
        'day_date': day_date,
        'sport_type': data.get('sport_type') or None,
        'extended_type_id': data.get('extended_type_id') or None,
        'planned_distance': data.get('planned_distance') or None,
        'planned_duration': data.get('planned_duration') or None,
        'notes': data.get('notes') or None,
    }

    try:
        repo = PlannedActivityRepository()
        new_id = repo.create(plan_data)
        items = repo.get_by_day(day_date, viewing_user_id)
        return jsonify({'id': new_id, 'items': items}), 201
    except DatabaseError as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/plan/<int:plan_id>', methods=['PUT'])
@login_required
def update_plan(plan_id):
    """Update a planned activity"""
    viewing_user_id = get_viewing_user_id()
    if not viewing_user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}

    allowed = {
        'sport_type', 'extended_type_id', 'planned_distance', 'planned_duration',
        'notes', 'matched_activity_id', 'day_date'
    }
    update_data = {k: data.get(k) for k in allowed if k in data}

    try:
        repo = PlannedActivityRepository()
        rows = repo.update(plan_id, viewing_user_id, update_data)
        if rows == 0:
            return jsonify({'error': 'Not found or unauthorized'}), 404
        return jsonify({'success': True}), 200
    except DatabaseError as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/plan/<int:plan_id>', methods=['DELETE'])
@login_required
def delete_plan(plan_id):
    """Delete a planned activity"""
    viewing_user_id = get_viewing_user_id()
    if not viewing_user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        repo = PlannedActivityRepository()
        rows = repo.delete(plan_id, viewing_user_id)
        if rows == 0:
            return jsonify({'error': 'Not found or unauthorized'}), 404
        return jsonify({'success': True}), 200
    except DatabaseError as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/plan/<int:plan_id>/duplicate', methods=['POST'])
@login_required
def duplicate_plan(plan_id):
    """Duplicate a planned activity"""
    viewing_user_id = get_viewing_user_id()
    if not viewing_user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        repo = PlannedActivityRepository()
        new_id = repo.duplicate(plan_id, viewing_user_id)
        if new_id is None:
            return jsonify({'error': 'Not found or unauthorized'}), 404

        # Return updated day list
        source = repo.fetchone(
            'SELECT day_date FROM planned_activities WHERE id = ?', (new_id,)
        )
        items = repo.get_by_day(source['day_date'], viewing_user_id) if source else []
        return jsonify({'id': new_id, 'items': items}), 201
    except DatabaseError as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/plan/reorder', methods=['POST'])
@login_required
def reorder_plan():
    """Batch reorder planned activities within a day"""
    viewing_user_id = get_viewing_user_id()
    if not viewing_user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    day_date = data.get('day_date', '').strip()
    ordered_ids = data.get('ordered_ids', [])

    if not day_date or not isinstance(ordered_ids, list):
        return jsonify({'error': 'day_date and ordered_ids are required'}), 400

    try:
        repo = PlannedActivityRepository()
        repo.reorder(day_date, viewing_user_id, ordered_ids)
        return jsonify({'success': True}), 200
    except DatabaseError as e:
        return jsonify({'error': str(e)}), 500
