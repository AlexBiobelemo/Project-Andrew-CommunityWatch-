import sys
import os
import pytest

# Add the project's root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Issue

@pytest.fixture()
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use an in-memory database
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler testing
    })

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture()
def client(app):
    """A test client for the app."""
    return app.test_client()
