import os
from flask import Flask
from flask_login import LoginManager
from config import config


def create_app(config_name=None):
    """
    Flask application factory.

    Args:
        config_name: Configuration name ('development', 'production', or None for default)

    Returns:
        Flask application instance
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config.get(config_name, config['default']))

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.user_login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        from app.models.user import User
        return User.get(int(user_id))

    # Initialize database
    from app.database import close_db, init_db
    with app.app_context():
        init_db()

    # Register database teardown
    app.teardown_appcontext(close_db)

    # Register custom Jinja2 filters
    from datetime import datetime as dt

    @app.template_filter('weekday')
    def weekday_filter(date_string):
        """Convert date string to weekday abbreviation"""
        try:
            date_obj = dt.strptime(date_string, '%Y-%m-%d')
            return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][date_obj.weekday()]
        except (ValueError, TypeError):
            return ''

    # Register context processor for athlete data (for coaches)
    @app.context_processor
    def inject_athlete_data():
        """Inject athlete information for coaches into all templates"""
        from flask_login import current_user
        from app.services.access_control_service import get_viewing_user_id, get_coach_athletes_list
        from app.models.user import User

        if not current_user.is_authenticated or not current_user.is_coach():
            return {}

        # Get list of athletes for this coach
        athletes = get_coach_athletes_list(current_user.id)

        # Get currently viewing athlete
        viewing_user_id = get_viewing_user_id()
        viewing_athlete = None
        if viewing_user_id and viewing_user_id != current_user.id:
            viewing_athlete = User.get(viewing_user_id)

        return {
            'coach_athletes': athletes,
            'viewing_athlete': viewing_athlete
        }

    # Register blueprints
    from app.auth import auth_bp
    from app.activities import activities_bp
    from app.api import api_bp
    from app.web import web_bp
    from app.admin import admin_bp
    from app.mcp_proxy import mcp_proxy_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(activities_bp, url_prefix='/api/activities')
    app.register_blueprint(api_bp)  # API endpoints at /api
    app.register_blueprint(web_bp)  # Web UI at root
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(mcp_proxy_bp)  # MCP proxy at /mcp

    return app
