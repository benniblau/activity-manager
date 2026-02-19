"""Access control service for managing coach-athlete data access"""

from datetime import datetime
from flask import session, current_app
from app.database import get_db
from app.models.user import User
from app.utils.email import send_coach_invitation_email


def can_view_user_data(viewer_id, target_user_id):
    """Check if viewer has permission to view target user's data

    Args:
        viewer_id: ID of user trying to view data
        target_user_id: ID of user whose data is being viewed

    Returns:
        True if viewer can access target user's data, False otherwise
    """
    # Users can always view their own data
    if viewer_id == target_user_id:
        return True

    # Check if viewer is an active coach of target user
    return is_active_coach_of(viewer_id, target_user_id)


def is_active_coach_of(coach_id, athlete_id):
    """Check if coach_id is an active coach of athlete_id

    Args:
        coach_id: ID of potential coach
        athlete_id: ID of athlete

    Returns:
        True if coach has active relationship with athlete, False otherwise
    """
    db = get_db()
    cursor = db.execute('''
        SELECT COUNT(*)
        FROM coach_athlete_relationships
        WHERE coach_id = ? AND athlete_id = ? AND status = 'active'
    ''', (coach_id, athlete_id))

    count = cursor.fetchone()[0]
    return count > 0


def get_accessible_users(user_id):
    """Get list of user IDs that the given user can access

    Args:
        user_id: User ID

    Returns:
        List of user IDs (includes self + coached athletes if user is a coach)
    """
    user = User.get(user_id)
    if not user:
        return []

    accessible_users = [user_id]  # Always include self

    if user.is_coach():
        # Add all active athletes
        athletes = user.get_athletes()
        accessible_users.extend([athlete.id for athlete in athletes])

    return accessible_users


def get_viewing_user_id():
    """Get the user_id currently being viewed

    For athletes: Always returns their own ID
    For coaches: Returns the athlete they're currently viewing, or the first athlete if not set

    Returns:
        User ID being viewed (from session, or default based on role)
    """
    from flask_login import current_user

    if not current_user.is_authenticated:
        return None

    # Athletes always view their own data
    if current_user.is_athlete():
        return current_user.id

    # Coaches view their athletes' data
    if current_user.is_coach():
        # Check if a specific athlete is selected in session
        viewing_user_id = session.get('viewing_user_id')

        if viewing_user_id:
            # Verify coach has access to this athlete
            if can_view_user_data(current_user.id, viewing_user_id):
                return viewing_user_id
            else:
                # Access denied, clear invalid session
                session.pop('viewing_user_id', None)

        # Default to first athlete's data
        athletes = get_coach_athletes_list(current_user.id)
        if athletes:
            first_athlete_id = athletes[0]['id']
            session['viewing_user_id'] = first_athlete_id
            return first_athlete_id

    # Fallback to current user (shouldn't reach here normally)
    return current_user.id


def set_viewing_user_id(user_id):
    """Set the user_id being viewed (for coaches to switch between athletes)

    Args:
        user_id: User ID to view data for

    Returns:
        True if successful, False if access denied
    """
    from flask_login import current_user

    if not current_user.is_authenticated:
        return False

    # Check if user has permission to view this data
    if can_view_user_data(current_user.id, user_id):
        session['viewing_user_id'] = user_id
        return True

    return False


def clear_viewing_user_id():
    """Clear the viewing_user_id from session (return to viewing own data)"""
    session.pop('viewing_user_id', None)


def invite_coach(athlete_id, coach_email):
    """Invite a coach to access athlete's data

    Args:
        athlete_id: ID of athlete sending invitation
        coach_email: Email address of coach to invite

    Returns:
        Tuple of (relationship_id, email_sent_successfully)

    Raises:
        ValueError: If validation fails or invitation already exists
    """
    # Validate email format
    if not coach_email or '@' not in coach_email:
        raise ValueError('Please provide a valid email address.')

    coach_email = coach_email.lower().strip()

    # Get athlete info
    athlete = User.get(athlete_id)
    if not athlete:
        raise ValueError('Athlete not found.')

    # Check if inviting self
    if athlete.email.lower() == coach_email:
        raise ValueError('You cannot invite yourself as a coach.')

    # Check if coach user exists
    coach = User.get_by_email(coach_email)

    # If user exists, validate they're a coach
    if coach and not coach.is_coach():
        raise ValueError(f'{coach_email} is registered as an athlete, not a coach. They cannot be invited as a coach.')

    db = get_db()

    # Check if relationship already exists (by coach_id OR coach_email)
    if coach:
        # Check by coach_id (registered user)
        cursor = db.execute('''
            SELECT id, status FROM coach_athlete_relationships
            WHERE coach_id = ? AND athlete_id = ?
        ''', (coach.id, athlete_id))
    else:
        # Check by coach_email (unregistered user)
        cursor = db.execute('''
            SELECT id, status FROM coach_athlete_relationships
            WHERE coach_email = ? AND athlete_id = ?
        ''', (coach_email, athlete_id))

    existing = cursor.fetchone()
    if existing:
        if existing[1] == 'active':
            coach_name = coach.name if coach else coach_email
            raise ValueError(f'{coach_name} already has active access to your data.')
        elif existing[1] == 'pending':
            coach_name = coach.name if coach else coach_email
            raise ValueError(f'An invitation has already been sent to {coach_name}.')
        elif existing[1] == 'inactive':
            # Reactivate inactive relationship
            if coach:
                db.execute('''
                    UPDATE coach_athlete_relationships
                    SET status = 'pending', invited_at = ?, coach_id = ?, coach_email = NULL
                    WHERE id = ?
                ''', (datetime.utcnow().isoformat(), coach.id, existing[0]))
            else:
                db.execute('''
                    UPDATE coach_athlete_relationships
                    SET status = 'pending', invited_at = ?
                    WHERE id = ?
                ''', (datetime.utcnow().isoformat(), existing[0]))
            db.commit()
            relationship_id = existing[0]

            # Send email notification
            app_url = current_app.config.get('HOST', 'http://localhost:5000')
            coach_name = coach.name if coach else coach_email.split('@')[0]
            email_sent = send_coach_invitation_email(
                coach_email=coach_email,
                coach_name=coach_name,
                athlete_name=athlete.name,
                app_url=app_url,
                is_registered=(coach is not None)
            )

            return (relationship_id, email_sent)

    # Create new invitation
    if coach:
        # Invite registered coach (use coach_id)
        cursor = db.execute('''
            INSERT INTO coach_athlete_relationships (coach_id, athlete_id, status, invited_at)
            VALUES (?, ?, 'pending', ?)
        ''', (coach.id, athlete_id, datetime.utcnow().isoformat()))
    else:
        # Invite unregistered coach (use coach_email)
        cursor = db.execute('''
            INSERT INTO coach_athlete_relationships (coach_email, athlete_id, status, invited_at)
            VALUES (?, ?, 'pending', ?)
        ''', (coach_email, athlete_id, datetime.utcnow().isoformat()))

    db.commit()
    relationship_id = cursor.lastrowid

    # Send email notification
    app_url = current_app.config.get('HOST', 'http://localhost:5000')
    coach_name = coach.name if coach else coach_email.split('@')[0]
    email_sent = send_coach_invitation_email(
        coach_email=coach_email,
        coach_name=coach_name,
        athlete_name=athlete.name,
        app_url=app_url,
        is_registered=(coach is not None)
    )

    return (relationship_id, email_sent)


def accept_coach_invitation(coach_id, athlete_id):
    """Coach accepts invitation from athlete

    Args:
        coach_id: ID of coach accepting
        athlete_id: ID of athlete who sent invitation

    Returns:
        True if successful

    Raises:
        ValueError: If invitation doesn't exist or is not pending
    """
    db = get_db()

    # Get invitation
    cursor = db.execute('''
        SELECT id, status FROM coach_athlete_relationships
        WHERE coach_id = ? AND athlete_id = ?
    ''', (coach_id, athlete_id))

    relationship = cursor.fetchone()
    if not relationship:
        raise ValueError('Invitation not found')

    if relationship[1] != 'pending':
        raise ValueError(f'Invitation is not pending (status: {relationship[1]})')

    # Accept invitation
    db.execute('''
        UPDATE coach_athlete_relationships
        SET status = 'active', accepted_at = ?
        WHERE id = ?
    ''', (datetime.utcnow().isoformat(), relationship[0]))

    db.commit()
    return True


def reject_coach_invitation(coach_id, athlete_id):
    """Coach rejects invitation from athlete

    Args:
        coach_id: ID of coach rejecting
        athlete_id: ID of athlete who sent invitation

    Returns:
        True if successful
    """
    db = get_db()

    db.execute('''
        DELETE FROM coach_athlete_relationships
        WHERE coach_id = ? AND athlete_id = ? AND status = 'pending'
    ''', (coach_id, athlete_id))

    db.commit()
    return True


def remove_coach_access(athlete_id, coach_id):
    """Athlete removes coach's access to their data

    Args:
        athlete_id: ID of athlete removing access
        coach_id: ID of coach to remove

    Returns:
        True if successful
    """
    db = get_db()

    db.execute('''
        UPDATE coach_athlete_relationships
        SET status = 'inactive'
        WHERE coach_id = ? AND athlete_id = ?
    ''', (coach_id, athlete_id))

    db.commit()
    return True


def get_pending_invitations(coach_id):
    """Get list of pending coach invitations (for coaches to accept)

    Args:
        coach_id: ID of coach

    Returns:
        List of dicts with invitation details
    """
    db = get_db()
    cursor = db.execute('''
        SELECT r.id, r.athlete_id, u.name, u.email, r.invited_at
        FROM coach_athlete_relationships r
        JOIN users u ON r.athlete_id = u.id
        WHERE r.coach_id = ? AND r.status = 'pending'
        ORDER BY r.invited_at DESC
    ''', (coach_id,))

    invitations = []
    for row in cursor.fetchall():
        invitations.append({
            'id': row[0],
            'athlete_id': row[1],
            'athlete_name': row[2],
            'athlete_email': row[3],
            'invited_at': row[4]
        })

    return invitations


def get_athlete_pending_coach_invitations(athlete_id):
    """Get list of pending coach invitations sent by athlete

    Args:
        athlete_id: ID of athlete

    Returns:
        List of dicts with invitation details including registration status
    """
    db = get_db()
    cursor = db.execute('''
        SELECT
            r.id,
            r.coach_id,
            r.coach_email,
            r.invited_at,
            u.name as coach_name,
            u.email as coach_user_email
        FROM coach_athlete_relationships r
        LEFT JOIN users u ON r.coach_id = u.id
        WHERE r.athlete_id = ? AND r.status = 'pending'
        ORDER BY r.invited_at DESC
    ''', (athlete_id,))

    invitations = []
    for row in cursor.fetchall():
        invitation = {
            'id': row[0],
            'invited_at': row[3]
        }

        if row[1]:  # coach_id is set - coach has registered
            invitation['coach_email'] = row[5]  # coach_user_email
            invitation['coach_name'] = row[4]
            invitation['is_registered'] = True
            invitation['status_text'] = 'Registered - waiting for acceptance'
        else:  # coach_email is set - coach not registered yet
            invitation['coach_email'] = row[2]  # coach_email from relationship
            invitation['coach_name'] = row[2].split('@')[0]
            invitation['is_registered'] = False
            invitation['status_text'] = 'Invitation sent - not registered yet'

        invitations.append(invitation)

    return invitations


def get_coach_athletes_list(coach_id):
    """Get detailed list of all athletes for a coach

    Args:
        coach_id: ID of coach

    Returns:
        List of dicts with athlete and relationship details
    """
    db = get_db()
    cursor = db.execute('''
        SELECT
            u.id,
            u.name,
            u.email,
            r.status,
            r.invited_at,
            r.accepted_at,
            COUNT(DISTINCT a.id) as activity_count
        FROM coach_athlete_relationships r
        JOIN users u ON r.athlete_id = u.id
        LEFT JOIN activities a ON u.id = a.user_id
        WHERE r.coach_id = ? AND r.status = 'active'
        GROUP BY u.id, u.name, u.email, r.status, r.invited_at, r.accepted_at
        ORDER BY u.name
    ''', (coach_id,))

    athletes = []
    for row in cursor.fetchall():
        athletes.append({
            'id': row[0],
            'name': row[1],
            'email': row[2],
            'status': row[3],
            'invited_at': row[4],
            'accepted_at': row[5],
            'activity_count': row[6]
        })

    return athletes
