"""
Initialize the Flask application and its extensions for CommunityWatch.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from datetime import datetime
from config import Config

# Initialize Flask extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'
scheduler = APScheduler()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
cache = Cache()  # Initialize Flask-Caching

def create_app(config_class=Config):
    """
    Create and configure a Flask application instance.

    Args:
        config_class: The configuration class to use (defaults to Config).

    Returns:
        Flask: Configured Flask application instance.
    """
    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure Flask-Caching
    app.config['CACHE_TYPE'] = 'SimpleCache'  # Use in-memory cache
    app.config['CACHE_DEFAULT_TIMEOUT'] = 3600  # Cache for 1 hour (3600 seconds)

    # Validate configuration
    config_class.validate(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)  # Initialize cache

    # Import User model and define user_loader for Flask-Login
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        """
        Load a user from the database by their ID for Flask-Login.

        Args:
            user_id: The ID of the user to load (stored in session).

        Returns:
            User: The User object, or None if not found.
        """
        return db.session.get(User, int(user_id))

    # Configure scheduler for non-debug, non-testing environments
    if not app.debug and not app.testing:
        if not scheduler.running:
            scheduler.init_app(app)
            scheduler.start()

            # Schedule cleanup task
            from app.tasks import delete_old_issues
            if not scheduler.get_job('delete_old_issues_job'):
                scheduler.add_job(
                    id='delete_old_issues_job',
                    func=lambda: delete_old_issues(app),
                    trigger='interval',
                    days=1,
                    replace_existing=True
                )

    # Register blueprints
    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    # Import models
    from app import models

    # Custom Jinja2 filter for formatting dates
    @app.template_filter('strftime')
    def format_datetime(timestamp, fmt='%B %d, %Y'):
        """
        Format a timestamp for display in templates.

        Args:
            timestamp: Unix timestamp or datetime object.
            fmt: Format string for strftime (default: '%B %d, %Y').

        Returns:
            str: Formatted date string or "N/A" if timestamp is None.
        """
        if timestamp is None:
            return "N/A"
        if isinstance(timestamp, datetime):
            return timestamp.strftime(fmt)
        return datetime.fromtimestamp(timestamp).strftime(fmt)

    return app
