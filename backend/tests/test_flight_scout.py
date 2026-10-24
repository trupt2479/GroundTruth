from datetime import datetime, timezone
import pytest

from app.schemas.flight import (
    AircraftInfo,
    AlternativeFlight,
    FlightLeg,
    InboundTurnaround,
)
from app.services.flight_scout import AlternativeFlightScout
from app.services.prediction_engine import PredictionEngine


@pytest.mark.asyncio
async def test_flight_scout_find_alternatives():
    """Verify AlternativeFlightScout finds and ranks chronological alternative flights."""
    scout = AlternativeFlightScout(mock_mode=True)

    after_time = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    alternatives = await scout.find_alternative_flights(
        carrier="UA",
        origin_iata="ORD",
        destination_iata="EWR",
        after_time=after_time,
    )

    assert len(alternatives) == 2
    assert all(isinstance(alt, AlternativeFlight) for alt in alternatives)

    # First alternative: UA1588 departing at 19:30
    assert alternatives[0].flight_number == "UA1588"
    assert alternatives[0].carrier == "UA"
    assert alternatives[0].seats_available is True
    assert alternatives[0].standby_recommended is False

    # Second alternative: UA2104 departing at 20:45
    assert alternatives[1].flight_number == "UA2104"
    assert alternatives[1].standby_recommended is True

    # Chronologically sorted
    assert alternatives[0].departure_time < alternatives[1].departure_time


@pytest.mark.asyncio
async def test_prediction_engine_scouts_alternatives_on_expedite_rebooking():
    """Verify that when directive is EXPEDITE_REBOOKING, alternatives are automatically populated."""
    engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    # Severe delay at outstation (BDL) -> 90 min turnaround delay -> EXPEDITE_REBOOKING
    touchdown = datetime(2026, 10, 24, 18, 45, tzinfo=timezone.utc)

    aircraft = AircraftInfo(icao_type="B738", tail_number="N123UA", category="NARROWBODY")
    current_leg = FlightLeg(
        flight_number="UA1422",
        origin_iata="BDL",  # Outstation
        destination_iata="EWR",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep,
        status="SCHEDULED",
    )
    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown,
    )

    # Force scout mock to return test alternatives for this city pair test
    from unittest.mock import AsyncMock
    engine.scout.find_alternative_flights = AsyncMock(
        return_value=[
            AlternativeFlight(
                flight_number="UA1588",
                carrier="UA",
                departure_time=datetime(2026, 10, 24, 19, 30, tzinfo=timezone.utc),
                arrival_time=datetime(2026, 10, 24, 22, 0, tzinfo=timezone.utc),
                origin_iata="BDL",
                destination_iata="EWR",
                seats_available=True,
                standby_recommended=False,
            )
        ]
    )

    assessment = await engine.assess_flight_async(
        current_leg=current_leg,
        turnaround=turnaround,
        downstream_connection_layover_minutes=50,
    )

    assert assessment.rebooking_directive == "EXPEDITE_REBOOKING"
    assert len(assessment.alternative_flights) == 1
    assert assessment.alternative_flights[0].flight_number == "UA1588"
    assert assessment.alternative_flights[0].origin_iata == "BDL"
    assert assessment.alternative_flights[0].destination_iata == "EWR"


@pytest.mark.asyncio
async def test_prediction_engine_does_not_scout_on_relax():
    """Verify that when flight is on time (RELAX_IN_LOUNGE), alternative flights list remains empty."""
    engine = PredictionEngine()

    sched_dep = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    touchdown = datetime(2026, 10, 24, 17, 0, tzinfo=timezone.utc)

    aircraft = AircraftInfo(icao_type="B738", tail_number="N123UA", category="NARROWBODY")
    current_leg = FlightLeg(
        flight_number="UA1422",
        origin_iata="ORD",
        destination_iata="EWR",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep,
        status="SCHEDULED",
    )
    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown,
    )

    assessment = await engine.assess_flight_async(
        current_leg=current_leg,
        turnaround=turnaround,
    )

    assert assessment.rebooking_directive == "RELAX_IN_LOUNGE"
    assert len(assessment.alternative_flights) == 0
