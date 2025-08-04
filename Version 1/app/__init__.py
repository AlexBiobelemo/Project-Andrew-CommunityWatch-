from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'info'
scheduler = APScheduler()


def create_app(config_class=Config):
    """Creates and configures an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    if not app.debug and not app.testing:
        if not scheduler.running:
            scheduler.init_app(app)
            scheduler.start()

            # Import and schedule the cleanup task
            from app.tasks import delete_old_issues
            if not scheduler.get_job('delete_old_issues_job'):
                scheduler.add_job(
                    id='delete_old_issues_job',
                    func=lambda: delete_old_issues(app),
                    trigger='interval',
                    days=1
                )

    from app.routes import bp as main_bp
    app.register_blueprint(main_bp)

    from app import models

    # Custom Jinja2 filter for formatting dates
    @app.template_filter('strftime')
    def _jinja2_filter_datetime(timestamp, fmt='%B %d, %Y'):
        if timestamp is None:
            return "N/A"
        dt_object = datetime.fromtimestamp(timestamp)
        return dt_object.strftime(fmt)

    return app
