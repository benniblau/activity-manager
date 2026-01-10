"""Gear repository for managing gear/equipment data"""

from .base import BaseRepository
from app.utils.errors import ValidationError


class GearRepository(BaseRepository):
    """Repository for gear/equipment operations"""

    def get_gear(self, gear_id):
        """Get gear by ID

        Args:
            gear_id: Gear ID (Strava gear ID)

        Returns:
            Gear dictionary or None
        """
        return self.get_by_id('gear', gear_id, id_column='id')

    def get_all_gear(self, is_active=None):
        """Get all gear

        Args:
            is_active: Filter by active status (True/False/None for all)

        Returns:
            List of gear dictionaries
        """
        query = 'SELECT * FROM gear'
        params = []

        if is_active is not None:
            query += ' WHERE is_active = ?'
            params.append(1 if is_active else 0)

        query += ' ORDER BY name'

        return self.fetchall(query, params)

    def get_gear_by_type(self, gear_type):
        """Get gear filtered by type

        Args:
            gear_type: Type of gear (e.g., 'bike', 'shoes')

        Returns:
            List of gear dictionaries
        """
        query = 'SELECT * FROM gear WHERE type = ? ORDER BY name'
        return self.fetchall(query, (gear_type,))

    def create_or_update_gear(self, gear_id, data):
        """Create new gear or update existing

        Args:
            gear_id: Gear ID
            data: Gear data dictionary

        Returns:
            Gear dictionary
        """
        existing = self.get_gear(gear_id)

        if existing:
            # Update
            self.update('gear', data, id_column='id', id_value=gear_id)
        else:
            # Create
            data['id'] = gear_id
            self.insert('gear', data)

        return self.get_gear(gear_id)

    def update_gear(self, gear_id, data):
        """Update gear information

        Args:
            gear_id: Gear ID
            data: Fields to update

        Returns:
            Updated gear dictionary

        Raises:
            ValidationError: If gear doesn't exist
        """
        existing = self.get_gear(gear_id)
        if not existing:
            raise ValidationError(f'Gear {gear_id} not found')

        self.update('gear', data, id_column='id', id_value=gear_id)
        return self.get_gear(gear_id)

    def retire_gear(self, gear_id):
        """Mark gear as retired (soft delete)

        Args:
            gear_id: Gear ID

        Returns:
            True if retired

        Raises:
            ValidationError: If gear doesn't exist
        """
        existing = self.get_gear(gear_id)
        if not existing:
            raise ValidationError(f'Gear {gear_id} not found')

        self.update('gear', {'is_active': False}, id_column='id', id_value=gear_id)
        return True

    def activate_gear(self, gear_id):
        """Reactivate retired gear

        Args:
            gear_id: Gear ID

        Returns:
            Updated gear dictionary

        Raises:
            ValidationError: If gear doesn't exist
        """
        existing = self.get_gear(gear_id)
        if not existing:
            raise ValidationError(f'Gear {gear_id} not found')

        return self.update_gear(gear_id, {'is_active': True})

    def get_gear_stats(self, gear_id):
        """Get usage statistics for specific gear

        Args:
            gear_id: Gear ID

        Returns:
            Dictionary with gear statistics:
                - total_activities: Number of activities
                - total_distance: Total distance in meters
                - total_time: Total moving time in seconds
                - total_elevation: Total elevation gain in meters
        """
        query = '''
            SELECT
                COUNT(*) as total_activities,
                SUM(distance) as total_distance,
                SUM(moving_time) as total_time,
                SUM(total_elevation_gain) as total_elevation
            FROM activities
            WHERE gear_id = ?
        '''
        stats = self.fetchone(query, (gear_id,))

        return {
            'gear_id': gear_id,
            'total_activities': stats['total_activities'] or 0,
            'total_distance': stats['total_distance'] or 0,
            'total_time': stats['total_time'] or 0,
            'total_elevation': stats['total_elevation'] or 0
        }

    def get_gear_with_stats(self, gear_id):
        """Get gear information with usage statistics

        Args:
            gear_id: Gear ID

        Returns:
            Dictionary with gear info and stats

        Raises:
            ValidationError: If gear doesn't exist
        """
        gear = self.get_gear(gear_id)
        if not gear:
            raise ValidationError(f'Gear {gear_id} not found')

        stats = self.get_gear_stats(gear_id)

        return {
            **gear,
            'stats': stats
        }

    def get_all_gear_with_stats(self, is_active=None):
        """Get all gear with usage statistics

        Args:
            is_active: Filter by active status

        Returns:
            List of gear dictionaries with stats
        """
        all_gear = self.get_all_gear(is_active)

        result = []
        for gear in all_gear:
            stats = self.get_gear_stats(gear['id'])
            result.append({
                **gear,
                'stats': stats
            })

        return result
