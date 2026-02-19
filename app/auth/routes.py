import time
import secrets
from datetime import datetime
from flask import current_app, redirect, request, session, jsonify, render_template, flash, url_for
from flask_login import login_user, logout_user, login_required as flask_login_required, current_user
from stravalib.client import Client
from app.auth import auth_bp
from app.auth.user_auth import register_user, authenticate_user
from app.auth.decorators import anonymous_required
from app.database import get_db
from app.models.user import User


def save_tokens_to_db(access_token, refresh_token, expires_at, user_id, athlete_id=None, athlete_name=None):
    """Save Strava tokens to database for persistence

    Args:
        access_token: Strava access token
        refresh_token: Strava refresh token
        expires_at: Token expiration timestamp
        user_id: User ID (required for multi-user)
        athlete_id: Strava athlete ID (optional)
        athlete_name: Strava athlete name (optional)
    """
    db = get_db()
    now = datetime.utcnow().isoformat()

    # Check if tokens exist for this user
    cursor = db.execute('SELECT id FROM strava_tokens WHERE user_id = ?', (user_id,))
    existing = cursor.fetchone()

    if existing:
        db.execute('''
            UPDATE strava_tokens SET
                access_token = ?,
                refresh_token = ?,
                expires_at = ?,
                athlete_id = COALESCE(?, athlete_id),
                athlete_name = COALESCE(?, athlete_name),
                updated_at = ?
            WHERE user_id = ?
        ''', (access_token, refresh_token, expires_at, athlete_id, athlete_name, now, user_id))
    else:
        db.execute('''
            INSERT INTO strava_tokens (user_id, access_token, refresh_token, expires_at, athlete_id, athlete_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, access_token, refresh_token, expires_at, athlete_id, athlete_name, now, now))

    db.commit()


def load_tokens_from_db(user_id):
    """Load Strava tokens from database for a specific user

    Args:
        user_id: User ID

    Returns:
        Dictionary with token data or None
    """
    db = get_db()
    cursor = db.execute('SELECT * FROM strava_tokens WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def delete_tokens_from_db(user_id):
    """Delete Strava tokens from database for a specific user

    Args:
        user_id: User ID
    """
    db = get_db()
    db.execute('DELETE FROM strava_tokens WHERE user_id = ?', (user_id,))
    db.commit()


def refresh_access_token(refresh_token):
    """Refresh the access token using the refresh token"""
    client = Client()

    print(f"[OAuth] Attempting to refresh token...")

    try:
        token_response = client.refresh_access_token(
            client_id=current_app.config['STRAVA_CLIENT_ID'],
            client_secret=current_app.config['STRAVA_CLIENT_SECRET'],
            refresh_token=refresh_token
        )

        # Handle different response formats from stravalib
        if hasattr(token_response, 'get'):
            # Dictionary response
            new_access_token = token_response.get('access_token')
            new_refresh_token = token_response.get('refresh_token')
            new_expires_at = token_response.get('expires_at')
        else:
            # Object response (stravalib may return object with attributes)
            new_access_token = getattr(token_response, 'access_token', None)
            new_refresh_token = getattr(token_response, 'refresh_token', None)
            new_expires_at = getattr(token_response, 'expires_at', None)

        if not new_access_token:
            print(f"[OAuth] Token refresh response missing access_token: {token_response}")
            return None

        print(f"[OAuth] Token refresh successful, new token expires at {new_expires_at}")

        return {
            'access_token': new_access_token,
            'refresh_token': new_refresh_token or refresh_token,  # Keep old refresh token if new one not provided
            'expires_at': new_expires_at
        }
    except Exception as e:
        import traceback
        print(f"[OAuth] Token refresh failed: {e}")
        print(f"[OAuth] Refresh token used: {refresh_token[:10]}..." if refresh_token else "[OAuth] No refresh token")
        print(traceback.format_exc())
        return None


def ensure_valid_token():
    """
    Ensure we have a valid Strava access token for the current user.
    Loads from DB if not in session, refreshes if expired.
    Returns True if we have a valid token, False otherwise.

    Requires user to be logged in.
    """
    # Check if user is logged in
    if not current_user.is_authenticated:
        print("[OAuth] User not logged in")
        return False

    user_id = current_user.id
    current_time = time.time()

    # First check session
    if 'strava_access_token' in session and 'strava_expires_at' in session:
        expires_at = session['strava_expires_at']
        # Check if token is expired (with 5 minute buffer)
        if expires_at > current_time + 300:
            return True
        else:
            time_until_expiry = expires_at - current_time
            print(f"[OAuth] Session token expired or expiring soon (expires in {time_until_expiry:.0f}s)")

    # Try to load from database
    tokens = load_tokens_from_db(user_id)
    if not tokens:
        print(f"[OAuth] No tokens found in database for user {user_id}")
        return False

    expires_at = tokens['expires_at']

    # Check if token is expired (with 5 minute buffer)
    if expires_at > current_time + 300:
        # Token is valid, load into session
        print(f"[OAuth] Loaded valid token from database (expires in {expires_at - current_time:.0f}s)")
        session['strava_access_token'] = tokens['access_token']
        session['strava_refresh_token'] = tokens['refresh_token']
        session['strava_expires_at'] = tokens['expires_at']
        session['strava_athlete_id'] = tokens.get('athlete_id')
        session['strava_athlete_name'] = tokens.get('athlete_name')
        return True

    # Token is expired, try to refresh
    time_since_expiry = current_time - expires_at
    print(f"[OAuth] Token expired {time_since_expiry:.0f}s ago, attempting refresh...")

    if not tokens.get('refresh_token'):
        print("[OAuth] No refresh token available")
        delete_tokens_from_db(user_id)
        # Clear only Strava session keys
        session.pop('strava_access_token', None)
        session.pop('strava_refresh_token', None)
        session.pop('strava_expires_at', None)
        session.pop('strava_athlete_id', None)
        session.pop('strava_athlete_name', None)
        return False

    new_tokens = refresh_access_token(tokens['refresh_token'])

    if new_tokens and new_tokens.get('access_token'):
        # Save new tokens to DB and session
        save_tokens_to_db(
            new_tokens['access_token'],
            new_tokens['refresh_token'],
            new_tokens['expires_at'],
            user_id,
            tokens.get('athlete_id'),
            tokens.get('athlete_name')
        )
        session['strava_access_token'] = new_tokens['access_token']
        session['strava_refresh_token'] = new_tokens['refresh_token']
        session['strava_expires_at'] = new_tokens['expires_at']
        session['strava_athlete_id'] = tokens.get('athlete_id')
        session['strava_athlete_name'] = tokens.get('athlete_name')
        print(f"[OAuth] Token refreshed successfully, new expiry: {datetime.fromtimestamp(new_tokens['expires_at'])}")
        return True

    # Refresh failed, clear tokens
    print(f"[OAuth] Token refresh failed, clearing tokens - user needs to re-authenticate")
    delete_tokens_from_db(user_id)
    # Clear only Strava session keys
    session.pop('strava_access_token', None)
    session.pop('strava_refresh_token', None)
    session.pop('strava_expires_at', None)
    session.pop('strava_athlete_id', None)
    session.pop('strava_athlete_name', None)
    return False


@auth_bp.route('/strava/connect')
@flask_login_required
def strava_connect():
    """
    Initiate Strava OAuth flow.
    Redirects user to Strava authorization page.
    Requires user to be logged in.
    """
    client = Client()

    # Build authorization URL - READ ONLY access
    redirect_uri = current_app.config['STRAVA_REDIRECT_URI']
    client_id = current_app.config['STRAVA_CLIENT_ID']

    # Generate state parameter to prevent CSRF and code reuse
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_user_id'] = current_user.id  # Store user ID for callback

    # Debug: log OAuth configuration
    print(f"[OAuth] HOST: {current_app.config.get('HOST')}")
    print(f"[OAuth] STRAVA_REDIRECT_URI: {redirect_uri}")
    print(f"[OAuth] STRAVA_CLIENT_ID: {client_id}")
    print(f"[OAuth] User ID: {current_user.id}")
    print(f"[OAuth] State: {state[:10]}...")

    authorize_url = client.authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=['read_all', 'activity:read_all'],  # Read-only access, no write permissions
        state=state
    )

    print(f"[OAuth] Redirecting to: {authorize_url}")
    return redirect(authorize_url)


@auth_bp.route('/strava/callback')
def strava_callback():
    """
    Handle OAuth callback from Strava.
    Exchanges authorization code for access token and persists to database.
    """
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')

    if error:
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        flash(f'Strava authorization error: {error}', 'danger')
        return redirect('/')

    if not code:
        session.pop('oauth_state', None)
        session.pop('oauth_user_id', None)
        flash('No authorization code provided', 'danger')
        return redirect('/')

    # Validate state parameter to prevent CSRF and code reuse
    expected_state = session.pop('oauth_state', None)
    user_id = session.pop('oauth_user_id', None)

    if not expected_state or not user_id:
        # No state in session - this might be a page refresh or stale callback
        # Check if we already have valid tokens
        if ensure_valid_token():
            print("[OAuth] Callback with no state but already authenticated - ignoring")
            return redirect('/')
        flash('OAuth session expired. Please try connecting again.', 'warning')
        return redirect('/')

    if state != expected_state:
        print(f"[OAuth] State mismatch: expected {expected_state[:10]}..., got {state[:10] if state else 'None'}...")
        flash('Invalid OAuth state. Please try connecting again.', 'danger')
        return redirect('/')

    # Verify user is still logged in
    if not current_user.is_authenticated or current_user.id != user_id:
        flash('Session expired. Please log in and try connecting to Strava again.', 'warning')
        return redirect(url_for('auth.user_login'))

    client = Client()

    try:
        print(f"[OAuth] Exchanging authorization code for token (user_id={user_id})...")

        # Exchange code for token
        token_response = client.exchange_code_for_token(
            client_id=current_app.config['STRAVA_CLIENT_ID'],
            client_secret=current_app.config['STRAVA_CLIENT_SECRET'],
            code=code
        )

        # Handle different response formats from stravalib
        if hasattr(token_response, 'get'):
            access_token = token_response.get('access_token')
            refresh_token = token_response.get('refresh_token')
            expires_at = token_response.get('expires_at')
        else:
            access_token = getattr(token_response, 'access_token', None)
            refresh_token = getattr(token_response, 'refresh_token', None)
            expires_at = getattr(token_response, 'expires_at', None)

        if not access_token:
            raise Exception(f"No access token in response: {token_response}")

        # Store tokens in session
        session['strava_access_token'] = access_token
        session['strava_refresh_token'] = refresh_token
        session['strava_expires_at'] = expires_at

        # Fetch athlete data
        athlete_id = None
        athlete_name = 'Strava User'
        try:
            authenticated_client = Client(access_token=access_token)
            athlete = authenticated_client.get_athlete()
            athlete_id = athlete.id
            athlete_name = f"{athlete.firstname} {athlete.lastname}".strip()
            session['strava_athlete_id'] = athlete_id
            session['strava_athlete_name'] = athlete_name
        except Exception as athlete_error:
            print(f"Could not fetch athlete data: {athlete_error}")

        # Persist tokens to database
        save_tokens_to_db(access_token, refresh_token, expires_at, user_id, athlete_id, athlete_name)

        flash(f"Successfully connected to Strava as {athlete_name}", 'success')
        print(f"[OAuth] Successfully authenticated as {athlete_name} (ID: {athlete_id}, user_id={user_id})")
        print(f"[OAuth] Token expires at: {expires_at} ({datetime.fromtimestamp(expires_at) if expires_at else 'unknown'})")

        return redirect('/')

    except Exception as e:
        import traceback
        print(f"[OAuth] Error: {e}")
        print(traceback.format_exc())

        # Check if this is an "invalid code" error - likely a page refresh
        error_str = str(e).lower()
        if 'invalid' in error_str and 'code' in error_str:
            # Check if we already have valid tokens (page was refreshed after auth)
            if ensure_valid_token():
                print("[OAuth] Authorization code invalid but already have valid tokens - ignoring")
                return redirect('/')
            flash('Authorization code expired. Please try connecting again.', 'warning')
        else:
            flash(f"Authentication failed: {str(e)}", 'danger')

        return redirect('/')


@auth_bp.route('/strava/status')
@flask_login_required
def strava_status():
    """Check Strava authentication status for current user"""
    if ensure_valid_token():
        expires_at = session.get('strava_expires_at')
        expires_in = expires_at - time.time() if expires_at else 0
        return jsonify({
            'authenticated': True,
            'user_id': current_user.id,
            'athlete_id': session.get('strava_athlete_id'),
            'athlete_name': session.get('strava_athlete_name'),
            'expires_at': expires_at,
            'expires_at_formatted': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            'expires_in_seconds': int(expires_in),
            'expires_in_minutes': int(expires_in / 60)
        })
    else:
        return jsonify({'authenticated': False, 'user_id': current_user.id})


@auth_bp.route('/strava/debug')
@flask_login_required
def strava_debug():
    """Debug endpoint to check Strava token state for current user"""
    user_id = current_user.id
    tokens = load_tokens_from_db(user_id)
    current_time = time.time()

    result = {
        'user_id': user_id,
        'current_time': current_time,
        'current_time_formatted': datetime.fromtimestamp(current_time).isoformat(),
        'session': {
            'has_access_token': 'strava_access_token' in session,
            'has_refresh_token': 'strava_refresh_token' in session,
            'expires_at': session.get('strava_expires_at'),
            'athlete_name': session.get('strava_athlete_name')
        },
        'database': None
    }

    if tokens:
        expires_at = tokens.get('expires_at', 0)
        result['database'] = {
            'has_access_token': bool(tokens.get('access_token')),
            'has_refresh_token': bool(tokens.get('refresh_token')),
            'access_token_preview': tokens.get('access_token', '')[:10] + '...' if tokens.get('access_token') else None,
            'refresh_token_preview': tokens.get('refresh_token', '')[:10] + '...' if tokens.get('refresh_token') else None,
            'expires_at': expires_at,
            'expires_at_formatted': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            'is_expired': expires_at < current_time,
            'seconds_until_expiry': int(expires_at - current_time),
            'athlete_name': tokens.get('athlete_name')
        }

    return jsonify(result)


@auth_bp.route('/strava/force-refresh')
@flask_login_required
def strava_force_refresh():
    """Force refresh the Strava access token for current user"""
    user_id = current_user.id
    tokens = load_tokens_from_db(user_id)

    if not tokens or not tokens.get('refresh_token'):
        return jsonify({'success': False, 'error': 'No refresh token available'})

    new_tokens = refresh_access_token(tokens['refresh_token'])

    if new_tokens and new_tokens.get('access_token'):
        save_tokens_to_db(
            new_tokens['access_token'],
            new_tokens['refresh_token'],
            new_tokens['expires_at'],
            user_id,
            tokens.get('athlete_id'),
            tokens.get('athlete_name')
        )
        session['strava_access_token'] = new_tokens['access_token']
        session['strava_refresh_token'] = new_tokens['refresh_token']
        session['strava_expires_at'] = new_tokens['expires_at']

        return jsonify({
            'success': True,
            'expires_at': new_tokens['expires_at'],
            'expires_at_formatted': datetime.fromtimestamp(new_tokens['expires_at']).isoformat()
        })
    else:
        return jsonify({'success': False, 'error': 'Token refresh failed'})


@auth_bp.route('/strava/disconnect')
@flask_login_required
def strava_disconnect():
    """Disconnect Strava for current user (clear tokens)"""
    user_id = current_user.id
    delete_tokens_from_db(user_id)

    # Clear Strava session keys
    session.pop('strava_access_token', None)
    session.pop('strava_refresh_token', None)
    session.pop('strava_expires_at', None)
    session.pop('strava_athlete_id', None)
    session.pop('strava_athlete_name', None)

    flash('Disconnected from Strava', 'info')
    return redirect('/')


# ========== User Authentication Routes ==========

@auth_bp.route('/user/register', methods=['GET', 'POST'])
@anonymous_required
def user_register():
    """User registration with email/password"""
    if request.method == 'GET':
        return render_template('auth/register.html')

    # POST request - handle registration
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    password_confirm = request.form.get('password_confirm', '')
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'athlete')

    # Validate inputs
    if not email:
        flash('Email is required', 'danger')
        return render_template('auth/register.html')

    if not password:
        flash('Password is required', 'danger')
        return render_template('auth/register.html')

    if len(password) < 8:
        flash('Password must be at least 8 characters', 'danger')
        return render_template('auth/register.html')

    if password != password_confirm:
        flash('Passwords do not match', 'danger')
        return render_template('auth/register.html')

    if not name:
        flash('Name is required', 'danger')
        return render_template('auth/register.html')

    if role not in ['athlete', 'coach']:
        flash('Invalid role selected', 'danger')
        return render_template('auth/register.html')

    # Try to register
    try:
        user_id = register_user(email, password, name, role)
        user = User.get(user_id)

        # Log user in
        login_user(user)
        flash(f'Registration successful! Welcome, {name}', 'success')

        # Redirect to next page or home
        next_page = session.pop('next', None)
        return redirect(next_page or url_for('web.index'))

    except ValueError as e:
        flash(str(e), 'danger')
        return render_template('auth/register.html')
    except Exception as e:
        flash(f'Registration failed: {str(e)}', 'danger')
        return render_template('auth/register.html')


@auth_bp.route('/user/login', methods=['GET', 'POST'])
@anonymous_required
def user_login():
    """User login with email/password"""
    if request.method == 'GET':
        return render_template('auth/login.html')

    # POST request - handle login
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    remember = request.form.get('remember', False)

    if not email or not password:
        flash('Email and password are required', 'danger')
        return render_template('auth/login.html')

    # Try to authenticate
    try:
        user = authenticate_user(email, password)

        if user:
            login_user(user, remember=bool(remember))
            flash(f'Welcome back, {user.name}!', 'success')

            # Redirect to next page or home
            next_page = session.pop('next', None)
            return redirect(next_page or url_for('web.index'))
        else:
            flash('Invalid email or password', 'danger')
            return render_template('auth/login.html')

    except Exception as e:
        flash(f'Login failed: {str(e)}', 'danger')
        return render_template('auth/login.html')


@auth_bp.route('/user/logout')
@flask_login_required
def user_logout():
    """User logout (also clears Strava session)"""
    print(f"[LOGOUT] User {current_user.id} ({current_user.email}) logging out")
    print(f"[LOGOUT] Session before clear: {dict(session)}")

    user_id = current_user.id

    # Clear Strava tokens for this user
    delete_tokens_from_db(user_id)

    # Logout user
    logout_user()

    # Clear all session data
    for key in list(session.keys()):
        session.pop(key)

    print(f"[LOGOUT] Session after clear: {dict(session)}")
    print(f"[LOGOUT] Is authenticated: {current_user.is_authenticated}")

    # Flash message before creating response
    flash('You have been logged out', 'info')

    # Create response with redirect
    response = redirect(url_for('auth.user_login'))

    # Force clear session cookie
    response.set_cookie('session', '', expires=0)

    return response


def get_strava_client():
    """
    Get authenticated Strava client with automatic token refresh for current user.

    Returns:
        Client: Authenticated stravalib Client instance

    Raises:
        Exception: If not authenticated or no Strava connection
    """
    # Check if user is logged in
    if not current_user.is_authenticated:
        raise Exception('Not logged in. Please log in first.')

    # Try to ensure we have a valid Strava token
    if ensure_valid_token():
        client = Client(access_token=session['strava_access_token'])
        # Set refresh token if available for auto-refresh
        if 'strava_refresh_token' in session:
            client.refresh_token = session['strava_refresh_token']
        return client

    raise Exception('Not connected to Strava. Please connect your Strava account first.')


def is_authenticated():
    """Check if user is authenticated with valid Strava token"""
    return current_user.is_authenticated and ensure_valid_token()
