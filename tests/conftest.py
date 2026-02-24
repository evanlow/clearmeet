"""
Shared pytest fixtures for all test modules.

Provides authenticated client fixture for testing protected routes.
"""
import pytest
from app import create_app


@pytest.fixture
def app():
    """Create test Flask application."""
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    app.config['SESSION_TYPE'] = 'null'  # Use simple sessions for testing
    return app


@pytest.fixture
def client(app):
    """Create test client with automatic authentication for protected routes."""
    client = app.test_client()
    
    # Log in with test credentials
    with client:
        client.post('/login', data={
            'username': app.config['AUTH_USERNAME'],
            'password': app.config['AUTH_PASSWORD']
        }, follow_redirects=False)
    
    return client


@pytest.fixture
def unauthenticated_client(app):
    """Create test client without authentication (for testing login flow)."""
    return app.test_client()


@pytest.fixture
def logged_in_client(app):
    """Alias for client fixture (for backwards compatibility)."""
    return client(app)
