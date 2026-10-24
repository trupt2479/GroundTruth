import asyncio
from datetime import date, datetime, timedelta, timezone
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas.flight import (
    AircraftInfo,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
)
from app.services.action_engine import ActionEngine
from app.services.flight_aggregator import FlightAggregator
from app.services.prediction_engine import PredictionEngine
from app.services.swap_evaluator import SwapEvaluator
from app.services.turnaround_engine import TurnaroundEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_e2e_browser_search_to_evaluation_flow(client):
    """GT-P5-03: Simulates full search -> API evaluation call -> schema verification."""
    query_params = {
        "carrier": "UA",
        "flight_num": "1422",
        "date": "2026-10-24",
    }

    # First Call: Triggers ingestion -> aggregation -> evaluation calculation -> cache write
    response = client.get("/api/v1/flights/evaluate", params=query_params)
    assert response.status_code == 200
    data = response.json()

    assessment = RealityAssessment.model_validate(data)
    assert assessment.flight_query.carrier == "UA"
    assert assessment.flight_query.flight_number == "1422"
    assert assessment.calculated_earliest_departure is not None
    assert assessment.rebooking_directive in [
        "RELAX_IN_LOUNGE",
        "MONITOR_CLOSELY",
        "EXPEDITE_REBOOKING",
    ]


def test_e2e_cached_evaluation_latency_benchmark(client, monkeypatch):
    """GT-P5-03: Benchmarks response latency to verify cached evaluation returns in < 50ms."""
    from app.services.cache_service import CacheService
    from tests.test_ingestion_cache import MockAsyncRedisClient

    # Use simulated fast in-memory Redis client for local benchmark
    fake_redis = MockAsyncRedisClient()
    monkeypatch.setattr(CacheService, "_get_client", lambda self: fake_redis)

    query_params = {
        "carrier": "UA",
        "flight_num": "1422",
        "date": "2026-10-24",
    }

    # Prime cache (first call populates in-memory cache)
    prime_resp = client.get("/api/v1/flights/evaluate", params=query_params)
    assert prime_resp.status_code == 200

    # Benchmark cached read
    latencies = []
    for _ in range(5):
        start = time.perf_counter()
        resp = client.get("/api/v1/flights/evaluate", params=query_params)
        duration_ms = (time.perf_counter() - start) * 1000
        latencies.append(duration_ms)
        assert resp.status_code == 200

    min_latency = min(latencies)
    # Verification: In-memory/local cached round-trip is < 50ms
    assert min_latency < 50.0, f"Expected < 50ms, got {min_latency:.2f}ms"



def test_scenario_1_outstation_misconnection_e2e():
    """Scenario 1 (Outstation Misconnection):

    Inbound aircraft arrives severely late at an outstation (e.g. BDL) with downstream connection.
    Confirms end-to-end prompt to rebook immediately (EXPEDITE_REBOOKING).
    """
    prediction_engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 16, 0, tzinfo=timezone.utc)
    # Severe inbound delay: Touchdown at 16:45 (needed was 15:15 for 45 min turn)
    touchdown = datetime(2026, 10, 24, 16, 45, tzinfo=timezone.utc)

    aircraft = AircraftInfo(
        icao_type="B738",
        tail_number="N2479U",
        category="NARROWBODY",
    )

    current_leg = FlightLeg(
        flight_number="UA1984",
        origin_iata="BDL",  # Outstation
        destination_iata="ORD",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2, minutes=30),
        actual_departure=sched_dep,  # Airline claims still on schedule
        actual_arrival=None,
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    # Downstream connection layover is 50 minutes at ORD; 90 min delay guarantees misconnection
    assessment = prediction_engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
        downstream_connection_layover_minutes=50,
    )

    assert assessment.is_unavoidable_delay is True
    assert assessment.delay_lead_time_minutes == 90
    assert assessment.swap_evaluation.swap_probability == "NEAR_ZERO"
    assert assessment.rebooking_directive == "EXPEDITE_REBOOKING"


def test_scenario_2_hub_spare_buffer_e2e():
    """Scenario 2 (Hub Spare Buffer):

    Inbound aircraft arrives late at a Fortress Hub (ATL). Airline maintains spare aircraft/crews.
    Confirms gate monitor directive (MONITOR_CLOSELY).
    """
    prediction_engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)
    # Inbound delay of 50 minutes: Touchdown at 14:05 (ideal was 13:15 for 45m MTT)
    touchdown = datetime(2026, 10, 24, 14, 5, tzinfo=timezone.utc)

    aircraft = AircraftInfo(
        icao_type="A321",
        tail_number="N301DN",
        category="NARROWBODY",
    )

    current_leg = FlightLeg(
        flight_number="DL992",
        origin_iata="ATL",  # Fortress Hub
        destination_iata="MCO",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=1, minutes=30),
        actual_departure=sched_dep,
        actual_arrival=None,
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    assessment = prediction_engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
    )

    assert assessment.is_unavoidable_delay is True
    assert assessment.delay_lead_time_minutes == 50
    assert assessment.swap_evaluation.origin_is_hub is True
    assert assessment.swap_evaluation.hub_type == "FORTRESS_HUB"
    assert assessment.swap_evaluation.swap_probability == "HIGH"
    assert assessment.rebooking_directive == "MONITOR_CLOSELY"


@pytest.mark.asyncio
async def test_e2e_sse_stream_pipeline():
    """GT-P5-03: End-to-end SSE stream delivery verification with simulated events."""
    from app.api.v1.endpoints.stream import flight_event_generator

    query = FlightQuery(
        carrier="UA",
        flight_number="1422",
        departure_date=date(2026, 10, 24),
    )
    aggregator = FlightAggregator()
    engine = PredictionEngine()

    mock_request = MagicMock()
    disconnect_signals = [False, False, True]

    async def fake_disconnect():
        if disconnect_signals:
            return disconnect_signals.pop(0)
        return True

    mock_request.is_disconnected = fake_disconnect

    received_events = []
    async for raw_event in flight_event_generator(
        flight_query=query,
        aggregator=aggregator,
        engine=engine,
        request=mock_request,
        heartbeat_interval=0.01,
        poll_interval=0.01,
    ):
        received_events.append(raw_event)
        if len(received_events) >= 2:
            break

    assert len(received_events) >= 2
    assert "event: INITIAL" in received_events[0]
    assert '"carrier": "UA"' in received_events[0]
    assert '"flight_number": "1422"' in received_events[0]

