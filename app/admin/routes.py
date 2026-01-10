from flask import render_template, request, jsonify, redirect, url_for, flash
from app.admin import admin_bp
from app.repositories import TypeRepository
from app.utils.errors import ValidationError, AppError


@admin_bp.route('/')
def index():
    """Admin dashboard"""
    return render_template('admin/index.html')


@admin_bp.route('/types')
def manage_types():
    """Extended activity types management page"""
    type_repo = TypeRepository()

    # Get extended types grouped by base sport type
    types_by_base = type_repo.get_extended_types_grouped_by_base()
    all_types = type_repo.get_extended_types()

    return render_template('admin/manage_types.html',
                           types_by_base=types_by_base,
                           all_types=all_types)


@admin_bp.route('/types', methods=['POST'])
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
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))


@admin_bp.route('/types/<int:type_id>', methods=['PUT', 'POST'])
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
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))


@admin_bp.route('/types/<int:type_id>', methods=['DELETE'])
def delete_extended_type(type_id):
    """Soft delete an extended activity type (set is_active = 0)"""
    try:
        type_repo = TypeRepository()
        type_repo.delete_extended_type(type_id)

        if request.is_json:
            return jsonify({'message': 'Extended type deleted successfully'}), 200
        else:
            flash('Extended type deleted successfully', 'success')
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
