import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _normalize_host(host):
    """Ensure HOST has a proper URL scheme (http:// or https://)"""
    if not host:
        return 'http://localhost:5000'
    if not host.startswith('http://') and not host.startswith('https://'):
        # Default to http:// for localhost, https:// for everything else
        if 'localhost' in host or '127.0.0.1' in host:
            return f'http://{host}'
        return f'https://{host}'
    return host


class Config:
    """Base configuration class"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

    # Host configuration (used for OAuth callbacks)
    # In production, set HOST to your full URL (e.g., https://activity.example.com)
    HOST = _normalize_host(os.environ.get('HOST'))

    # Database
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or os.path.join(BASE_DIR, "activities.db")

    # Strava API Credentials
    STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
    STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')
    STRAVA_ACCESS_TOKEN = os.environ.get('STRAVA_ACCESS_TOKEN')
    STRAVA_REFRESH_TOKEN = os.environ.get('STRAVA_REFRESH_TOKEN')

    # Strava OAuth
    STRAVA_AUTHORIZE_URL = 'https://www.strava.com/oauth/authorize'
    STRAVA_TOKEN_URL = 'https://www.strava.com/oauth/token'
    STRAVA_API_BASE_URL = 'https://www.strava.com/api/v3'
    # Redirect URI built from HOST, or can be overridden directly
    STRAVA_REDIRECT_URI = os.environ.get('STRAVA_REDIRECT_URI') or f"{_normalize_host(os.environ.get('HOST'))}/auth/strava/callback"

    # Email Configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    FROM_EMAIL = os.environ.get('FROM_EMAIL') or os.environ.get('SMTP_USERNAME')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'

    # In production, all sensitive values should come from environment variables
    # Remove the fallback defaults for security
    SECRET_KEY = os.environ.get('SECRET_KEY')
    STRAVA_CLIENT_ID = os.environ.get('STRAVA_CLIENT_ID')
    STRAVA_CLIENT_SECRET = os.environ.get('STRAVA_CLIENT_SECRET')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
