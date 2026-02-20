"""Invitation service for token-based invitation-only registration"""

import secrets
import re
from datetime import datetime, timedelta
from flask import current_app
from app.database import get_db
from app.models.user import User


def is_users_table_empty():
    """Check if there are any registered users (bootstrap mode detection)

    Returns:
        True if no users exist, False otherwise
    """
    db = get_db()
    cursor = db.execute('SELECT COUNT(*) FROM users')
    return cursor.fetchone()[0] == 0


def create_invitation(inviter_id, invited_email, invited_role):
    """Create a new invitation

    Args:
        inviter_id: ID of the user sending the invitation
        invited_email: Email address to invite
        invited_role: Role for the invited user ('athlete' or 'coach')

    Returns:
        Invitation dict

    Raises:
        ValueError: If validation fails
    """
    # Validate email
    invited_email = invited_email.strip().lower()
    if not invited_email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', invited_email):
        raise ValueError('A valid email address is required.')

    # Validate role
    if invited_role not in ('athlete', 'coach'):
        raise ValueError('Role must be "athlete" or "coach".')

    db = get_db()

    # Prevent self-invite
    inviter = User.get(inviter_id)
    if inviter and inviter.email.lower() == invited_email:
        raise ValueError('You cannot invite yourself.')

    # Email not already registered
    existing_user = User.get_by_email(invited_email)
    if existing_user:
        raise ValueError(f'The email {invited_email} is already registered.')

    # No active pending invitation to the same email
    cursor = db.execute(
        '''SELECT id FROM invitations
           WHERE invited_email = ? AND status = 'pending' AND expires_at > ?''',
        (invited_email, datetime.utcnow().isoformat())
    )
    if cursor.fetchone():
        raise ValueError(f'An active invitation has already been sent to {invited_email}.')

    # Generate secure token and expiry
    token = secrets.token_urlsafe(32)
    expiry_days = current_app.config.get('INVITATION_EXPIRY_DAYS', 30)
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=expiry_days)).isoformat()
    created_at = now.isoformat()

    cursor = db.execute(
        '''INSERT INTO invitations
           (token, inviter_id, invited_email, invited_role, status, created_at, expires_at)
           VALUES (?, ?, ?, ?, 'pending', ?, ?)''',
        (token, inviter_id, invited_email, invited_role, created_at, expires_at)
    )
    db.commit()
    invitation_id = cursor.lastrowid

    return get_invitation_by_id(invitation_id)


def get_invitation_by_id(invitation_id):
    """Fetch a single invitation by ID"""
    db = get_db()
    cursor = db.execute('SELECT * FROM invitations WHERE id = ?', (invitation_id,))
    row = cursor.fetchone()
    if row:
        return _row_to_dict(row)
    return None


def validate_invitation_token(token):
    """Validate an invitation token

    Args:
        token: Invitation token string

    Returns:
        Invitation dict if valid

    Raises:
        ValueError: With user-friendly message if invalid/expired/used/cancelled
    """
    if not token:
        raise ValueError('An invitation token is required.')

    db = get_db()
    cursor = db.execute('SELECT * FROM invitations WHERE token = ?', (token,))
    row = cursor.fetchone()

    if not row:
        raise ValueError('This invitation link is invalid.')

    invitation = _row_to_dict(row)

    if invitation['status'] == 'used':
        raise ValueError('This invitation link has already been used.')

    if invitation['status'] == 'cancelled':
        raise ValueError('This invitation link has been cancelled.')

    if invitation['status'] != 'pending':
        raise ValueError('This invitation link is no longer valid.')

    # Check expiry at runtime
    now = datetime.utcnow().isoformat()
    if invitation['expires_at'] < now:
        raise ValueError('This invitation link has expired. Please request a new invitation.')

    return invitation


def consume_invitation(token, new_user_id):
    """Mark an invitation as used after successful registration

    Args:
        token: Invitation token
        new_user_id: ID of the newly registered user

    Returns:
        Updated invitation dict
    """
    db = get_db()
    now = datetime.utcnow().isoformat()
    db.execute(
        '''UPDATE invitations
           SET status = 'used', used_at = ?, used_by_user_id = ?
           WHERE token = ?''',
        (now, new_user_id, token)
    )
    db.commit()

    cursor = db.execute('SELECT * FROM invitations WHERE token = ?', (token,))
    row = cursor.fetchone()
    return _row_to_dict(row) if row else None


def cancel_invitation(invitation_id, requesting_user_id):
    """Cancel a pending invitation

    Args:
        invitation_id: ID of the invitation to cancel
        requesting_user_id: ID of user requesting cancellation (must be the inviter)

    Returns:
        True if cancelled

    Raises:
        ValueError: If not found, not owned, or not pending
    """
    invitation = get_invitation_by_id(invitation_id)

    if not invitation:
        raise ValueError('Invitation not found.')

    if invitation['inviter_id'] != requesting_user_id:
        raise ValueError('You do not have permission to cancel this invitation.')

    if invitation['status'] != 'pending':
        raise ValueError('Only pending invitations can be cancelled.')

    db = get_db()
    db.execute(
        "UPDATE invitations SET status = 'cancelled' WHERE id = ?",
        (invitation_id,)
    )
    db.commit()
    return True


def get_invitations_sent_by(user_id):
    """Get all invitations sent by a user, newest first

    Args:
        user_id: ID of the inviting user

    Returns:
        List of invitation dicts with computed 'is_expired' bool
    """
    db = get_db()
    cursor = db.execute(
        'SELECT * FROM invitations WHERE inviter_id = ? ORDER BY created_at DESC',
        (user_id,)
    )
    now = datetime.utcnow().isoformat()
    results = []
    for row in cursor.fetchall():
        inv = _row_to_dict(row)
        inv['is_expired'] = inv['status'] == 'pending' and inv['expires_at'] < now
        results.append(inv)
    return results


def _row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict"""
    return dict(row)
