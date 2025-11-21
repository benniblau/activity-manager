import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory of the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration class"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

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
    STRAVA_REDIRECT_URI = os.environ.get('STRAVA_REDIRECT_URI') or 'http://localhost:5001/auth/callback'


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
