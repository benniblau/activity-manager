"""Unified API routes for extended activity type management"""

from flask import request, jsonify
from app.api import api_bp
from app.repositories import TypeRepository
from app.utils.errors import ValidationError, AppError


@api_bp.route('/extended-types', methods=['GET'])
def get_extended_types():
    """Get all extended activity types

    Query parameters:
        - is_active: Filter by active status (true/false)
        - grouped: Return grouped by base sport type (true/false)
    """
    try:
        type_repo = TypeRepository()

        # Parse query parameters
        is_active_param = request.args.get('is_active')
        grouped = request.args.get('grouped', 'false').lower() == 'true'

        # Determine is_active filter
        if is_active_param is not None:
            is_active = is_active_param.lower() == 'true'
        else:
            is_active = True  # Default to active only

        # Get types
        if grouped:
            types = type_repo.get_extended_types_grouped_by_base(is_active=is_active)
        else:
            types = type_repo.get_extended_types(is_active=is_active)

        return jsonify(types), 200

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/extended-types/<int:type_id>', methods=['GET'])
def get_extended_type(type_id):
    """Get a single extended activity type by ID"""
    try:
        type_repo = TypeRepository()
        extended_type = type_repo.get_by_id('extended_activity_types', type_id)

        if not extended_type:
            raise ValidationError(f'Extended type {type_id} not found', status_code=404)

        return jsonify(extended_type), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/extended-types', methods=['POST'])
def create_extended_type():
    """Create a new extended activity type

    Request body (JSON):
        - base_sport_type: Base sport type (required)
        - custom_name: Custom name for this type (required)
        - description: Description (optional)
        - icon_override: Font Awesome icon override (optional)
        - color_class: Bootstrap color class (optional)
        - display_order: Display order (optional)
    """
    try:
        data = request.get_json()

        if not data:
            raise ValidationError('No data provided')

        # Create extended type using repository
        type_repo = TypeRepository()
        extended_type = type_repo.create_extended_type(data)

        return jsonify({
            'message': 'Extended type created successfully',
            'type': extended_type
        }), 201

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/extended-types/<int:type_id>', methods=['PUT', 'PATCH'])
def update_extended_type(type_id):
    """Update an extended activity type

    Request body (JSON): Fields to update
    """
    try:
        data = request.get_json()

        if not data:
            raise ValidationError('No data provided')

        # Update extended type using repository
        type_repo = TypeRepository()
        extended_type = type_repo.update_extended_type(type_id, data)

        return jsonify({
            'message': 'Extended type updated successfully',
            'type': extended_type
        }), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/extended-types/<int:type_id>', methods=['DELETE'])
def delete_extended_type(type_id):
    """Soft delete an extended activity type (set is_active = 0)"""
    try:
        type_repo = TypeRepository()
        type_repo.delete_extended_type(type_id)

        return jsonify({
            'message': 'Extended type deleted successfully'
        }), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/extended-types/<int:type_id>/activate', methods=['POST'])
def activate_extended_type(type_id):
    """Reactivate a soft-deleted extended activity type"""
    try:
        type_repo = TypeRepository()

        # Check if type exists
        existing = type_repo.get_by_id('extended_activity_types', type_id)
        if not existing:
            raise ValidationError(f'Extended type {type_id} not found', status_code=404)

        # Reactivate
        type_repo.update('extended_activity_types', {'is_active': True}, id_value=type_id)
        extended_type = type_repo.get_by_id('extended_activity_types', type_id)

        return jsonify({
            'message': 'Extended type activated successfully',
            'type': extended_type
        }), 200

    except ValidationError as e:
        return jsonify(e.to_dict()), e.status_code
    except AppError as e:
        return jsonify(e.to_dict()), e.status_code


@api_bp.route('/standard-types', methods=['GET'])
def get_standard_types():
    """Get all standard activity types

    Query parameters:
        - grouped: Return grouped by category (true/false)
    """
    try:
        type_repo = TypeRepository()
        grouped = request.args.get('grouped', 'false').lower() == 'true'

        if grouped:
            types = type_repo.get_types_by_category()
        else:
            types = type_repo.get_standard_types()

        return jsonify(types), 200

    except AppError as e:
        return jsonify(e.to_dict()), e.status_code
