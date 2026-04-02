"""Repository for training template and segment data"""

from datetime import datetime
from .base import BaseRepository
from app.utils.errors import DatabaseError, ValidationError, AppError


class TrainingTemplateRepository(BaseRepository):
    """Repository for training template CRUD and segment management"""

    # ── Templates ─────────────────────────────────────────────────────────────

    def get_templates(self, user_id, sport_type=None):
        """List active templates for a user, optionally filtered by sport_type"""
        if sport_type:
            return self.fetchall(
                '''SELECT t.*, COUNT(s.id) as segment_count
                   FROM training_templates t
                   LEFT JOIN template_segments s ON s.template_id = t.id
                   WHERE t.user_id = ? AND t.is_active = 1 AND t.sport_type = ?
                   GROUP BY t.id
                   ORDER BY t.name''',
                (user_id, sport_type)
            )
        return self.fetchall(
            '''SELECT t.*, COUNT(s.id) as segment_count
               FROM training_templates t
               LEFT JOIN template_segments s ON s.template_id = t.id
               WHERE t.user_id = ? AND t.is_active = 1
               GROUP BY t.id
               ORDER BY t.name''',
            (user_id,)
        )

    def get_template(self, template_id, user_id):
        """Fetch a single template, raises AppError(404) if not found/unauthorized"""
        row = self.fetchone(
            'SELECT * FROM training_templates WHERE id = ? AND user_id = ? AND is_active = 1',
            (template_id, user_id)
        )
        if not row:
            raise AppError(f'Training template {template_id} not found', status_code=404)
        return row

    def get_template_with_segments(self, template_id, user_id):
        """Fetch a template with its ordered segments"""
        template = self.get_template(template_id, user_id)
        segments = self.get_segments(template_id)
        result = dict(template)
        result['segments'] = [dict(s) for s in segments]
        return result

    def create_template(self, data, user_id):
        """Create a new training template"""
        name = (data.get('name') or '').strip()
        if not name:
            raise ValidationError('name is required')

        sport_type = data.get('sport_type') or None
        description = data.get('description') or None

        try:
            new_id = self.insert('training_templates', {
                'user_id': user_id,
                'name': name,
                'sport_type': sport_type,
                'description': description,
            })
        except Exception as e:
            if 'UNIQUE' in str(e):
                raise ValidationError(f"A template named '{name}' already exists")
            raise DatabaseError(f'Create template failed: {e}', e)

        return self.get_template(new_id, user_id)

    def update_template(self, template_id, user_id, data):
        """Update template fields"""
        # Verify ownership
        self.get_template(template_id, user_id)

        allowed = {'name', 'sport_type', 'description'}
        update_data = {k: v for k, v in data.items() if k in allowed}
        if 'name' in update_data:
            update_data['name'] = (update_data['name'] or '').strip()
            if not update_data['name']:
                raise ValidationError('name is required')
        update_data['updated_at'] = datetime.utcnow().isoformat()

        if len(update_data) <= 1:  # only updated_at
            return self.get_template(template_id, user_id)

        set_clause = ', '.join(f'{k} = ?' for k in update_data.keys())
        values = list(update_data.values()) + [template_id]
        try:
            db = self.get_db()
            db.execute(f'UPDATE training_templates SET {set_clause} WHERE id = ?', values)
            db.commit()
        except Exception as e:
            if 'UNIQUE' in str(e):
                raise ValidationError(f"A template named '{update_data.get('name', '')}' already exists")
            raise DatabaseError(f'Update template failed: {e}', e)

        return self.get_template(template_id, user_id)

    def delete_template(self, template_id, user_id):
        """Soft-delete a template"""
        self.get_template(template_id, user_id)
        try:
            db = self.get_db()
            db.execute(
                "UPDATE training_templates SET is_active = 0, updated_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), template_id)
            )
            db.commit()
        except Exception as e:
            raise DatabaseError(f'Delete template failed: {e}', e)

    # ── Segments ──────────────────────────────────────────────────────────────

    def get_segments(self, template_id):
        """Return segments for a template ordered by sort_order"""
        return self.fetchall(
            'SELECT * FROM template_segments WHERE template_id = ? ORDER BY sort_order ASC, id ASC',
            (template_id,)
        )

    def create_segment(self, template_id, user_id, data):
        """Add a segment to a template"""
        # Verify template ownership
        self.get_template(template_id, user_id)

        label = (data.get('label') or '').strip()
        if not label:
            raise ValidationError('label is required')

        # Auto sort_order = max + 1
        result = self.fetchone(
            'SELECT MAX(sort_order) as max_order FROM template_segments WHERE template_id = ?',
            (template_id,)
        )
        max_order = result['max_order'] if result and result['max_order'] is not None else -1

        new_id = self.insert('template_segments', {
            'template_id': template_id,
            'sort_order': max_order + 1,
            'label': label,
            'distance_meters': data.get('distance_meters') or None,
            'duration_seconds': data.get('duration_seconds') or None,
            'target_pace_sec_per_km': data.get('target_pace_sec_per_km') or None,
            'notes': data.get('notes') or None,
        })
        return self.fetchone('SELECT * FROM template_segments WHERE id = ?', (new_id,))

    def update_segment(self, segment_id, template_id, user_id, data):
        """Update a segment"""
        # Verify template ownership
        self.get_template(template_id, user_id)

        allowed = {'label', 'distance_meters', 'duration_seconds', 'target_pace_sec_per_km', 'notes'}
        update_data = {k: v for k, v in data.items() if k in allowed}

        if 'label' in update_data:
            update_data['label'] = (update_data['label'] or '').strip()
            if not update_data['label']:
                raise ValidationError('label is required')

        if not update_data:
            return self.fetchone('SELECT * FROM template_segments WHERE id = ? AND template_id = ?', (segment_id, template_id))

        set_clause = ', '.join(f'{k} = ?' for k in update_data.keys())
        values = list(update_data.values()) + [segment_id, template_id]
        try:
            db = self.get_db()
            db.execute(
                f'UPDATE template_segments SET {set_clause} WHERE id = ? AND template_id = ?',
                values
            )
            db.commit()
        except Exception as e:
            raise DatabaseError(f'Update segment failed: {e}', e)

        return self.fetchone('SELECT * FROM template_segments WHERE id = ? AND template_id = ?', (segment_id, template_id))

    def delete_segment(self, segment_id, template_id, user_id):
        """Hard-delete a segment"""
        # Verify template ownership
        self.get_template(template_id, user_id)
        try:
            db = self.get_db()
            cursor = db.execute(
                'DELETE FROM template_segments WHERE id = ? AND template_id = ?',
                (segment_id, template_id)
            )
            db.commit()
            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(f'Delete segment failed: {e}', e)

    def reorder_segments(self, template_id, user_id, ordered_ids):
        """Batch-update sort_order for all segments in a template"""
        self.get_template(template_id, user_id)
        try:
            db = self.get_db()
            for index, seg_id in enumerate(ordered_ids):
                db.execute(
                    'UPDATE template_segments SET sort_order = ? WHERE id = ? AND template_id = ?',
                    (index, seg_id, template_id)
                )
            db.commit()
            return True
        except Exception as e:
            raise DatabaseError(f'Reorder segments failed: {e}', e)
