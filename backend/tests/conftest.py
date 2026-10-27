import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def enforce_test_mock_mode(monkeypatch):
    """Ensure test suite runs in isolated mock ingestion mode independent of local .env."""
    monkeypatch.setattr(settings, "MOCK_INGESTION", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", None)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)


@pytest.fixture
def client():
    return TestClient(app)
