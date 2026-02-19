"""User model for authentication and authorization"""

from flask_login import UserMixin
from app.database import get_db


class User(UserMixin):
    """User model compatible with Flask-Login"""

    def __init__(self, id, email, name, role, is_active=True):
        self.id = id
        self.email = email
        self.name = name
        self.role = role
        self._is_active = is_active

    def __repr__(self):
        return f'<User {self.email}>'

    @property
    def is_active(self):
        """Override UserMixin's is_active property"""
        return self._is_active

    def is_coach(self):
        """Check if user has coach role"""
        return self.role == 'coach'

    def is_athlete(self):
        """Check if user has athlete role"""
        return self.role == 'athlete'

    @staticmethod
    def get(user_id):
        """Load user by ID

        Args:
            user_id: User ID

        Returns:
            User instance or None if not found
        """
        db = get_db()
        cursor = db.execute(
            'SELECT id, email, name, role, is_active FROM users WHERE id = ?',
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            return User(
                id=row[0],
                email=row[1],
                name=row[2],
                role=row[3],
                is_active=bool(row[4])
            )
        return None

    @staticmethod
    def get_by_email(email):
        """Load user by email

        Args:
            email: User email address

        Returns:
            User instance or None if not found
        """
        db = get_db()
        cursor = db.execute(
            'SELECT id, email, name, role, is_active FROM users WHERE email = ?',
            (email,)
        )
        row = cursor.fetchone()
        if row:
            return User(
                id=row[0],
                email=row[1],
                name=row[2],
                role=row[3],
                is_active=bool(row[4])
            )
        return None

    def get_athletes(self):
        """Get list of athletes this coach can access

        Returns:
            List of User instances (athletes) if user is a coach, empty list otherwise
        """
        if not self.is_coach():
            return []

        db = get_db()
        cursor = db.execute('''
            SELECT u.id, u.email, u.name, u.role, u.is_active
            FROM users u
            JOIN coach_athlete_relationships r ON u.id = r.athlete_id
            WHERE r.coach_id = ? AND r.status = 'active'
            ORDER BY u.name
        ''', (self.id,))

        athletes = []
        for row in cursor.fetchall():
            athletes.append(User(
                id=row[0],
                email=row[1],
                name=row[2],
                role=row[3],
                is_active=bool(row[4])
            ))
        return athletes

    def get_coaches(self):
        """Get list of coaches who have access to this athlete's data

        Returns:
            List of User instances (coaches)
        """
        db = get_db()
        cursor = db.execute('''
            SELECT u.id, u.email, u.name, u.role, u.is_active
            FROM users u
            JOIN coach_athlete_relationships r ON u.id = r.coach_id
            WHERE r.athlete_id = ? AND r.status = 'active'
            ORDER BY u.name
        ''', (self.id,))

        coaches = []
        for row in cursor.fetchall():
            coaches.append(User(
                id=row[0],
                email=row[1],
                name=row[2],
                role=row[3],
                is_active=bool(row[4])
            ))
        return coaches
