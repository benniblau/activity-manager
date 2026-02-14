"""Day repository for managing day-specific data and queries"""

from .base import BaseRepository


class DayRepository(BaseRepository):
    """Repository for day-related operations"""

    def get_day(self, date):
        """Get day information for a specific date

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Day dictionary or None
        """
        query = 'SELECT * FROM days WHERE date = ?'
        return self.fetchone(query, (date,))

    def get_or_create_day(self, date, data=None):
        """Get existing day or create if doesn't exist

        Args:
            date: Date string (YYYY-MM-DD)
            data: Optional additional day data

        Returns:
            Day dictionary
        """
        # Check if exists
        existing = self.get_day(date)
        if existing:
            return existing

        # Create new day
        day_data = {'date': date}
        if data:
            day_data.update(data)

        self.insert('days', day_data)
        return self.get_day(date)

    def update_day(self, date, data):
        """Update day information

        Args:
            date: Date string (YYYY-MM-DD)
            data: Fields to update

        Returns:
            Updated day dictionary
        """
        # Ensure day exists
        self.get_or_create_day(date)

        # Update
        self.update('days', data, id_column='date', id_value=date)

        return self.get_day(date)

    def get_feelings_by_dates(self, dates):
        """Get day feelings for a list of dates, keyed by date

        Args:
            dates: List of date strings (YYYY-MM-DD)

        Returns:
            Dictionary mapping date strings to day feeling dictionaries
        """
        if not dates:
            return {}

        placeholders = ','.join(['?' for _ in dates])
        rows = self.fetchall(
            f'SELECT * FROM days WHERE date IN ({placeholders})',
            dates
        )
        return {row['date']: row for row in rows}

    def get_days_in_range(self, start_date, end_date):
        """Get all days in a date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of day dictionaries
        """
        query = '''
            SELECT * FROM days
            WHERE date >= ? AND date <= ?
            ORDER BY date
        '''
        return self.fetchall(query, (start_date, end_date))

    def get_day_with_activities(self, date):
        """Get day information with associated activities

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Dictionary with:
                - day: Day information
                - activities: List of activities for that day
        """
        day = self.get_day(date)

        # Get activities
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

    def get_day_stats(self, date):
        """Get aggregated statistics for a specific day

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Dictionary with day statistics
        """
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
