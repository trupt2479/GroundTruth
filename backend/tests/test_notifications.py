from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas.flight import (
    AircraftInfo,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
    SwapHeuristic,
)
from app.schemas.notification import NotificationResponse, NotificationSubscription
from app.services.cache_service import CacheService
from app.services.notification_service import NotificationService
from tests.test_ingestion_cache import MockAsyncRedisClient


@pytest.fixture
def mock_cache_service():
    service = CacheService()
    fake_client = MockAsyncRedisClient()
    service._get_client = lambda: fake_client
    return service


@pytest.fixture
def notification_service(mock_cache_service):
    return NotificationService(cache_service=mock_cache_service)


@pytest.fixture
def client(monkeypatch):
    fake_client = MockAsyncRedisClient()
    monkeypatch.setattr(CacheService, "_get_client", lambda self: fake_client)
    return TestClient(app)


@pytest.fixture
def sample_reality_assessment():
    flight_query = FlightQuery(
        carrier="UA",
        flight_number="1422",
        departure_date=date(2026, 10, 24),
    )
    sched_dep = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    swap = SwapHeuristic(
        origin_is_hub=False,
        hub_type="OUTSTATION",
        swap_probability="NEAR_ZERO",
    )
    return RealityAssessment(
        flight_query=flight_query,
        official_airline_departure=sched_dep,
        calculated_earliest_departure=sched_dep + timedelta(minutes=45),
        delay_lead_time_minutes=45,
        is_unavoidable_delay=True,
        swap_evaluation=swap,
        rebooking_directive="EXPEDITE_REBOOKING",
    )


@pytest.mark.asyncio
async def test_subscription_redis_persistence(notification_service):
    """GT-ADV-04: Test saving and retrieving subscriptions from Redis."""
    sub_sms = NotificationSubscription(
        flight_carrier="UA",
        flight_number="1422",
        flight_date="2026-10-24",
        recipient_type="SMS",
        destination="+15551234567",
        alert_on_delay=True,
    )
    sub_webhook = NotificationSubscription(
        flight_carrier="UA",
        flight_number="1422",
        flight_date="2026-10-24",
        recipient_type="WEBHOOK",
        destination="https://api.example.com/webhook",
        alert_on_delay=True,
    )

    success_sms = await notification_service.subscribe(sub_sms)
    assert success_sms is True

    success_webhook = await notification_service.subscribe(sub_webhook)
    assert success_webhook is True

    # Retrieve subscribers
    subscribers = await notification_service.get_subscribers("UA", "1422", "2026-10-24")
    assert len(subscribers) == 2
    assert any(s.recipient_type == "SMS" and s.destination == "+15551234567" for s in subscribers)
    assert any(s.recipient_type == "WEBHOOK" and s.destination == "https://api.example.com/webhook" for s in subscribers)


@pytest.mark.asyncio
async def test_dispatch_mock_sms_on_unavoidable_delay(notification_service, sample_reality_assessment, caplog):
    """GT-ADV-04: Test mock SMS formatting and dispatch logic on is_unavoidable_delay = True."""
    sub = NotificationSubscription(
        flight_carrier="UA",
        flight_number="1422",
        flight_date="2026-10-24",
        recipient_type="SMS",
        destination="+15551234567",
        alert_on_delay=True,
    )
    await notification_service.subscribe(sub)

    with caplog.at_level("INFO"):
        dispatched_count = await notification_service.dispatch_assessment_alerts(sample_reality_assessment)

    assert dispatched_count == 1
    assert "[MOCK SMS to +15551234567]" in caplog.text
    assert "UA1422 on 2026-10-24 has a confirmed 45m physical delay" in caplog.text
    assert "Rebooking directive: EXPEDITE_REBOOKING" in caplog.text


@pytest.mark.asyncio
async def test_dispatch_webhook_payload(notification_service, sample_reality_assessment):
    """GT-ADV-04: Test webhook dispatch asynchronously posting JSON payload."""
    sub = NotificationSubscription(
        flight_carrier="UA",
        flight_number="1422",
        flight_date="2026-10-24",
        recipient_type="WEBHOOK",
        destination="https://api.example.com/hooks/flights",
        alert_on_delay=True,
    )
    await notification_service.subscribe(sub)

    mock_post = AsyncMock()
    with patch("httpx.AsyncClient.post", mock_post):
        dispatched_count = await notification_service.dispatch_assessment_alerts(sample_reality_assessment)

    assert dispatched_count == 1
    mock_post.assert_awaited_once()
    called_url = mock_post.await_args[0][0]
    called_json = mock_post.await_args.kwargs["json"]
    assert called_url == "https://api.example.com/hooks/flights"
    assert called_json["flight_query"]["carrier"] == "UA"
    assert called_json["flight_query"]["flight_number"] == "1422"
    assert called_json["is_unavoidable_delay"] is True


def test_api_subscribe_endpoint_success(client):
    """GT-ADV-04: Test POST /api/v1/notifications/subscribe returns 201 Created."""
    payload = {
        "flight_carrier": "UA",
        "flight_number": "1422",
        "flight_date": "2026-10-24",
        "recipient_type": "SMS",
        "destination": "+15551234567",
        "alert_on_delay": True,
        "alert_on_crew_timeout": True,
        "alert_on_swap": True,
    }
    response = client.post("/api/v1/notifications/subscribe", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "+15551234567" in data["message"]
    assert data["subscription"]["destination"] == "+15551234567"
    assert data["subscription"]["flight_carrier"] == "UA"


def test_api_subscribe_endpoint_validation_errors(client):
    """GT-ADV-04: Test POST /api/v1/notifications/subscribe rejects invalid inputs with 422."""
    # Invalid carrier length
    resp1 = client.post(
        "/api/v1/notifications/subscribe",
        json={
            "flight_carrier": "UNITED",
            "flight_number": "1422",
            "flight_date": "2026-10-24",
            "recipient_type": "SMS",
            "destination": "+15551234567",
        },
    )
    assert resp1.status_code == 422

    # Invalid phone format (not E.164)
    resp2 = client.post(
        "/api/v1/notifications/subscribe",
        json={
            "flight_carrier": "UA",
            "flight_number": "1422",
            "flight_date": "2026-10-24",
            "recipient_type": "SMS",
            "destination": "555-1234",
        },
    )
    assert resp2.status_code == 422

    # Invalid webhook URL (not HTTP/HTTPS)
    resp3 = client.post(
        "/api/v1/notifications/subscribe",
        json={
            "flight_carrier": "UA",
            "flight_number": "1422",
            "flight_date": "2026-10-24",
            "recipient_type": "WEBHOOK",
            "destination": "ftp://example.com/bad",
        },
    )
    assert resp3.status_code == 422
