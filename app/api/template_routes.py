"""REST API routes for training templates and their segments"""

from flask import request, jsonify
from flask_login import login_required
from app.api import api_bp
from app.repositories.training_template_repository import TrainingTemplateRepository
from app.services.access_control_service import get_viewing_user_id
from app.utils.errors import ValidationError, AppError, DatabaseError


def _repo():
    return TrainingTemplateRepository()


# ── Templates ─────────────────────────────────────────────────────────────────

@api_bp.route('/templates/', methods=['GET'])
@login_required
def list_templates():
    user_id = get_viewing_user_id()
    sport_type = request.args.get('sport_type') or None
    rows = _repo().get_templates(user_id, sport_type=sport_type)
    return jsonify([dict(r) for r in rows])


@api_bp.route('/templates/', methods=['POST'])
@login_required
def create_template():
    user_id = get_viewing_user_id()
    data = request.get_json(force=True) or {}
    try:
        template = _repo().create_template(data, user_id)
        return jsonify(dict(template)), 201
    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    user_id = get_viewing_user_id()
    try:
        template = _repo().get_template_with_segments(template_id, user_id)
        return jsonify(template)
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    user_id = get_viewing_user_id()
    data = request.get_json(force=True) or {}
    try:
        template = _repo().update_template(template_id, user_id, data)
        return jsonify(dict(template))
    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    user_id = get_viewing_user_id()
    try:
        _repo().delete_template(template_id, user_id)
        return jsonify({'success': True})
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


# ── Segments ──────────────────────────────────────────────────────────────────

@api_bp.route('/templates/<int:template_id>/segments', methods=['POST'])
@login_required
def add_segment(template_id):
    user_id = get_viewing_user_id()
    data = request.get_json(force=True) or {}
    try:
        segment = _repo().create_segment(template_id, user_id, data)
        return jsonify(dict(segment)), 201
    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>/segments/<int:segment_id>', methods=['PUT'])
@login_required
def update_segment(template_id, segment_id):
    user_id = get_viewing_user_id()
    data = request.get_json(force=True) or {}
    try:
        segment = _repo().update_segment(segment_id, template_id, user_id, data)
        return jsonify(dict(segment))
    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>/segments/<int:segment_id>', methods=['DELETE'])
@login_required
def delete_segment(template_id, segment_id):
    user_id = get_viewing_user_id()
    try:
        _repo().delete_segment(segment_id, template_id, user_id)
        return jsonify({'success': True})
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/templates/<int:template_id>/segments/reorder', methods=['POST'])
@login_required
def reorder_segments(template_id):
    user_id = get_viewing_user_id()
    data = request.get_json(force=True) or {}
    ordered_ids = data.get('ordered_ids', [])
    if not isinstance(ordered_ids, list):
        return jsonify({'error': 'ordered_ids must be a list'}), 400
    try:
        _repo().reorder_segments(template_id, user_id, ordered_ids)
        return jsonify({'success': True})
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
