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
                   a.moving_time as matched_moving_time
            FROM planned_activities p
            LEFT JOIN standard_activity_types s ON p.sport_type = s.name
            LEFT JOIN extended_activity_types e ON p.extended_type_id = e.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
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
                   a.moving_time as matched_moving_time
            FROM planned_activities p
            LEFT JOIN standard_activity_types s ON p.sport_type = s.name
            LEFT JOIN extended_activity_types e ON p.extended_type_id = e.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
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
            'notes', 'matched_activity_id', 'sort_order', 'day_date', 'updated_at'
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
            for index, plan_id in enumerate(ordered_ids):
                db.execute(
                    '''UPDATE planned_activities
                       SET sort_order = ?, updated_at = ?
                       WHERE id = ? AND user_id = ? AND day_date = ?''',
                    (index, datetime.utcnow().isoformat(), plan_id, user_id, day_date)
                )
            db.commit()
            return True
        except Exception as e:
            raise DatabaseError(f"Reorder failed: {str(e)}", e)
