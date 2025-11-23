import time
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

    try:
        token_response = client.refresh_access_token(
            client_id=current_app.config['STRAVA_CLIENT_ID'],
            client_secret=current_app.config['STRAVA_CLIENT_SECRET'],
            refresh_token=refresh_token
        )

        return {
            'access_token': token_response.get('access_token'),
            'refresh_token': token_response.get('refresh_token'),
            'expires_at': token_response.get('expires_at')
        }
    except Exception as e:
        print(f"[OAuth] Token refresh failed: {e}")
        return None


def ensure_valid_token():
    """
    Ensure we have a valid access token.
    Loads from DB if not in session, refreshes if expired.
    Returns True if we have a valid token, False otherwise.
    """
    # First check session
    if 'access_token' in session and 'expires_at' in session:
        # Check if token is expired (with 5 minute buffer)
        if session['expires_at'] > time.time() + 300:
            return True

    # Try to load from database
    tokens = load_tokens_from_db()
    if not tokens:
        return False

    # Check if token is expired (with 5 minute buffer)
    if tokens['expires_at'] > time.time() + 300:
        # Token is valid, load into session
        session['access_token'] = tokens['access_token']
        session['refresh_token'] = tokens['refresh_token']
        session['expires_at'] = tokens['expires_at']
        session['athlete_id'] = tokens.get('athlete_id')
        session['athlete_name'] = tokens.get('athlete_name')
        return True

    # Token is expired, try to refresh
    print(f"[OAuth] Token expired, refreshing...")
    new_tokens = refresh_access_token(tokens['refresh_token'])

    if new_tokens:
        # Save new tokens to DB and session
        save_tokens_to_db(
            new_tokens['access_token'],
            new_tokens['refresh_token'],
            new_tokens['expires_at']
        )
        session['access_token'] = new_tokens['access_token']
        session['refresh_token'] = new_tokens['refresh_token']
        session['expires_at'] = new_tokens['expires_at']
        session['athlete_id'] = tokens.get('athlete_id')
        session['athlete_name'] = tokens.get('athlete_name')
        print(f"[OAuth] Token refreshed successfully")
        return True

    # Refresh failed, clear tokens
    print(f"[OAuth] Token refresh failed, clearing tokens")
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

    # Debug: log OAuth configuration
    print(f"[OAuth] HOST: {current_app.config.get('HOST')}")
    print(f"[OAuth] STRAVA_REDIRECT_URI: {redirect_uri}")
    print(f"[OAuth] STRAVA_CLIENT_ID: {client_id}")

    authorize_url = client.authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=['read_all', 'activity:read_all']  # Read-only access, no write permissions
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

    if error:
        session['auth_error'] = error
        return redirect('/')

    if not code:
        session['auth_error'] = 'No authorization code provided'
        return redirect('/')

    client = Client()

    try:
        # Exchange code for token
        token_response = client.exchange_code_for_token(
            client_id=current_app.config['STRAVA_CLIENT_ID'],
            client_secret=current_app.config['STRAVA_CLIENT_SECRET'],
            code=code
        )

        access_token = token_response.get('access_token')
        refresh_token = token_response.get('refresh_token')
        expires_at = token_response.get('expires_at')

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

        return redirect('/')

    except Exception as e:
        import traceback
        print(f"OAuth error: {e}")
        print(traceback.format_exc())
        session['auth_error'] = f"Authentication failed: {str(e)}"
        return redirect('/')


@auth_bp.route('/status')
def status():
    """Check authentication status"""
    if ensure_valid_token():
        return jsonify({
            'authenticated': True,
            'athlete_id': session.get('athlete_id'),
            'athlete_name': session.get('athlete_name'),
            'expires_at': session.get('expires_at')
        })
    else:
        return jsonify({'authenticated': False})


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
        return Client(access_token=session['access_token'])

    # Fall back to config tokens if available (for backward compatibility)
    access_token = current_app.config.get('STRAVA_ACCESS_TOKEN')
    if access_token:
        return Client(access_token=access_token)

    raise Exception('Not authenticated. Please login first.')


def is_authenticated():
    """Check if user is authenticated with valid token"""
    return ensure_valid_token()
