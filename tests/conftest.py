"""Pytest configuration and fixtures for testing"""

import pytest
import tempfile
import os
from app import create_app
from app.database import get_db, init_db


@pytest.fixture(scope='session')
def app():
    """Create and configure a test Flask application"""
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()

    # Create app with test configuration
    app = create_app({
        'TESTING': True,
        'DATABASE_PATH': db_path,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False
    })

    # Initialize the database
    with app.app_context():
        init_db()

    yield app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the app"""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """Get database connection for testing

    Note: This fixture has function scope, so each test gets a clean database
    """
    with app.app_context():
        db = get_db()

        # Clear all tables before each test
        db.execute('DELETE FROM activities')
        db.execute('DELETE FROM extended_activity_types WHERE id > 100')  # Keep seed data
        db.execute('DELETE FROM days')
        db.execute('DELETE FROM gear')
        db.commit()

        yield db


@pytest.fixture(scope='function')
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers():
    """Fixture for authentication headers"""
    return {
        'Authorization': 'Bearer test-token'
    }


@pytest.fixture
def mock_strava_client(mocker):
    """Mock Strava client for testing"""
    client = mocker.Mock()
    client.get_activities = mocker.Mock(return_value=[])
    client.get_activity = mocker.Mock()
    return client
