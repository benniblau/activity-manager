import time
import secrets
from datetime import datetime
from flask import current_app, redirect, request, session, jsonify
from stravalib.client import Client
from app.auth import auth_bp
from app.database import get_db


def save_tokens_to_db(access_token, refresh_token, expires_at, athlete_id=None, athlete_name=None):
    """Save Strava tokens to database for persistence"""
    db = get_db()
    now = datetime.utcnow().isoformat()

    # Check if tokens exist
    cursor = db.execute('SELECT id FROM strava_tokens WHERE id = 1')
    exists = cursor.fetchone()

    if exists:
        db.execute('''
            UPDATE strava_tokens SET
                access_token = ?,
                refresh_token = ?,
                expires_at = ?,
                athlete_id = COALESCE(?, athlete_id),
                athlete_name = COALESCE(?, athlete_name),
                updated_at = ?
            WHERE id = 1
        ''', (access_token, refresh_token, expires_at, athlete_id, athlete_name, now))
    else:
        db.execute('''
            INSERT INTO strava_tokens (id, access_token, refresh_token, expires_at, athlete_id, athlete_name, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ''', (access_token, refresh_token, expires_at, athlete_id, athlete_name, now, now))

    db.commit()


def load_tokens_from_db():
    """Load Strava tokens from database"""
    db = get_db()
    cursor = db.execute('SELECT * FROM strava_tokens WHERE id = 1')
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


def delete_tokens_from_db():
    """Delete Strava tokens from database"""
    db = get_db()
    db.execute('DELETE FROM strava_tokens WHERE id = 1')
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
    Ensure we have a valid access token.
    Loads from DB if not in session, refreshes if expired.
    Returns True if we have a valid token, False otherwise.
    """
    current_time = time.time()

    # First check session
    if 'access_token' in session and 'expires_at' in session:
        expires_at = session['expires_at']
        # Check if token is expired (with 5 minute buffer)
        if expires_at > current_time + 300:
            return True
        else:
            time_until_expiry = expires_at - current_time
            print(f"[OAuth] Session token expired or expiring soon (expires in {time_until_expiry:.0f}s)")

    # Try to load from database
    tokens = load_tokens_from_db()
    if not tokens:
        print("[OAuth] No tokens found in database")
        return False

    expires_at = tokens['expires_at']

    # Check if token is expired (with 5 minute buffer)
    if expires_at > current_time + 300:
        # Token is valid, load into session
        print(f"[OAuth] Loaded valid token from database (expires in {expires_at - current_time:.0f}s)")
        session['access_token'] = tokens['access_token']
        session['refresh_token'] = tokens['refresh_token']
        session['expires_at'] = tokens['expires_at']
        session['athlete_id'] = tokens.get('athlete_id')
        session['athlete_name'] = tokens.get('athlete_name')
        return True

    # Token is expired, try to refresh
    time_since_expiry = current_time - expires_at
    print(f"[OAuth] Token expired {time_since_expiry:.0f}s ago, attempting refresh...")

    if not tokens.get('refresh_token'):
        print("[OAuth] No refresh token available")
        delete_tokens_from_db()
        session.clear()
        return False

    new_tokens = refresh_access_token(tokens['refresh_token'])

    if new_tokens and new_tokens.get('access_token'):
        # Save new tokens to DB and session
        save_tokens_to_db(
            new_tokens['access_token'],
            new_tokens['refresh_token'],
            new_tokens['expires_at'],
            tokens.get('athlete_id'),
            tokens.get('athlete_name')
        )
        session['access_token'] = new_tokens['access_token']
        session['refresh_token'] = new_tokens['refresh_token']
        session['expires_at'] = new_tokens['expires_at']
        session['athlete_id'] = tokens.get('athlete_id')
        session['athlete_name'] = tokens.get('athlete_name')
        print(f"[OAuth] Token refreshed successfully, new expiry: {datetime.fromtimestamp(new_tokens['expires_at'])}")
        return True

    # Refresh failed, clear tokens
    print(f"[OAuth] Token refresh failed, clearing tokens - user needs to re-authenticate")
    delete_tokens_from_db()
    session.clear()
    return False


@auth_bp.route('/login')
def login():
    """
    Initiate Strava OAuth flow.
    Redirects user to Strava authorization page.
    """
    client = Client()

    # Build authorization URL - READ ONLY access
    redirect_uri = current_app.config['STRAVA_REDIRECT_URI']
    client_id = current_app.config['STRAVA_CLIENT_ID']

    # Generate state parameter to prevent CSRF and code reuse
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    # Debug: log OAuth configuration
    print(f"[OAuth] HOST: {current_app.config.get('HOST')}")
    print(f"[OAuth] STRAVA_REDIRECT_URI: {redirect_uri}")
    print(f"[OAuth] STRAVA_CLIENT_ID: {client_id}")
    print(f"[OAuth] State: {state[:10]}...")

    authorize_url = client.authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=['read_all', 'activity:read_all'],  # Read-only access, no write permissions
        state=state
    )

    print(f"[OAuth] Redirecting to: {authorize_url}")
    return redirect(authorize_url)


@auth_bp.route('/callback')
def callback():
    """
    Handle OAuth callback from Strava.
    Exchanges authorization code for access token and persists to database.
    """
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state')

    if error:
        session.pop('oauth_state', None)
        session['auth_error'] = f'Strava authorization error: {error}'
        return redirect('/')

    if not code:
        session.pop('oauth_state', None)
        session['auth_error'] = 'No authorization code provided'
        return redirect('/')

    # Validate state parameter to prevent CSRF and code reuse
    expected_state = session.pop('oauth_state', None)
    if not expected_state:
        # No state in session - this might be a page refresh or stale callback
        # Check if we already have valid tokens
        if ensure_valid_token():
            print("[OAuth] Callback with no state but already authenticated - ignoring")
            return redirect('/')
        session['auth_error'] = 'OAuth session expired. Please try connecting again.'
        return redirect('/')

    if state != expected_state:
        print(f"[OAuth] State mismatch: expected {expected_state[:10]}..., got {state[:10] if state else 'None'}...")
        session['auth_error'] = 'Invalid OAuth state. Please try connecting again.'
        return redirect('/')

    client = Client()

    try:
        print(f"[OAuth] Exchanging authorization code for token...")

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
        session['access_token'] = access_token
        session['refresh_token'] = refresh_token
        session['expires_at'] = expires_at

        # Fetch athlete data
        athlete_id = None
        athlete_name = 'Strava User'
        try:
            authenticated_client = Client(access_token=access_token)
            athlete = authenticated_client.get_athlete()
            athlete_id = athlete.id
            athlete_name = f"{athlete.firstname} {athlete.lastname}".strip()
            session['athlete_id'] = athlete_id
            session['athlete_name'] = athlete_name
        except Exception as athlete_error:
            print(f"Could not fetch athlete data: {athlete_error}")

        # Persist tokens to database
        save_tokens_to_db(access_token, refresh_token, expires_at, athlete_id, athlete_name)

        session['auth_success'] = f"Successfully connected to Strava as {athlete_name}"
        print(f"[OAuth] Successfully authenticated as {athlete_name} (ID: {athlete_id})")
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
            session['auth_error'] = 'Authorization code expired. Please try connecting again.'
        else:
            session['auth_error'] = f"Authentication failed: {str(e)}"

        return redirect('/')


@auth_bp.route('/status')
def status():
    """Check authentication status"""
    if ensure_valid_token():
        expires_at = session.get('expires_at')
        expires_in = expires_at - time.time() if expires_at else 0
        return jsonify({
            'authenticated': True,
            'athlete_id': session.get('athlete_id'),
            'athlete_name': session.get('athlete_name'),
            'expires_at': expires_at,
            'expires_at_formatted': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            'expires_in_seconds': int(expires_in),
            'expires_in_minutes': int(expires_in / 60)
        })
    else:
        return jsonify({'authenticated': False})


@auth_bp.route('/debug')
def debug():
    """Debug endpoint to check token state"""
    tokens = load_tokens_from_db()
    current_time = time.time()

    result = {
        'current_time': current_time,
        'current_time_formatted': datetime.fromtimestamp(current_time).isoformat(),
        'session': {
            'has_access_token': 'access_token' in session,
            'has_refresh_token': 'refresh_token' in session,
            'expires_at': session.get('expires_at'),
            'athlete_name': session.get('athlete_name')
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


@auth_bp.route('/force-refresh')
def force_refresh():
    """Force refresh the access token"""
    tokens = load_tokens_from_db()
    if not tokens or not tokens.get('refresh_token'):
        return jsonify({'success': False, 'error': 'No refresh token available'})

    new_tokens = refresh_access_token(tokens['refresh_token'])

    if new_tokens and new_tokens.get('access_token'):
        save_tokens_to_db(
            new_tokens['access_token'],
            new_tokens['refresh_token'],
            new_tokens['expires_at'],
            tokens.get('athlete_id'),
            tokens.get('athlete_name')
        )
        session['access_token'] = new_tokens['access_token']
        session['refresh_token'] = new_tokens['refresh_token']
        session['expires_at'] = new_tokens['expires_at']

        return jsonify({
            'success': True,
            'expires_at': new_tokens['expires_at'],
            'expires_at_formatted': datetime.fromtimestamp(new_tokens['expires_at']).isoformat()
        })
    else:
        return jsonify({'success': False, 'error': 'Token refresh failed'})


@auth_bp.route('/logout')
def logout():
    """Clear session and database tokens"""
    delete_tokens_from_db()
    session.clear()
    return redirect('/')


def get_strava_client():
    """
    Get authenticated Strava client with automatic token refresh.

    Returns:
        Client: Authenticated stravalib Client instance

    Raises:
        Exception: If not authenticated
    """
    # Try to ensure we have a valid token
    if ensure_valid_token():
        client = Client(access_token=session['access_token'])
        # Set refresh token if available for auto-refresh
        if 'refresh_token' in session:
            client.refresh_token = session['refresh_token']
        return client

    # Fall back to config tokens if available (for backward compatibility)
    access_token = current_app.config.get('STRAVA_ACCESS_TOKEN')
    if access_token:
        client = Client(access_token=access_token)
        refresh_token = current_app.config.get('STRAVA_REFRESH_TOKEN')
        if refresh_token:
            client.refresh_token = refresh_token
        return client

    raise Exception('Not authenticated. Please login first.')


def is_authenticated():
    """Check if user is authenticated with valid token"""
    return ensure_valid_token()
