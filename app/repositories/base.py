"""Base repository class with common database operations"""

from abc import ABC
from datetime import datetime
from flask import g
from app.database import get_db
from app.utils.database_helpers import db_row_to_dict, dict_to_db_values
from app.utils.errors import DatabaseError


class BaseRepository(ABC):
    """Abstract base class for all repositories

    Provides common database operations and utilities for data access.
    Subclasses should define their table name and implement specific queries.
    """

    def __init__(self, db=None):
        """Initialize repository with optional database connection

        Args:
            db: Optional database connection. If None, will use Flask g.db
        """
        self._db = db
        self._auto_commit = True  # Auto-commit by default

    def get_db(self):
        """Get database connection from Flask g object or use provided connection

        Returns:
            Database connection
        """
        if self._db is not None:
            return self._db
        return get_db()

    def set_auto_commit(self, auto_commit):
        """Enable or disable auto-commit for batch operations

        Args:
            auto_commit: Boolean - True to commit after each operation, False to batch
        """
        self._auto_commit = auto_commit

    def commit(self):
        """Manually commit the current transaction"""
        db = self.get_db()
        db.commit()

    def execute(self, query, params=None):
        """Execute a query and return cursor

        Args:
            query: SQL query string
            params: Query parameters (tuple or list)

        Returns:
            Database cursor

        Raises:
            DatabaseError: If query execution fails
        """
        if params is None:
            params = ()

        try:
            db = self.get_db()
            return db.execute(query, params)
        except Exception as e:
            raise DatabaseError(f"Query execution failed: {str(e)}", e)

    def fetchone(self, query, params=None):
        """Execute query and fetch single row as dictionary

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Dictionary or None if no results
        """
        cursor = self.execute(query, params)
        row = cursor.fetchone()
        return db_row_to_dict(row)

    def fetchall(self, query, params=None):
        """Execute query and fetch all rows as list of dictionaries

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries
        """
        cursor = self.execute(query, params)
        rows = cursor.fetchall()
        return [db_row_to_dict(row) for row in rows]

    def insert(self, table, data):
        """Insert a row into a table

        Args:
            table: Table name
            data: Dictionary of column->value pairs

        Returns:
            ID of inserted row

        Raises:
            DatabaseError: If insert fails
        """
        try:
            # Convert data to DB-friendly format
            db_data = dict_to_db_values(data)

            # Build query
            columns = ', '.join(db_data.keys())
            placeholders = ', '.join(['?' for _ in db_data])
            query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'

            # Execute
            db = self.get_db()
            cursor = db.execute(query, list(db_data.values()))
            if self._auto_commit:
                db.commit()

            return cursor.lastrowid
        except Exception as e:
            raise DatabaseError(f"Insert failed for table {table}: {str(e)}", e)

    def update(self, table, data, id_column='id', id_value=None):
        """Update a row in a table

        Args:
            table: Table name
            data: Dictionary of column->value pairs to update
            id_column: Name of ID column (default: 'id')
            id_value: Value of ID to update

        Returns:
            Number of rows affected

        Raises:
            DatabaseError: If update fails
        """
        try:
            # Convert data to DB-friendly format
            db_data = dict_to_db_values(data)

            # Remove ID from update data if present
            db_data.pop(id_column, None)

            # Add updated timestamp if not present
            if 'updated_at' not in db_data:
                db_data['updated_at'] = datetime.utcnow().isoformat()

            # Build query
            set_clause = ', '.join([f'{key} = ?' for key in db_data.keys()])
            query = f'UPDATE {table} SET {set_clause} WHERE {id_column} = ?'

            # Execute
            db = self.get_db()
            values = list(db_data.values()) + [id_value]
            cursor = db.execute(query, values)
            if self._auto_commit:
                db.commit()

            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(f"Update failed for table {table}: {str(e)}", e)

    def delete(self, table, id_column='id', id_value=None):
        """Delete a row from a table

        Args:
            table: Table name
            id_column: Name of ID column (default: 'id')
            id_value: Value of ID to delete

        Returns:
            Number of rows deleted

        Raises:
            DatabaseError: If delete fails
        """
        try:
            query = f'DELETE FROM {table} WHERE {id_column} = ?'

            db = self.get_db()
            cursor = db.execute(query, (id_value,))
            db.commit()

            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(f"Delete failed for table {table}: {str(e)}", e)

    def soft_delete(self, table, id_column='id', id_value=None):
        """Soft delete a row (set is_active = 0)

        Args:
            table: Table name
            id_column: Name of ID column (default: 'id')
            id_value: Value of ID to soft delete

        Returns:
            Number of rows affected
        """
        return self.update(
            table,
            {'is_active': 0},
            id_column=id_column,
            id_value=id_value
        )

    def get_by_id(self, table, id_value, id_column='id'):
        """Get a single row by ID

        Args:
            table: Table name
            id_value: ID value to fetch
            id_column: Name of ID column (default: 'id')

        Returns:
            Dictionary or None
        """
        query = f'SELECT * FROM {table} WHERE {id_column} = ?'
        return self.fetchone(query, (id_value,))

    def get_all(self, table, where_clause='', params=None, order_by='', limit=None, offset=None):
        """Get all rows from a table with optional filtering

        Args:
            table: Table name
            where_clause: Optional WHERE clause (without WHERE keyword)
            params: Parameters for WHERE clause
            order_by: Optional ORDER BY clause (without ORDER BY keyword)
            limit: Optional LIMIT
            offset: Optional OFFSET

        Returns:
            List of dictionaries
        """
        if params is None:
            params = []

        query = f'SELECT * FROM {table}'

        if where_clause:
            query += f' WHERE {where_clause}'

        if order_by:
            query += f' ORDER BY {order_by}'

        if limit is not None:
            query += f' LIMIT ?'
            params.append(limit)

        if offset is not None:
            query += f' OFFSET ?'
            params.append(offset)

        return self.fetchall(query, params)

    def count(self, table, where_clause='', params=None):
        """Count rows in a table

        Args:
            table: Table name
            where_clause: Optional WHERE clause (without WHERE keyword)
            params: Parameters for WHERE clause

        Returns:
            Integer count
        """
        if params is None:
            params = []

        query = f'SELECT COUNT(*) as count FROM {table}'

        if where_clause:
            query += f' WHERE {where_clause}'

        result = self.fetchone(query, params)
        return result['count'] if result else 0

    def exists(self, table, where_clause, params=None):
        """Check if a row exists

        Args:
            table: Table name
            where_clause: WHERE clause (without WHERE keyword)
            params: Parameters for WHERE clause

        Returns:
            Boolean
        """
        count = self.count(table, where_clause, params)
        return count > 0
