from flask import current_app, redirect, request, session, jsonify, url_for
from stravalib.client import Client
from app.auth import auth_bp


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
    Exchanges authorization code for access token.
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

        # Debug: print token_response structure
        print(f"Token response type: {type(token_response)}")
        print(f"Token response keys: {token_response.keys() if hasattr(token_response, 'keys') else 'N/A'}")
        print(f"Token response: {token_response}")

        # Store tokens in session
        session['access_token'] = token_response.get('access_token')
        session['refresh_token'] = token_response.get('refresh_token')
        session['expires_at'] = token_response.get('expires_at')

        # Fetch athlete data using the access token
        # In stravalib 2.4, athlete data is not included in token response
        try:
            authenticated_client = Client(access_token=session['access_token'])
            athlete = authenticated_client.get_athlete()
            session['athlete_id'] = athlete.id
            session['athlete_name'] = f"{athlete.firstname} {athlete.lastname}".strip()
        except Exception as athlete_error:
            print(f"Could not fetch athlete data: {athlete_error}")
            session['athlete_name'] = 'Strava User'

        session['auth_success'] = f"Successfully connected to Strava as {session['athlete_name']}"

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
    if 'access_token' in session:
        return jsonify({
            'authenticated': True,
            'athlete_id': session.get('athlete_id'),
            'expires_at': session.get('expires_at')
        })
    else:
        return jsonify({'authenticated': False})


@auth_bp.route('/logout')
def logout():
    """Clear session and log out"""
    session.clear()
    return redirect('/')


def get_strava_client():
    """
    Get authenticated Strava client.

    Returns:
        Client: Authenticated stravalib Client instance

    Raises:
        Exception: If not authenticated
    """
    if 'access_token' not in session:
        # Fall back to config tokens if available
        access_token = current_app.config.get('STRAVA_ACCESS_TOKEN')
        if access_token:
            client = Client(access_token=access_token)
            return client
        raise Exception('Not authenticated. Please login first.')

    client = Client(access_token=session['access_token'])
    return client
