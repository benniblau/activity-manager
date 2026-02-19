"""User authentication functions for registration, login, and password management"""

import bcrypt
from datetime import datetime
from app.database import get_db
from app.models.user import User


def hash_password(password):
    """Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password, password_hash):
    """Verify a password against its hash

    Args:
        password: Plain text password to verify
        password_hash: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def register_user(email, password, name, role='athlete'):
    """Register a new user

    Args:
        email: User email address (must be unique)
        password: Plain text password (will be hashed)
        name: User's full name
        role: User role ('athlete' or 'coach'), defaults to 'athlete'

    Returns:
        User instance if successful

    Raises:
        ValueError: If email already exists or validation fails
    """
    # Validate inputs
    if not email or '@' not in email:
        raise ValueError('Valid email address is required')

    if not password or len(password) < 8:
        raise ValueError('Password must be at least 8 characters')

    if not name or len(name.strip()) == 0:
        raise ValueError('Name is required')

    if role not in ('athlete', 'coach'):
        raise ValueError('Role must be either "athlete" or "coach"')

    # Check if email already exists
    if User.get_by_email(email):
        raise ValueError('Email address already registered')

    # Hash password
    password_hash = hash_password(password)

    # Insert user
    db = get_db()
    try:
        cursor = db.execute('''
            INSERT INTO users (email, password_hash, name, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        ''', (
            email.lower().strip(),
            password_hash,
            name.strip(),
            role,
            datetime.utcnow().isoformat(),
            datetime.utcnow().isoformat()
        ))
        user_id = cursor.lastrowid

        # If registering as a coach, link any pending invitations by email
        if role == 'coach':
            db.execute('''
                UPDATE coach_athlete_relationships
                SET coach_id = ?, coach_email = NULL
                WHERE coach_email = ? AND coach_id IS NULL
            ''', (user_id, email.lower().strip()))

        db.commit()
        return User.get(user_id)

    except Exception as e:
        db.rollback()
        raise ValueError(f'Failed to register user: {str(e)}')


def authenticate_user(email, password):
    """Authenticate a user with email and password

    Args:
        email: User email address
        password: Plain text password

    Returns:
        User instance if authentication successful, None otherwise
    """
    if not email or not password:
        return None

    # Get user by email
    user = User.get_by_email(email.lower().strip())
    if not user:
        return None

    # Check if user is active
    if not user.is_active:
        return None

    # Get password hash from database
    db = get_db()
    cursor = db.execute(
        'SELECT password_hash FROM users WHERE id = ?',
        (user.id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    password_hash = row[0]

    # Verify password
    if verify_password(password, password_hash):
        return user

    return None


def update_password(user_id, old_password, new_password):
    """Update user's password

    Args:
        user_id: User ID
        old_password: Current password (for verification)
        new_password: New password

    Returns:
        True if successful

    Raises:
        ValueError: If validation fails or old password is incorrect
    """
    if not new_password or len(new_password) < 8:
        raise ValueError('New password must be at least 8 characters')

    # Get current password hash
    db = get_db()
    cursor = db.execute(
        'SELECT password_hash FROM users WHERE id = ?',
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError('User not found')

    # Verify old password
    if not verify_password(old_password, row[0]):
        raise ValueError('Current password is incorrect')

    # Hash new password
    new_password_hash = hash_password(new_password)

    # Update password
    try:
        db.execute('''
            UPDATE users
            SET password_hash = ?, updated_at = ?
            WHERE id = ?
        ''', (new_password_hash, datetime.utcnow().isoformat(), user_id))
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        raise ValueError(f'Failed to update password: {str(e)}')


def update_user_profile(user_id, name=None, email=None):
    """Update user profile information

    Args:
        user_id: User ID
        name: New name (optional)
        email: New email (optional)

    Returns:
        Updated User instance

    Raises:
        ValueError: If validation fails or email is already taken
    """
    db = get_db()

    # Build update query dynamically
    updates = []
    params = []

    if name is not None and name.strip():
        updates.append('name = ?')
        params.append(name.strip())

    if email is not None and email.strip():
        # Check if email is already taken by another user
        cursor = db.execute(
            'SELECT id FROM users WHERE email = ? AND id != ?',
            (email.lower().strip(), user_id)
        )
        if cursor.fetchone():
            raise ValueError('Email address already in use')

        updates.append('email = ?')
        params.append(email.lower().strip())

    if not updates:
        # Nothing to update
        return User.get(user_id)

    updates.append('updated_at = ?')
    params.append(datetime.utcnow().isoformat())
    params.append(user_id)

    # Update user
    try:
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        db.execute(query, params)
        db.commit()
        return User.get(user_id)

    except Exception as e:
        db.rollback()
        raise ValueError(f'Failed to update profile: {str(e)}')


def deactivate_user(user_id):
    """Deactivate a user account

    Args:
        user_id: User ID

    Returns:
        True if successful
    """
    db = get_db()
    try:
        db.execute('''
            UPDATE users
            SET is_active = 0, updated_at = ?
            WHERE id = ?
        ''', (datetime.utcnow().isoformat(), user_id))
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        raise ValueError(f'Failed to deactivate user: {str(e)}')


def reactivate_user(user_id):
    """Reactivate a user account

    Args:
        user_id: User ID

    Returns:
        True if successful
    """
    db = get_db()
    try:
        db.execute('''
            UPDATE users
            SET is_active = 1, updated_at = ?
            WHERE id = ?
        ''', (datetime.utcnow().isoformat(), user_id))
        db.commit()
        return True

    except Exception as e:
        db.rollback()
        raise ValueError(f'Failed to reactivate user: {str(e)}')
