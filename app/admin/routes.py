from flask import render_template, request, jsonify, redirect, url_for, flash
from app.admin import admin_bp
from app.database import get_db, get_extended_types, validate_sport_type
from collections import defaultdict


@admin_bp.route('/')
def index():
    """Admin dashboard"""
    return render_template('admin/index.html')


@admin_bp.route('/types')
def manage_types():
    """Extended activity types management page"""
    extended_types = get_extended_types()

    # Group by base_sport_type for display
    types_by_base = defaultdict(list)
    for ext_type in extended_types:
        types_by_base[ext_type['base_sport_type']].append(ext_type)

    return render_template('admin/manage_types.html',
                           types_by_base=dict(types_by_base),
                           all_types=extended_types)


@admin_bp.route('/types', methods=['POST'])
def create_extended_type():
    """Create a new extended activity type"""
    db = get_db()
    data = request.get_json() if request.is_json else request.form

    # Validate required fields
    if not data.get('base_sport_type') or not data.get('custom_name'):
        return jsonify({'error': 'Base sport type and custom name are required'}), 400

    # Validate base_sport_type exists in standard types
    if not validate_sport_type(data['base_sport_type']):
        return jsonify({'error': f'Invalid base_sport_type: {data["base_sport_type"]}'}), 400

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
            return redirect(url_for('admin.manage_types'))

    except Exception as e:
        # Handle unique constraint violation (duplicate custom_name)
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'An extended type with this name already exists'}), 409
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/types/<int:type_id>', methods=['PUT', 'POST'])
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
            return redirect(url_for('admin.manage_types'))

    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            return jsonify({'error': 'An extended type with this name already exists'}), 409
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/types/<int:type_id>', methods=['DELETE'])
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
        return redirect(url_for('admin.manage_types'))
