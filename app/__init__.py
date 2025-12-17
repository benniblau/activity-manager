import os
from flask import Flask
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

    app = Flask(__name__, instance_relative_config=True)

    # Load configuration
    app.config.from_object(config.get(config_name, config['default']))

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

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

    # Register blueprints
    from app.auth import auth_bp
    from app.activities import activities_bp
    from app.web import web_bp
    from app.planning import planning_bp
    from app.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(activities_bp, url_prefix='/api/activities')
    app.register_blueprint(web_bp)  # Web UI at root
    app.register_blueprint(planning_bp, url_prefix='/planning')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    return app
