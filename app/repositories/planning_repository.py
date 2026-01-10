"""Planning repository for managing planned activities"""

from .base import BaseRepository
from app.utils.errors import PlannedActivityNotFoundError, ValidationError, InvalidOperationError


class PlanningRepository(BaseRepository):
    """Repository for planned activity operations"""

    def get_planned_activity(self, planned_id):
        """Get a single planned activity by ID with extended type info

        Args:
            planned_id: Planned activity ID

        Returns:
            Planned activity dictionary

        Raises:
            PlannedActivityNotFoundError: If planned activity doesn't exist
        """
        query = '''
            SELECT
                p.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon,
                ext.base_sport_type as extended_base_type,
                a.name as matched_activity_name
            FROM planned_activities p
            LEFT JOIN extended_activity_types ext ON p.extended_type_id = ext.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
            WHERE p.id = ?
        '''
        planned = self.fetchone(query, (planned_id,))

        if not planned:
            raise PlannedActivityNotFoundError(planned_id)

        return planned

    def get_planned_activities(self, start_date, end_date):
        """Get planned activities within a date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of planned activity dictionaries
        """
        query = '''
            SELECT
                p.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon,
                ext.base_sport_type as extended_base_type,
                a.name as matched_activity_name
            FROM planned_activities p
            LEFT JOIN extended_activity_types ext ON p.extended_type_id = ext.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
            WHERE p.date >= ? AND p.date <= ?
            ORDER BY p.date, p.created_at
        '''
        return self.fetchall(query, (start_date, end_date))

    def get_planned_activities_by_date(self, date):
        """Get all planned activities for a specific date

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            List of planned activity dictionaries
        """
        query = '''
            SELECT
                p.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon,
                ext.base_sport_type as extended_base_type,
                a.name as matched_activity_name
            FROM planned_activities p
            LEFT JOIN extended_activity_types ext ON p.extended_type_id = ext.id
            LEFT JOIN activities a ON p.matched_activity_id = a.id
            WHERE p.date = ?
            ORDER BY p.created_at
        '''
        return self.fetchall(query, (date,))

    def create_planned_activity(self, data):
        """Create a new planned activity

        Args:
            data: Planned activity data
                Required: date, name
                Must have either: extended_type_id OR sport_type

        Returns:
            Created planned activity dictionary

        Raises:
            ValidationError: If validation fails
        """
        # Validate required fields
        if not data.get('date'):
            raise ValidationError('Date is required', field='date')

        if not data.get('name'):
            raise ValidationError('Name is required', field='name')

        # Clean up empty strings to None
        extended_type_id = data.get('extended_type_id')
        if extended_type_id == '' or extended_type_id == 'null':
            extended_type_id = None

        sport_type = data.get('sport_type')
        if sport_type == '' or sport_type == 'null':
            sport_type = None

        # Must have either extended_type_id or sport_type
        if not extended_type_id and not sport_type:
            raise ValidationError('Either extended_type_id or sport_type must be provided')

        # Set the cleaned values
        data['extended_type_id'] = extended_type_id
        data['sport_type'] = sport_type if not extended_type_id else None

        # Insert
        planned_id = self.insert('planned_activities', data)

        # Return created activity
        return self.get_planned_activity(planned_id)

    def update_planned_activity(self, planned_id, data):
        """Update a planned activity

        Args:
            planned_id: Planned activity ID
            data: Fields to update

        Returns:
            Updated planned activity dictionary

        Raises:
            PlannedActivityNotFoundError: If planned activity doesn't exist
        """
        # Check if exists
        existing = self.get_by_id('planned_activities', planned_id)
        if not existing:
            raise PlannedActivityNotFoundError(planned_id)

        # Clean up empty strings to None for type fields
        if 'extended_type_id' in data:
            if data['extended_type_id'] == '' or data['extended_type_id'] == 'null':
                data['extended_type_id'] = None

        if 'sport_type' in data:
            if data['sport_type'] == '' or data['sport_type'] == 'null':
                data['sport_type'] = None

        # If extended_type_id is being set, clear sport_type
        if data.get('extended_type_id'):
            data['sport_type'] = None

        # Update
        self.update('planned_activities', data, id_value=planned_id)

        # Return updated
        return self.get_planned_activity(planned_id)

    def delete_planned_activity(self, planned_id):
        """Delete a planned activity

        Args:
            planned_id: Planned activity ID

        Returns:
            True if deleted

        Raises:
            PlannedActivityNotFoundError: If planned activity doesn't exist
        """
        # Check if exists
        existing = self.get_by_id('planned_activities', planned_id)
        if not existing:
            raise PlannedActivityNotFoundError(planned_id)

        # Delete
        self.delete('planned_activities', id_value=planned_id)
        return True

    def copy_planned_activity(self, planned_id, target_dates):
        """Copy a planned activity to multiple target dates

        Args:
            planned_id: Source planned activity ID
            target_dates: List of target date strings

        Returns:
            Number of copies created

        Raises:
            PlannedActivityNotFoundError: If source activity doesn't exist
            ValidationError: If target_dates is empty
        """
        # Get original
        original = self.get_by_id('planned_activities', planned_id)
        if not original:
            raise PlannedActivityNotFoundError(planned_id)

        # Validate target_dates
        if not target_dates:
            raise ValidationError('No target dates provided')

        # Convert to list if string
        if isinstance(target_dates, str):
            target_dates = [target_dates]

        # Copy to each target date
        copied_count = 0
        for target_date in target_dates:
            copy_data = {
                'date': target_date,
                'name': original['name'],
                'description': original['description'],
                'extended_type_id': original['extended_type_id'],
                'sport_type': original['sport_type'],
                'planned_distance': original['planned_distance'],
                'planned_duration': original['planned_duration'],
                'planned_elevation': original['planned_elevation'],
                'coaching_notes': original['coaching_notes'],
                'intensity_level': original['intensity_level']
            }

            self.insert('planned_activities', copy_data)
            copied_count += 1

        return copied_count

    def match_to_actual(self, planned_id, activity_id):
        """Link a planned activity to an actual activity

        Args:
            planned_id: Planned activity ID
            activity_id: Actual activity ID

        Returns:
            True if matched

        Raises:
            PlannedActivityNotFoundError: If planned activity doesn't exist
            ValidationError: If actual activity doesn't exist
            InvalidOperationError: If dates don't match or activity already matched
        """
        # Get planned activity
        planned = self.get_by_id('planned_activities', planned_id)
        if not planned:
            raise PlannedActivityNotFoundError(planned_id)

        # Get actual activity
        actual = self.get_by_id('activities', activity_id)
        if not actual:
            raise ValidationError(f'Activity {activity_id} not found')

        # Validate dates match
        if planned['date'] != actual['day_date']:
            raise InvalidOperationError(
                f"Date mismatch: Planned activity is on {planned['date']} "
                f"but actual activity is on {actual['day_date']}"
            )

        # Check if activity is already matched to a different planned activity
        existing_match = self.fetchone(
            '''SELECT id, name FROM planned_activities
               WHERE matched_activity_id = ? AND id != ?''',
            (activity_id, planned_id)
        )
        if existing_match:
            raise InvalidOperationError(
                f"Activity is already matched to \"{existing_match['name']}\". "
                f"Please unmatch it first."
            )

        # Create match
        self.update(
            'planned_activities',
            {
                'matched_activity_id': activity_id,
                'match_type': 'manual'
            },
            id_value=planned_id
        )

        return True

    def unmatch_activity(self, planned_id):
        """Remove the match between a planned activity and actual activity

        Args:
            planned_id: Planned activity ID

        Returns:
            True if unmatched

        Raises:
            PlannedActivityNotFoundError: If planned activity doesn't exist
        """
        # Check if exists
        existing = self.get_by_id('planned_activities', planned_id)
        if not existing:
            raise PlannedActivityNotFoundError(planned_id)

        # Remove match
        self.update(
            'planned_activities',
            {
                'matched_activity_id': None,
                'match_type': None
            },
            id_value=planned_id
        )

        return True

    def get_unmatched_planned_activities(self, start_date=None, end_date=None):
        """Get planned activities that haven't been matched to actual activities

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of unmatched planned activity dictionaries
        """
        query = '''
            SELECT
                p.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon
            FROM planned_activities p
            LEFT JOIN extended_activity_types ext ON p.extended_type_id = ext.id
            WHERE p.matched_activity_id IS NULL
        '''
        params = []

        if start_date:
            query += ' AND p.date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND p.date <= ?'
            params.append(end_date)

        query += ' ORDER BY p.date'

        return self.fetchall(query, params)

    def get_completion_rate(self, start_date, end_date):
        """Calculate completion rate for planned activities in a date range

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with:
                - total_planned: Total planned activities
                - completed: Number matched to actual activities
                - completion_rate: Percentage (0-100)
        """
        query = '''
            SELECT
                COUNT(*) as total_planned,
                SUM(CASE WHEN matched_activity_id IS NOT NULL THEN 1 ELSE 0 END) as completed
            FROM planned_activities
            WHERE date >= ? AND date <= ?
        '''
        result = self.fetchone(query, (start_date, end_date))

        total = result['total_planned'] or 0
        completed = result['completed'] or 0
        rate = (completed / total * 100) if total > 0 else 0

        return {
            'total_planned': total,
            'completed': completed,
            'completion_rate': round(rate, 1)
        }
