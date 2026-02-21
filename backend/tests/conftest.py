import pytest
import requests
import os

@pytest.fixture(scope="session")
def api_base_url():
    """Get base URL from environment"""
    base_url = os.environ.get('EXPO_PUBLIC_BACKEND_URL')
    if not base_url:
        pytest.fail("EXPO_PUBLIC_BACKEND_URL not set in environment")
    return base_url.rstrip('/')

@pytest.fixture
def api_client(api_base_url):
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session
