from datetime import date, datetime, timedelta, timezone
import pytest

from app.schemas.flight import (
    AircraftInfo,
    AirspaceAdvisory,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
)
from app.services.faa_nas_client import FaaNasClient
from app.services.prediction_engine import PredictionEngine


@pytest.mark.asyncio
async def test_faa_nas_mock_fixture_parsing():
    """Verify parsing active FAA XML status fixture into airport status."""
    client = FaaNasClient(mock_mode=True)

    # 1. Test Ground Stop at ORD
    ord_status = await client.get_airport_airspace_status("ORD")
    assert ord_status is not None
    assert ord_status["airport_iata"] == "ORD"
    assert ord_status["status_type"] == "GROUND_STOP"
    assert ord_status["reason"] == "THUNDERSTORMS"
    assert ord_status["avg_delay_minutes"] == 75
    assert ord_status["advisory_active"] is True

    # 2. Test Ground Delay Program at EWR
    ewr_status = await client.get_airport_airspace_status("EWR")
    assert ewr_status is not None
    assert ewr_status["airport_iata"] == "EWR"
    assert ewr_status["status_type"] == "GROUND_DELAY_PROGRAM"
    assert ewr_status["reason"] == "LOW CEILINGS"
    assert ewr_status["avg_delay_minutes"] == 45
    assert ewr_status["advisory_active"] is True

    # 3. Test Normal airport with no advisories
    sfo_status = await client.get_airport_airspace_status("SFO")
    assert sfo_status is not None
    assert sfo_status["airport_iata"] == "SFO"
    assert sfo_status["status_type"] == "NORMAL"
    assert sfo_status["advisory_active"] is False


@pytest.mark.asyncio
async def test_prediction_engine_ground_stop_escalation():
    """Test prediction engine forces unavoidable delay and EXPEDITE_REBOOKING when Ground Stop is active."""
    engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    touchdown = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)

    aircraft = AircraftInfo(icao_type="B738", tail_number="N123UA", category="NARROWBODY")
    current_leg = FlightLeg(
        flight_number="UA1422",
        origin_iata="ORD",
        destination_iata="EWR",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2),
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

    # Active FAA Ground Stop advisory at ORD (origin)
    advisory = AirspaceAdvisory(
        airport_iata="ORD",
        program_type="GROUND_STOP",
        reason="THUNDERSTORMS",
        avg_delay_minutes=75,
        advisory_active=True,
    )

    assessment = engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
        airspace_advisory=advisory,
    )

    # Escalated outcomes
    assert assessment.is_unavoidable_delay is True
    assert assessment.delay_lead_time_minutes >= 75
    assert assessment.rebooking_directive == "EXPEDITE_REBOOKING"
    assert assessment.airspace_advisory is not None
    assert assessment.airspace_advisory.program_type == "GROUND_STOP"


@pytest.mark.asyncio
async def test_prediction_engine_ground_delay_program_injection():
    """Test prediction engine injects FAA GDP delay into physical departure calculation."""
    engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc)
    touchdown = datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc)

    aircraft = AircraftInfo(icao_type="A320", tail_number="N456UA", category="NARROWBODY")
    current_leg = FlightLeg(
        flight_number="UA500",
        origin_iata="EWR",
        destination_iata="ORD",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2),
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    # Active FAA Ground Delay Program with 45 min delay
    advisory = AirspaceAdvisory(
        airport_iata="EWR",
        program_type="GROUND_DELAY_PROGRAM",
        reason="LOW CEILINGS",
        avg_delay_minutes=45,
        advisory_active=True,
    )

    assessment = engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
        airspace_advisory=advisory,
    )

    assert assessment.is_unavoidable_delay is True
    assert assessment.delay_lead_time_minutes >= 45
    assert assessment.airspace_advisory.program_type == "GROUND_DELAY_PROGRAM"
