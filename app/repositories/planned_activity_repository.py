"""Repository for planned activity (training plan) data"""

from datetime import datetime
from .base import BaseRepository
from app.utils.errors import DatabaseError


class PlannedActivityRepository(BaseRepository):
    """Repository for planned activity CRUD and ordering operations"""

    def get_by_day(self, day_date, user_id):
        """Get planned activities for a specific day, ordered by sort_order"""
        return self.fetchall('''
            SELECT p.*,
                   s.display_name as sport_display_name,
                   s.icon as sport_icon,
                   s.color as sport_color,
                   e.custom_name as extended_name,
                   e.color_class as extended_color,
                   a.name as matched_activity_name,
                   a.sport_type as matched_sport_type,
                   a.distance as matched_distance,
                   a.moving_time as matched_moving_time,
                   tt.name as template_name,
                   tt.sport_type as template_sport_type
            FROM planned_activities p
            LEFT JOIN standard_activity_types s ON p.sport_type = s.name
            LEFT JOIN extended_activity_types e ON p.extended_type_id = e.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
            LEFT JOIN training_templates tt ON p.template_id = tt.id
            WHERE p.user_id = ? AND p.day_date = ?
            ORDER BY p.sort_order ASC, p.id ASC
        ''', (user_id, day_date))

    def get_by_week(self, start_date, end_date, user_id):
        """Get planned activities for a date range, ordered by date then sort_order"""
        return self.fetchall('''
            SELECT p.*,
                   s.display_name as sport_display_name,
                   s.icon as sport_icon,
                   s.color as sport_color,
                   e.custom_name as extended_name,
                   e.color_class as extended_color,
                   a.name as matched_activity_name,
                   a.sport_type as matched_sport_type,
                   a.distance as matched_distance,
                   a.moving_time as matched_moving_time,
                   tt.name as template_name,
                   tt.sport_type as template_sport_type
            FROM planned_activities p
            LEFT JOIN standard_activity_types s ON p.sport_type = s.name
            LEFT JOIN extended_activity_types e ON p.extended_type_id = e.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
            LEFT JOIN training_templates tt ON p.template_id = tt.id
            WHERE p.user_id = ? AND p.day_date >= ? AND p.day_date <= ?
            ORDER BY p.day_date ASC, p.sort_order ASC, p.id ASC
        ''', (user_id, start_date, end_date))

    def create(self, data):
        """Insert a new planned activity; auto-assigns sort_order as max+1 for the day"""
        user_id = data['user_id']
        day_date = data['day_date']

        # Determine next sort_order for this day
        result = self.fetchone(
            'SELECT MAX(sort_order) as max_order FROM planned_activities WHERE user_id = ? AND day_date = ?',
            (user_id, day_date)
        )
        max_order = result['max_order'] if result and result['max_order'] is not None else -1
        data['sort_order'] = max_order + 1

        return self.insert('planned_activities', data)

    def update(self, plan_id, user_id, data):
        """Update a planned activity (only if it belongs to user)

        Returns:
            Number of rows affected, or 0 if not found/unauthorized
        """
        # Ensure updated_at is set
        data['updated_at'] = datetime.utcnow().isoformat()

        # Build SET clause
        allowed_fields = {
            'sport_type', 'extended_type_id', 'planned_distance', 'planned_duration',
            'notes', 'matched_activity_id', 'sort_order', 'day_date', 'template_id', 'updated_at'
        }
        update_data = {k: v for k, v in data.items() if k in allowed_fields}

        if not update_data:
            return 0

        set_clause = ', '.join(f'{k} = ?' for k in update_data.keys())
        values = list(update_data.values()) + [plan_id, user_id]

        try:
            db = self.get_db()
            cursor = db.execute(
                f'UPDATE planned_activities SET {set_clause} WHERE id = ? AND user_id = ?',
                values
            )
            db.commit()
            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(f"Update failed: {str(e)}", e)

    def delete(self, plan_id, user_id):
        """Hard delete a planned activity (only if it belongs to user)

        Returns:
            Number of rows deleted
        """
        try:
            db = self.get_db()
            cursor = db.execute(
                'DELETE FROM planned_activities WHERE id = ? AND user_id = ?',
                (plan_id, user_id)
            )
            db.commit()
            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(f"Delete failed: {str(e)}", e)

    def duplicate(self, plan_id, user_id):
        """Copy a planned activity and append it at end of the same day

        Returns:
            ID of the new row, or None if source not found
        """
        source = self.fetchone(
            'SELECT * FROM planned_activities WHERE id = ? AND user_id = ?',
            (plan_id, user_id)
        )
        if not source:
            return None

        new_data = {
            'user_id': source['user_id'],
            'day_date': source['day_date'],
            'sport_type': source['sport_type'],
            'extended_type_id': source['extended_type_id'],
            'planned_distance': source['planned_distance'],
            'planned_duration': source['planned_duration'],
            'notes': source['notes'],
            'matched_activity_id': None,  # new item is unmatched
        }
        return self.create(new_data)

    def reorder(self, day_date, user_id, ordered_ids):
        """Batch-update sort_order for all items in a day

        Args:
            day_date: YYYY-MM-DD string
            user_id: User ID (for access control)
            ordered_ids: List of plan IDs in desired order

        Returns:
            True on success
        """
        try:
            db = self.get_db()
            self._apply_order(db, user_id, day_date, ordered_ids, datetime.utcnow().isoformat())
            db.commit()
            return True
        except Exception as e:
            raise DatabaseError(f"Reorder failed: {str(e)}", e)

    def move_to_day(self, plan_id, user_id, to_day, to_ordered_ids=None,
                    from_day=None, from_ordered_ids=None):
        """Move a planned activity to another day and re-apply sort order on both days

        A match points at an activity that happened on a specific day, so the
        matched activity is dropped when it does not belong to the target day.

        Args:
            plan_id: Plan ID to move
            user_id: User ID (for access control)
            to_day: Target day as YYYY-MM-DD
            to_ordered_ids: Plan IDs of the target day in desired order (incl. plan_id)
            from_day: Source day as YYYY-MM-DD (optional)
            from_ordered_ids: Plan IDs remaining on the source day in desired order

        Returns:
            Dict with resulting `day_date` and `matched_activity_id`,
            or None if the plan was not found / not owned by the user
        """
        source = self.fetchone(
            'SELECT day_date, matched_activity_id FROM planned_activities WHERE id = ? AND user_id = ?',
            (plan_id, user_id)
        )
        if not source:
            return None

        matched_id = source['matched_activity_id']
        if matched_id is not None and source['day_date'] != to_day:
            matched = self.fetchone('SELECT day_date FROM activities WHERE id = ?', (matched_id,))
            if not matched or matched['day_date'] != to_day:
                matched_id = None

        now = datetime.utcnow().isoformat()
        try:
            db = self.get_db()
            db.execute(
                '''UPDATE planned_activities
                   SET day_date = ?, matched_activity_id = ?, updated_at = ?
                   WHERE id = ? AND user_id = ?''',
                (to_day, matched_id, now, plan_id, user_id)
            )
            self._apply_order(db, user_id, to_day, to_ordered_ids or [], now)
            if from_day and from_day != to_day:
                self._apply_order(db, user_id, from_day, from_ordered_ids or [], now)
            db.commit()
            return {'day_date': to_day, 'matched_activity_id': matched_id}
        except Exception as e:
            raise DatabaseError(f"Move failed: {str(e)}", e)

    def _apply_order(self, db, user_id, day_date, ordered_ids, timestamp):
        """Write sort_order for the given day; ignores IDs not on that day"""
        for index, plan_id in enumerate(ordered_ids):
            db.execute(
                '''UPDATE planned_activities
                   SET sort_order = ?, updated_at = ?
                   WHERE id = ? AND user_id = ? AND day_date = ?''',
                (index, timestamp, plan_id, user_id, day_date)
            )
