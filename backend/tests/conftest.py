import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app
from app.services.cache_service import CacheService
from tests.test_ingestion_cache import MockAsyncRedisClient


@pytest.fixture(autouse=True)
def enforce_test_mock_mode(monkeypatch):
    """Ensure test suite runs in isolated mock ingestion mode independent of local .env."""
    monkeypatch.setattr(settings, "MOCK_INGESTION", True)
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", None)
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)
    monkeypatch.setattr(settings, "REDIS_HOST", "localhost")

    # Fast in-memory mock Redis for tests
    fake_redis = MockAsyncRedisClient()
    monkeypatch.setattr(CacheService, "_get_client", lambda self: fake_redis)


@pytest.fixture
def client():
    return TestClient(app)
