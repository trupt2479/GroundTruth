import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from app.main import app
from app.schemas.flight import RealityAssessment
from app.services.aerodatabox_client import (
    AeroDataBoxRateLimitError,
    AeroDataBoxServiceUnavailableError,
)
from app.services.flight_aggregator import FlightAggregator


@pytest.fixture
def client():
    return TestClient(app)


def test_evaluate_flight_success(client):
    """Test GET /api/v1/flights/evaluate returns 200 OK with valid RealityAssessment schema."""
    response = client.get(
        "/api/v1/flights/evaluate",
        params={
            "carrier": "UA",
            "flight_num": "1422",
            "date": "2026-10-24",
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Validate against RealityAssessment Pydantic schema
    assessment = RealityAssessment.model_validate(data)
    assert assessment.flight_query.carrier == "UA"
    assert assessment.flight_query.flight_number == "1422"
    assert assessment.delay_lead_time_minutes >= 0
    assert assessment.rebooking_directive in [
        "RELAX_IN_LOUNGE",
        "MONITOR_CLOSELY",
        "EXPEDITE_REBOOKING",
    ]


def test_evaluate_flight_invalid_carrier_422(client):
    """Test GET /api/v1/flights/evaluate returns 422 on invalid carrier (lowercase or length)."""
    # Lowercase carrier
    response = client.get(
        "/api/v1/flights/evaluate",
        params={
            "carrier": "ua",
            "flight_num": "1422",
            "date": "2026-10-24",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert "error_code" in data
    assert "detail" in data

    # 3-character carrier code
    response2 = client.get(
        "/api/v1/flights/evaluate",
        params={
            "carrier": "UAL",
            "flight_num": "1422",
            "date": "2026-10-24",
        },
    )
    assert response2.status_code == 422


def test_evaluate_flight_invalid_date_422(client):
    """Test GET /api/v1/flights/evaluate returns 422 on invalid date format."""
    response = client.get(
        "/api/v1/flights/evaluate",
        params={
            "carrier": "UA",
            "flight_num": "1422",
            "date": "10-24-2026",  # Not YYYY-MM-DD
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert "error_code" in data


def test_evaluate_flight_upstream_service_unavailable_503(client):
    """Test GET /api/v1/flights/evaluate returns 503 when external APIs fail."""
    with patch(
        "app.services.flight_aggregator.FlightAggregator.get_flight_context",
        AsyncMock(
            side_effect=AeroDataBoxServiceUnavailableError("RapidAPI 503 Outage")
        ),
    ):
        response = client.get(
            "/api/v1/flights/evaluate",
            params={
                "carrier": "UA",
                "flight_num": "1422",
                "date": "2026-10-24",
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert data["error_code"] == "HTTP_503"
        assert "temporarily unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_sse_stream_initial_event_and_heartbeat():
    """Test SSE stream opens, sends initial event with text/event-stream, and delivers heartbeat."""
    from unittest.mock import MagicMock
    from app.api.v1.endpoints.stream import flight_event_generator
    from app.schemas.flight import FlightQuery
    from app.services.flight_aggregator import FlightAggregator
    from app.services.prediction_engine import PredictionEngine

    query = FlightQuery(
        carrier="UA",
        flight_number="1422",
        departure_date=date(2026, 10, 24),
    )
    aggregator = FlightAggregator()
    engine = PredictionEngine()

    mock_request = MagicMock()
    # Let is_disconnected be false for the initial yield and first tick, then true to exit cleanly
    disconnect_counter = [False, False, True]

    async def fake_is_disconnected():
        if disconnect_counter:
            return disconnect_counter.pop(0)
        return True

    mock_request.is_disconnected = fake_is_disconnected

    events = []
    async for event in flight_event_generator(
        flight_query=query,
        aggregator=aggregator,
        engine=engine,
        request=mock_request,
        heartbeat_interval=0.01,
        poll_interval=0.02,
    ):
        events.append(event)
        if len(events) >= 2:
            break

    assert len(events) >= 2
    assert "event: INITIAL" in events[0]
    assert "data: {" in events[0]
    assert "event: TICK" in events[1] or ": keep-alive" in events[1] or "event: UPDATE" in events[1]


