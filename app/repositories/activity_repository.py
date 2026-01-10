"""Activity repository for managing activity data"""

from datetime import datetime
from .base import BaseRepository
from app.utils.errors import ActivityNotFoundError, ValidationError, DatabaseError


class ActivityRepository(BaseRepository):
    """Repository for activity CRUD operations and queries"""

    def get_activity(self, activity_id):
        """Get a single activity by ID with extended type information

        Args:
            activity_id: Activity ID

        Returns:
            Activity dictionary or None

        Raises:
            ActivityNotFoundError: If activity doesn't exist
        """
        query = '''
            SELECT
                a.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon
            FROM activities a
            LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
            WHERE a.id = ?
        '''
        activity = self.fetchone(query, (activity_id,))

        if not activity:
            raise ActivityNotFoundError(activity_id)

        return activity

    def get_activities(self, filters=None, limit=None, offset=0):
        """Get activities with optional filtering

        Args:
            filters: Dictionary of filter criteria:
                - sport_type: Filter by sport type
                - start_date: Activities after this date
                - end_date: Activities before this date
                - day_date: Activities on specific day
                - gear_id: Activities with specific gear
                - extended_type_id: Activities with extended type
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of activity dictionaries
        """
        if filters is None:
            filters = {}

        # Build query
        query = '''
            SELECT
                a.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon
            FROM activities a
            LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
            WHERE 1=1
        '''
        params = []

        # Apply filters
        if filters.get('sport_type'):
            query += ' AND a.sport_type = ?'
            params.append(filters['sport_type'])

        if filters.get('day_date'):
            query += ' AND a.day_date = ?'
            params.append(filters['day_date'])
        else:
            # Date range filtering
            if filters.get('start_date'):
                query += ' AND a.start_date >= ?'
                params.append(filters['start_date'])

            if filters.get('end_date'):
                query += ' AND a.start_date <= ?'
                params.append(filters['end_date'])

        if filters.get('gear_id'):
            query += ' AND a.gear_id = ?'
            params.append(filters['gear_id'])

        if filters.get('extended_type_id'):
            query += ' AND a.extended_type_id = ?'
            params.append(filters['extended_type_id'])

        # Order by start date (most recent first)
        query += ' ORDER BY a.start_date DESC'

        # Pagination
        if limit is not None:
            query += ' LIMIT ?'
            params.append(limit)

        if offset:
            query += ' OFFSET ?'
            params.append(offset)

        return self.fetchall(query, params)

    def create_activity(self, data):
        """Create a new activity

        Args:
            data: Activity data dictionary
                Required: name, sport_type, start_date_local, elapsed_time

        Returns:
            Created activity dictionary

        Raises:
            ValidationError: If required fields are missing
            DatabaseError: If creation fails
        """
        # Validate required fields
        required_fields = ['name', 'sport_type', 'start_date_local', 'elapsed_time']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise ValidationError(f'Missing required fields: {", ".join(missing_fields)}')

        # Set defaults
        if 'start_date' not in data:
            data['start_date'] = data['start_date_local']
        if 'moving_time' not in data:
            data['moving_time'] = data['elapsed_time']
        if 'manual' not in data:
            data['manual'] = True

        # Insert activity
        activity_id = self.insert('activities', data)

        # Return created activity
        return self.get_activity(activity_id)

    def update_activity(self, activity_id, data):
        """Update an existing activity

        Args:
            activity_id: Activity ID
            data: Dictionary of fields to update

        Returns:
            Updated activity dictionary

        Raises:
            ActivityNotFoundError: If activity doesn't exist
            DatabaseError: If update fails
        """
        # Check if activity exists
        existing = self.get_by_id('activities', activity_id)
        if not existing:
            raise ActivityNotFoundError(activity_id)

        # Update
        rows_affected = self.update('activities', data, id_value=activity_id)

        if rows_affected == 0:
            raise DatabaseError(f"Failed to update activity {activity_id}")

        # Return updated activity
        return self.get_activity(activity_id)

    def delete_activity(self, activity_id):
        """Delete an activity

        Args:
            activity_id: Activity ID

        Returns:
            True if deleted

        Raises:
            ActivityNotFoundError: If activity doesn't exist
        """
        # Check if exists
        existing = self.get_by_id('activities', activity_id)
        if not existing:
            raise ActivityNotFoundError(activity_id)

        # Delete
        self.delete('activities', id_value=activity_id)
        return True

    def get_stats(self, filters=None):
        """Get activity statistics with optional filtering

        Args:
            filters: Dictionary of filter criteria (same as get_activities)

        Returns:
            Dictionary with aggregated statistics:
                - total_activities: Count of activities
                - total_distance_meters: Total distance
                - total_distance_km: Total distance in km
                - total_elevation_meters: Total elevation gain
                - total_time_seconds: Total moving time
                - total_time_hours: Total time in hours
                - average_distance_km: Average distance per activity
        """
        if filters is None:
            filters = {}

        # Build query
        query = '''
            SELECT
                COUNT(*) as total_activities,
                SUM(distance) as total_distance,
                SUM(total_elevation_gain) as total_elevation,
                SUM(moving_time) as total_time
            FROM activities WHERE 1=1
        '''
        params = []

        # Apply filters
        if filters.get('sport_type'):
            query += ' AND sport_type = ?'
            params.append(filters['sport_type'])

        if filters.get('start_date'):
            query += ' AND start_date >= ?'
            params.append(filters['start_date'])

        if filters.get('end_date'):
            query += ' AND start_date <= ?'
            params.append(filters['end_date'])

        result = self.fetchone(query, params)

        total_activities = result['total_activities'] or 0
        total_distance = result['total_distance'] or 0
        total_elevation = result['total_elevation'] or 0
        total_time = result['total_time'] or 0

        return {
            'total_activities': total_activities,
            'total_distance_meters': total_distance,
            'total_distance_km': round(total_distance / 1000, 2),
            'total_elevation_meters': total_elevation,
            'total_time_seconds': total_time,
            'total_time_hours': round(total_time / 3600, 2),
            'average_distance_km': round(total_distance / 1000 / total_activities, 2) if total_activities > 0 else 0
        }

    def upsert_from_strava(self, strava_data):
        """Insert or update activity from Strava data

        Args:
            strava_data: Dictionary with Strava activity data (must include 'id')

        Returns:
            Tuple of (created: bool, activity: dict)
                - created: True if new activity was created, False if updated
                - activity: The resulting activity dictionary

        Raises:
            ValidationError: If strava_data is invalid
            DatabaseError: If upsert fails
        """
        if 'id' not in strava_data:
            raise ValidationError("Strava data must include 'id'")

        activity_id = strava_data['id']

        # Check if activity exists
        existing = self.get_by_id('activities', activity_id)

        if existing:
            # Update existing activity
            # Remove id from update data
            update_data = {k: v for k, v in strava_data.items() if k != 'id'}
            activity = self.update_activity(activity_id, update_data)
            return (False, activity)
        else:
            # Create new activity
            activity = self.create_activity(strava_data)
            return (True, activity)

    def get_activities_by_gear(self, gear_id):
        """Get all activities for a specific gear

        Args:
            gear_id: Gear ID

        Returns:
            List of activity dictionaries
        """
        query = '''
            SELECT
                a.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon
            FROM activities a
            LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
            WHERE a.gear_id = ?
            ORDER BY a.start_date DESC
        '''
        return self.fetchall(query, (gear_id,))

    def get_activities_by_day(self, day_date):
        """Get all activities for a specific day

        Args:
            day_date: Date string in YYYY-MM-DD format

        Returns:
            List of activity dictionaries
        """
        return self.get_activities(filters={'day_date': day_date})

    def search_activities(self, search_term, limit=50):
        """Search activities by name or description

        Args:
            search_term: Search string
            limit: Maximum results

        Returns:
            List of activity dictionaries
        """
        query = '''
            SELECT
                a.*,
                ext.custom_name as extended_name,
                ext.color_class as extended_color,
                ext.icon_override as extended_icon
            FROM activities a
            LEFT JOIN extended_activity_types ext ON a.extended_type_id = ext.id
            WHERE a.name LIKE ? OR a.description LIKE ?
            ORDER BY a.start_date DESC
            LIMIT ?
        '''
        search_pattern = f'%{search_term}%'
        return self.fetchall(query, (search_pattern, search_pattern, limit))
