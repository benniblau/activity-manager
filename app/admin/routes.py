from flask import render_template, request, jsonify, redirect, url_for, flash, current_app, session
from flask_login import login_required, current_user
from app.admin import admin_bp
from app.repositories import TypeRepository
from app.repositories.api_key_repository import ApiKeyRepository
from app.utils.errors import ValidationError, AppError
from app.auth.user_auth import update_user_profile, update_password
from app.services.access_control_service import (
    invite_coach, get_pending_invitations, get_coach_athletes_list,
    accept_coach_invitation, reject_coach_invitation, remove_coach_access,
    set_viewing_user_id, get_athlete_pending_coach_invitations
)
from app.services.invitation_service import (
    create_invitation, cancel_invitation, get_invitations_sent_by
)
from app.utils.email import send_invitation_email
from app.auth.decorators import coach_required


@admin_bp.route('/')
@login_required
def index():
    """Admin dashboard"""
    return render_template('admin/index.html')


@admin_bp.route('/types')
def manage_types():
    """Extended activity types management page"""
    type_repo = TypeRepository()

    # Get extended types grouped by base sport type
    types_by_base = type_repo.get_extended_types_grouped_by_base()
    all_types = type_repo.get_extended_types()

    return render_template('admin/manage_types.html',
                           types_by_base=types_by_base,
                           all_types=all_types)


@admin_bp.route('/types', methods=['POST'])
def create_extended_type():
    """Create a new extended activity type"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Create extended type using repository
        type_repo = TypeRepository()
        extended_type = type_repo.create_extended_type(data)

        if request.is_json:
            return jsonify({
                'id': extended_type['id'],
                'message': 'Extended type created successfully'
            }), 201
        else:
            flash('Extended type created successfully', 'success')
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))


@admin_bp.route('/types/<int:type_id>', methods=['PUT', 'POST'])
def update_extended_type(type_id):
    """Update an extended activity type"""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Update extended type using repository
        type_repo = TypeRepository()
        type_repo.update_extended_type(type_id, data)

        if request.is_json:
            return jsonify({'message': 'Extended type updated successfully'}), 200
        else:
            flash('Extended type updated successfully', 'success')
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))


@admin_bp.route('/types/<int:type_id>', methods=['DELETE'])
def delete_extended_type(type_id):
    """Soft delete an extended activity type (set is_active = 0)"""
    try:
        type_repo = TypeRepository()
        type_repo.delete_extended_type(type_id)

        if request.is_json:
            return jsonify({'message': 'Extended type deleted successfully'}), 200
        else:
            flash('Extended type deleted successfully', 'success')
            return redirect(url_for('admin.manage_types'))

    except ValidationError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))
    except AppError as e:
        if request.is_json:
            return jsonify(e.to_dict()), e.status_code
        else:
            flash(e.message, 'error')
            return redirect(url_for('admin.manage_types'))


# ========== User Profile Management ==========

@admin_bp.route('/profile')
@login_required
def profile():
    """User profile management page"""
    # Get Strava connection status
    from app.auth.routes import load_tokens_from_db
    strava_tokens = load_tokens_from_db(current_user.id)
    is_strava_connected = strava_tokens is not None
    strava_athlete_name = strava_tokens.get('athlete_name') if strava_tokens else None

    # Get coaches and pending coach invitations (for athletes)
    coaches = []
    pending_coach_invitations = []
    if current_user.is_athlete():
        coaches = current_user.get_coaches()
        pending_coach_invitations = get_athlete_pending_coach_invitations(current_user.id)

    # Get athletes and pending invitations (for coaches)
    athletes = []
    pending_invitations = []
    if current_user.is_coach():
        athletes = get_coach_athletes_list(current_user.id)
        pending_invitations = get_pending_invitations(current_user.id)

    invitations_sent = get_invitations_sent_by(current_user.id)

    api_keys = ApiKeyRepository().get_keys_for_user(current_user.id)
    new_api_key = session.pop('new_api_key', None)

    return render_template(
        'admin/profile.html',
        user=current_user,
        is_strava_connected=is_strava_connected,
        strava_athlete_name=strava_athlete_name,
        coaches=coaches,
        athletes=athletes,
        pending_invitations=pending_invitations,
        pending_coach_invitations=pending_coach_invitations,
        invitations_sent=invitations_sent,
        api_keys=api_keys,
        new_api_key=new_api_key
    )


@admin_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile (name/email)"""
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()

    try:
        update_user_profile(current_user.id, name=name if name else None, email=email if email else None)
        flash('Profile updated successfully', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validate
    if not current_password:
        flash('Current password is required', 'danger')
        return redirect(url_for('admin.profile'))

    if not new_password:
        flash('New password is required', 'danger')
        return redirect(url_for('admin.profile'))

    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('admin.profile'))

    try:
        update_password(current_user.id, current_password, new_password)
        flash('Password changed successfully', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


# ========== Coach-Athlete Relationship Management ==========

@admin_bp.route('/coaches/invite', methods=['POST'])
@login_required
def invite_coach_route():
    """Invite a coach by email (athlete only)"""
    if not current_user.is_athlete():
        flash('Only athletes can invite coaches', 'danger')
        return redirect(url_for('admin.profile'))

    coach_email = request.form.get('coach_email', '').strip()

    if not coach_email:
        flash('Coach email is required', 'danger')
        return redirect(url_for('admin.profile'))

    try:
        relationship_id, email_sent = invite_coach(current_user.id, coach_email)

        # Provide detailed feedback about invitation status
        if email_sent:
            flash(f'Invitation sent to {coach_email}. An email notification has been sent.', 'success')
        else:
            flash(f'Invitation created for {coach_email}, but email notification could not be sent. '
                  f'Please notify the coach directly to check their profile for the pending invitation.', 'warning')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/coaches/<int:coach_id>/remove', methods=['POST'])
@login_required
def remove_coach_route(coach_id):
    """Remove coach access (athlete only)"""
    if not current_user.is_athlete():
        flash('Only athletes can remove coaches', 'danger')
        return redirect(url_for('admin.profile'))

    try:
        remove_coach_access(current_user.id, coach_id)
        flash('Coach access removed', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/athletes/<int:athlete_id>/accept', methods=['POST'])
@login_required
@coach_required
def accept_invitation(athlete_id):
    """Accept athlete invitation (coach only)"""
    try:
        accept_coach_invitation(current_user.id, athlete_id)
        flash('Invitation accepted', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/athletes/<int:athlete_id>/reject', methods=['POST'])
@login_required
@coach_required
def reject_invitation(athlete_id):
    """Reject athlete invitation (coach only)"""
    try:
        reject_coach_invitation(current_user.id, athlete_id)
        flash('Invitation rejected', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/invitations/send', methods=['POST'])
@login_required
def send_invitation_route():
    """Send a registration invitation by email"""
    invited_email = request.form.get('invited_email', '').strip()
    invited_role = request.form.get('invited_role', 'athlete')

    if not invited_email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('admin.profile'))

    try:
        invitation = create_invitation(current_user.id, invited_email, invited_role)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('admin.profile'))

    # Build registration URL with token
    host = current_app.config.get('HOST', 'http://localhost:5001')
    registration_url = f"{host}{url_for('auth.user_register')}?token={invitation['token']}"

    # Attempt to send email
    expiry_days = current_app.config.get('INVITATION_EXPIRY_DAYS', 30)
    email_sent = send_invitation_email(
        invited_email=invited_email,
        invited_role=invited_role,
        inviter_name=current_user.name,
        registration_url=registration_url,
        expiry_days=expiry_days
    )

    if email_sent:
        flash(f'Invitation sent to {invited_email}.', 'success')
    else:
        flash(
            f'Invitation created for {invited_email}, but the email could not be sent. '
            f'Share this registration link directly: {registration_url}',
            'warning'
        )

    return redirect(url_for('admin.profile'))


@admin_bp.route('/invitations/<int:invitation_id>/cancel', methods=['POST'])
@login_required
def cancel_invitation_route(invitation_id):
    """Cancel a pending invitation"""
    try:
        cancel_invitation(invitation_id, current_user.id)
        flash('Invitation cancelled.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('admin.profile'))


@admin_bp.route('/api-keys', methods=['POST'])
@login_required
def create_api_key():
    """Create a new MCP API key"""
    scope = request.form.get('scope', 'read')
    if scope not in ('read', 'readwrite'):
        flash('Invalid scope.', 'danger')
        return redirect(url_for('admin.profile'))

    label = request.form.get('label', '').strip() or None
    result = ApiKeyRepository().create_key(current_user.id, scope, label)
    session['new_api_key'] = result['raw_key']
    flash('API key created successfully.', 'success')
    return redirect(url_for('admin.profile'))


@admin_bp.route('/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
def delete_api_key(key_id):
    """Revoke an API key"""
    deleted = ApiKeyRepository().delete_key(key_id, current_user.id)
    if deleted:
        flash('API key revoked.', 'success')
    else:
        flash('Key not found.', 'danger')
    return redirect(url_for('admin.profile'))


@admin_bp.route('/switch-view/<int:user_id>', methods=['POST'])
@login_required
@coach_required
def switch_view(user_id):
    """Switch viewing context to different athlete (coach only)"""
    try:
        # Switch to selected athlete's data
        if set_viewing_user_id(user_id):
            from app.models.user import User
            viewing_user = User.get(user_id)
            flash(f'Now viewing {viewing_user.name}\'s data', 'success')
        else:
            flash('Access denied - you cannot view this athlete\'s data', 'danger')
    except Exception as e:
        flash(str(e), 'danger')

    return redirect(url_for('web.index'))
