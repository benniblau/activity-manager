"""Type repository for managing standard and extended activity types"""

from collections import defaultdict
from .base import BaseRepository
from app.utils.errors import TypeNotFoundError, ValidationError, DuplicateError, DatabaseError


class TypeRepository(BaseRepository):
    """Repository for standard and extended activity type operations"""

    # ========== Standard Activity Types ==========

    def get_standard_types(self):
        """Get all standard activity types

        Returns:
            List of standard type dictionaries
        """
        query = '''
            SELECT * FROM standard_activity_types
            ORDER BY category, display_order, name
        '''
        return self.fetchall(query)

    def get_standard_type(self, name):
        """Get a single standard type by name

        Args:
            name: Type name (e.g., 'Run', 'Ride')

        Returns:
            Standard type dictionary or None
        """
        query = 'SELECT * FROM standard_activity_types WHERE name = ?'
        return self.fetchone(query, (name,))

    def get_types_by_category(self):
        """Get standard types grouped by category

        Returns:
            Dictionary mapping category -> list of types
            Example: {'Foot': [{'name': 'Run', ...}, ...], 'Cycle': [...]}
        """
        types = self.get_standard_types()

        grouped = defaultdict(list)
        for type_data in types:
            grouped[type_data['category']].append(type_data)

        return dict(grouped)

    def validate_sport_type(self, sport_type):
        """Check if a sport type exists in standard types

        Args:
            sport_type: Sport type name to validate

        Returns:
            Boolean - True if valid, False otherwise
        """
        return self.exists(
            'standard_activity_types',
            'name = ?',
            (sport_type,)
        )

    def auto_create_type(self, sport_type, category='Other'):
        """Auto-create a standard type for unknown sport types from Strava

        Args:
            sport_type: Sport type name
            category: Category (default: 'Other')

        Returns:
            Created type dictionary

        Raises:
            DatabaseError: If creation fails
        """
        # Check if already exists
        existing = self.get_standard_type(sport_type)
        if existing:
            return existing

        # Create new type
        type_data = {
            'name': sport_type,
            'category': category,
            'display_name': sport_type,
            'icon': 'circle-question',
            'color': 'badge-other',
            'description': f'Auto-created type for {sport_type}',
            'is_official': False,  # Mark as non-official
            'display_order': 999
        }

        try:
            self.insert('standard_activity_types', type_data)
            return self.get_standard_type(sport_type)
        except Exception as e:
            raise DatabaseError(f"Failed to auto-create type {sport_type}: {str(e)}", e)

    # ========== Extended Activity Types ==========

    def get_extended_types(self, is_active=True, user_id=None):
        """Get extended activity types

        Args:
            is_active: If True, only return active types (default: True)
                       If False, return all types
                       If None, return all types
            user_id: User ID (optional, for multi-user filtering)
                     Returns system-wide types (user_id IS NULL) + user's types

        Returns:
            List of extended type dictionaries
        """
        query = 'SELECT * FROM extended_activity_types WHERE 1=1'
        params = []

        # Filter by user_id (show system types + user's types)
        if user_id is not None:
            query += ' AND (user_id IS NULL OR user_id = ?)'
            params.append(user_id)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        query += ' ORDER BY base_sport_type, display_order, custom_name'

        return self.fetchall(query, params)

    def get_extended_type(self, type_id, user_id=None):
        """Get a single extended type by ID

        Args:
            type_id: Extended type ID
            user_id: User ID (optional, for access control)

        Returns:
            Extended type dictionary

        Raises:
            TypeNotFoundError: If type doesn't exist or access denied
        """
        if user_id is not None:
            query = '''
                SELECT * FROM extended_activity_types
                WHERE id = ? AND (user_id IS NULL OR user_id = ?)
            '''
            type_data = self.fetchone(query, (type_id, user_id))
        else:
            type_data = self.get_by_id('extended_activity_types', type_id)

        if not type_data:
            raise TypeNotFoundError(type_id)

        return type_data

    def get_extended_types_by_base(self, base_sport_type, is_active=True, user_id=None):
        """Get extended types for a specific base sport type

        Args:
            base_sport_type: Base sport type name
            is_active: Filter by active status
            user_id: User ID (optional, for multi-user filtering)

        Returns:
            List of extended type dictionaries
        """
        query = '''
            SELECT * FROM extended_activity_types
            WHERE base_sport_type = ?
        '''
        params = [base_sport_type]

        # Filter by user_id (show system types + user's types)
        if user_id is not None:
            query += ' AND (user_id IS NULL OR user_id = ?)'
            params.append(user_id)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        query += ' ORDER BY display_order, custom_name'

        return self.fetchall(query, params)

    def create_extended_type(self, data, user_id=None):
        """Create a new extended activity type

        Args:
            data: Extended type data
                Required: base_sport_type, custom_name
                Optional: user_id (if not provided as parameter)
            user_id: User ID for user-specific types (None for system-wide types)

        Returns:
            Created extended type dictionary

        Raises:
            ValidationError: If required fields missing or invalid
            DuplicateError: If custom_name already exists
        """
        # Validate required fields
        if not data.get('base_sport_type'):
            raise ValidationError('base_sport_type is required')

        if not data.get('custom_name'):
            raise ValidationError('custom_name is required')

        # Validate base_sport_type exists
        if not self.validate_sport_type(data['base_sport_type']):
            raise ValidationError(
                f"Invalid base_sport_type: {data['base_sport_type']}",
                field='base_sport_type'
            )

        # Set user_id (from parameter or data)
        if user_id is not None:
            data['user_id'] = user_id

        # Check for duplicate custom_name (global due to UNIQUE constraint)
        existing = self.fetchone(
            'SELECT id FROM extended_activity_types WHERE custom_name = ?',
            (data['custom_name'],)
        )
        if existing:
            raise DuplicateError('Extended type', data['custom_name'])

        # Clean up empty strings for optional fields
        for field in ['description', 'icon_override', 'color_class']:
            if field in data and (data[field] == '' or data[field] == 'null'):
                data[field] = None

        # Insert
        try:
            type_id = self.insert('extended_activity_types', data)
            return self.get_extended_type(type_id, user_id=data.get('user_id'))
        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                raise DuplicateError('Extended type', data['custom_name'])
            raise DatabaseError(f"Failed to create extended type: {str(e)}", e)

    def update_extended_type(self, type_id, data, user_id=None):
        """Update an extended activity type

        Args:
            type_id: Extended type ID
            data: Fields to update
            user_id: User ID (optional, for access control)

        Returns:
            Updated extended type dictionary

        Raises:
            TypeNotFoundError: If type doesn't exist or access denied
            DuplicateError: If custom_name conflicts
        """
        # Check if exists and user has access
        existing = self.get_extended_type(type_id, user_id=user_id)

        # Check for duplicate custom_name (excluding current record)
        if data.get('custom_name'):
            duplicate = self.fetchone(
                'SELECT id FROM extended_activity_types WHERE custom_name = ? AND id != ?',
                (data['custom_name'], type_id)
            )
            if duplicate:
                raise DuplicateError('Extended type', data['custom_name'])

        # Clean up empty strings for optional fields
        for field in ['description', 'icon_override', 'color_class']:
            if field in data and (data[field] == '' or data[field] == 'null'):
                data[field] = None

        # Update
        try:
            self.update('extended_activity_types', data, id_value=type_id)
            return self.get_extended_type(type_id, user_id=user_id)
        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                raise DuplicateError('Extended type', data.get('custom_name', 'unknown'))
            raise DatabaseError(f"Failed to update extended type: {str(e)}", e)

    def delete_extended_type(self, type_id, user_id=None):
        """Soft delete an extended type (set is_active = 0)

        Args:
            type_id: Extended type ID
            user_id: User ID (optional, for access control)

        Returns:
            True if deleted

        Raises:
            TypeNotFoundError: If type doesn't exist or access denied
        """
        # Check if exists and user has access
        self.get_extended_type(type_id, user_id=user_id)

        # Soft delete
        self.soft_delete('extended_activity_types', id_value=type_id)
        return True

    def restore_extended_type(self, type_id, user_id=None):
        """Restore a soft-deleted extended type

        Args:
            type_id: Extended type ID
            user_id: User ID (optional, for access control)

        Returns:
            Restored extended type dictionary

        Raises:
            TypeNotFoundError: If type doesn't exist or access denied
        """
        # Check if exists and user has access (allow inactive types)
        existing = self.get_by_id('extended_activity_types', type_id)
        if not existing:
            raise TypeNotFoundError(type_id)

        if user_id is not None:
            # Verify access control
            if existing['user_id'] is not None and existing['user_id'] != user_id:
                raise TypeNotFoundError(type_id)

        # Restore
        return self.update_extended_type(type_id, {'is_active': True}, user_id=user_id)

    def get_extended_types_grouped_by_base(self, is_active=True, user_id=None):
        """Get extended types grouped by base sport type

        Args:
            is_active: Filter by active status
            user_id: User ID (optional, for multi-user filtering)

        Returns:
            Dictionary mapping base_sport_type -> list of extended types
        """
        extended_types = self.get_extended_types(is_active, user_id=user_id)

        grouped = defaultdict(list)
        for ext_type in extended_types:
            grouped[ext_type['base_sport_type']].append(ext_type)

        return dict(grouped)
