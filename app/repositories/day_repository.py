"""Day repository for managing day-specific data and queries"""

from .base import BaseRepository


class DayRepository(BaseRepository):
    """Repository for day-related operations"""

    def get_day(self, date, user_id=None):
        """Get day information for a specific date

        Args:
            date: Date string (YYYY-MM-DD)
            user_id: User ID (optional, for access control)

        Returns:
            Day dictionary or None
        """
        if user_id is not None:
            query = 'SELECT * FROM days WHERE date = ? AND user_id = ?'
            return self.fetchone(query, (date, user_id))
        else:
            query = 'SELECT * FROM days WHERE date = ?'
            return self.fetchone(query, (date,))

    def get_or_create_day(self, date, user_id, data=None):
        """Get existing day or create if doesn't exist

        Args:
            date: Date string (YYYY-MM-DD)
            user_id: User ID (required for multi-user)
            data: Optional additional day data

        Returns:
            Day dictionary
        """
        # Check if exists
        existing = self.get_day(date, user_id)
        if existing:
            return existing

        # Create new day
        day_data = {'date': date, 'user_id': user_id}
        if data:
            day_data.update(data)

        self.insert('days', day_data)
        return self.get_day(date, user_id)

    def update_day(self, date, user_id, data):
        """Update day information

        Args:
            date: Date string (YYYY-MM-DD)
            user_id: User ID (required for multi-user)
            data: Fields to update

        Returns:
            Updated day dictionary
        """
        # Ensure day exists
        self.get_or_create_day(date, user_id)

        # Update - need custom WHERE clause for composite key
        db = self.get_db()
        set_clause = ', '.join([f'{k} = ?' for k in data.keys()])
        values = list(data.values()) + [date, user_id]

        query = f'UPDATE days SET {set_clause} WHERE date = ? AND user_id = ?'
        db.execute(query, values)

        if self._auto_commit:
            db.commit()

        return self.get_day(date, user_id)

    def get_feelings_by_dates(self, dates, user_id=None):
        """Get day feelings for a list of dates, keyed by date

        Args:
            dates: List of date strings (YYYY-MM-DD)
            user_id: User ID (optional, for access control)

        Returns:
            Dictionary mapping date strings to day feeling dictionaries
        """
        if not dates:
            return {}

        placeholders = ','.join(['?' for _ in dates])

        if user_id is not None:
            query = f'SELECT * FROM days WHERE date IN ({placeholders}) AND user_id = ?'
            rows = self.fetchall(query, dates + [user_id])
        else:
            query = f'SELECT * FROM days WHERE date IN ({placeholders})'
            rows = self.fetchall(query, dates)

        return {row['date']: row for row in rows}

    def get_days_in_range(self, start_date, end_date, user_id=None):
        """Get all days in a date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            user_id: User ID (optional, for access control)

        Returns:
            List of day dictionaries
        """
        if user_id is not None:
            query = '''
                SELECT * FROM days
                WHERE date >= ? AND date <= ? AND user_id = ?
                ORDER BY date
            '''
            return self.fetchall(query, (start_date, end_date, user_id))
        else:
            query = '''
                SELECT * FROM days
                WHERE date >= ? AND date <= ?
                ORDER BY date
            '''
            return self.fetchall(query, (start_date, end_date))

    def get_day_with_activities(self, date, user_id=None):
        """Get day information with associated activities

        Args:
            date: Date string (YYYY-MM-DD)
            user_id: User ID (optional, for access control)

        Returns:
            Dictionary with:
                - day: Day information
                - activities: List of activities for that day
        """
        day = self.get_day(date, user_id)

        # Get activities
        if user_id is not None:
            activities_query = '''
                SELECT
                    a.*,
                    ext.custom_name as extended_name,
                    ext.color_class as extended_color
                FROM activities a
                LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
                WHERE a.day_date = ? AND a.user_id = ?
                ORDER BY a.start_date_local
            '''
            activities = self.fetchall(activities_query, (date, user_id))
        else:
            activities_query = '''
                SELECT
                    a.*,
                    ext.custom_name as extended_name,
                    ext.color_class as extended_color
                FROM activities a
                LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
                WHERE a.day_date = ?
                ORDER BY a.start_date_local
            '''
            activities = self.fetchall(activities_query, (date,))

        return {
            'day': day,
            'activities': activities
        }

    def get_day_stats(self, date, user_id=None):
        """Get aggregated statistics for a specific day

        Args:
            date: Date string (YYYY-MM-DD)
            user_id: User ID (optional, for access control)

        Returns:
            Dictionary with day statistics
        """
        if user_id is not None:
            query = '''
                SELECT
                    COUNT(*) as activity_count,
                    SUM(distance) as total_distance,
                    SUM(moving_time) as total_time,
                    SUM(total_elevation_gain) as total_elevation
                FROM activities
                WHERE day_date = ? AND user_id = ?
            '''
            stats = self.fetchone(query, (date, user_id))
        else:
            query = '''
                SELECT
                    COUNT(*) as activity_count,
                    SUM(distance) as total_distance,
                    SUM(moving_time) as total_time,
                    SUM(total_elevation_gain) as total_elevation
                FROM activities
                WHERE day_date = ?
            '''
            stats = self.fetchone(query, (date,))

        return {
            'date': date,
            'activity_count': stats['activity_count'] or 0,
            'total_distance': stats['total_distance'] or 0,
            'total_time': stats['total_time'] or 0,
            'total_elevation': stats['total_elevation'] or 0
        }
