from datetime import datetime, timedelta, timezone
import pytest

from app.schemas.flight import (
    AircraftInfo,
    CrewDutyAssessment,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
)
from app.services.crew_duty_watchdog import CrewDutyWatchdog
from app.services.prediction_engine import PredictionEngine


@pytest.fixture
def watchdog():
    return CrewDutyWatchdog()


@pytest.fixture
def prediction_engine():
    return PredictionEngine()


def test_crew_duty_calculation_across_rotations(watchdog):
    """Validates duty accumulation across 2 prior rotation legs under FAA Part 117."""
    base_time = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)

    # Leg n-2: 06:00 - 08:30 (Crew report time: 05:00 UTC)
    leg_n2 = FlightLeg(
        flight_number="UA101",
        origin_iata="EWR",
        destination_iata="ORD",
        scheduled_departure=base_time,
        scheduled_arrival=base_time + timedelta(hours=2, minutes=30),
        status="COMPLETED",
    )

    # Leg n-1: 09:30 - 12:00
    leg_n1 = FlightLeg(
        flight_number="UA102",
        origin_iata="ORD",
        destination_iata="DEN",
        scheduled_departure=base_time + timedelta(hours=3, minutes=30),
        scheduled_arrival=base_time + timedelta(hours=6),
        status="COMPLETED",
    )

    # Current leg: scheduled 13:00 - 15:30
    current_leg = FlightLeg(
        flight_number="UA103",
        origin_iata="DEN",
        destination_iata="SFO",
        scheduled_departure=base_time + timedelta(hours=7),
        scheduled_arrival=base_time + timedelta(hours=9, minutes=30),
        status="SCHEDULED",
    )

    # Earliest departure is on-time (13:00)
    calculated_earliest_departure = current_leg.scheduled_departure

    assessment: CrewDutyAssessment = watchdog.assess_crew_duty(
        current_leg=current_leg,
        previous_legs=[leg_n2, leg_n1],
        calculated_earliest_departure=calculated_earliest_departure,
    )

    # Expected show-up: 05:00 UTC. Duty end: 15:30 UTC -> 10.5 hours = 630 mins
    # Remaining buffer: 840 - 630 = 210 mins (> 120 mins -> LOW risk)
    assert assessment.elapsed_duty_minutes == 630
    assert assessment.remaining_buffer_minutes == 210
    assert assessment.timeout_risk == "LOW"
    assert "Well within FAA Part 117 limits" in assessment.risk_summary


def test_crew_timeout_high_risk_escalation(watchdog, prediction_engine):
    """Validates timeout_risk == 'HIGH' when remaining buffer < 60m and verifies rebooking escalation."""
    base_time = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)

    # Leg n-2: 06:00 - 09:00 (Report time: 05:00 UTC)
    leg_n2 = FlightLeg(
        flight_number="UA201",
        origin_iata="ORD",
        destination_iata="IAH",
        scheduled_departure=base_time,
        scheduled_arrival=base_time + timedelta(hours=3),
        status="COMPLETED",
    )

    # Leg n-1: 10:00 - 13:00
    leg_n1 = FlightLeg(
        flight_number="UA202",
        origin_iata="IAH",
        destination_iata="LAX",
        scheduled_departure=base_time + timedelta(hours=4),
        scheduled_arrival=base_time + timedelta(hours=7),
        status="COMPLETED",
    )

    # Current leg: scheduled 14:00 - 17:00 (3h duration)
    current_leg = FlightLeg(
        flight_number="UA203",
        origin_iata="LAX",
        destination_iata="SFO",
        scheduled_departure=base_time + timedelta(hours=8),
        scheduled_arrival=base_time + timedelta(hours=11),
        status="SCHEDULED",
    )

    # Severe cascading delay pushes earliest departure to 17:30 UTC
    # Duty start: 05:00 UTC. Projected arrival: 17:30 + 3h = 20:30 UTC
    # Total duty: 15.5 hours = 930 mins. Remaining buffer: 840 - 930 = -90 mins (< 60m -> HIGH)
    delayed_earliest_dep = base_time + timedelta(hours=11, minutes=30)

    duty_assessment: CrewDutyAssessment = watchdog.assess_crew_duty(
        current_leg=current_leg,
        previous_legs=[leg_n2, leg_n1],
        calculated_earliest_departure=delayed_earliest_dep,
    )

    assert duty_assessment.timeout_risk == "HIGH"
    assert duty_assessment.remaining_buffer_minutes < 60
    assert "crew timeout risk" in duty_assessment.risk_summary

    # Test full prediction engine integration
    aircraft = AircraftInfo(icao_type="B738", tail_number="N12345", category="NARROWBODY")
    turnaround = InboundTurnaround(
        previous_legs=[leg_n2, leg_n1],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=delayed_earliest_dep - timedelta(minutes=45),
        earliest_possible_departure=delayed_earliest_dep,
    )

    flight_query = FlightQuery(carrier="UA", flight_number="203", departure_date="2026-10-24")

    reality = prediction_engine.assess_flight(
        flight_query=flight_query,
        current_leg=current_leg,
        turnaround=turnaround,
    )

    assert reality.is_unavoidable_delay is True
    assert reality.rebooking_directive == "EXPEDITE_REBOOKING"
    assert reality.crew_duty is not None
    assert reality.crew_duty.timeout_risk == "HIGH"


def test_crew_duty_moderate_risk(watchdog):
    """Validates MODERATE risk when remaining buffer is between 60 and 120 minutes."""
    base_time = datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)

    # Leg n-1: 06:00 - 10:00 (Crew report time: 05:00 UTC)
    leg_n1 = FlightLeg(
        flight_number="AA449",
        origin_iata="DFW",
        destination_iata="MIA",
        scheduled_departure=base_time,
        scheduled_arrival=base_time + timedelta(hours=4),
        status="COMPLETED",
    )

    # Current leg: scheduled 14:00 - 17:00 (3h duration)
    current_leg = FlightLeg(
        flight_number="AA450",
        origin_iata="MIA",
        destination_iata="JFK",
        scheduled_departure=base_time + timedelta(hours=8),  # 14:00
        scheduled_arrival=base_time + timedelta(hours=11),    # 17:00 (3h duration)
        status="SCHEDULED",
    )

    # Delay earliest dep to 14:30 -> duty end at 17:30 UTC
    # Initial report: 05:00 UTC. Duty end: 17:30 UTC. Elapsed: 12.5 hrs = 750 mins
    # Remaining buffer: 840 - 750 = 90 mins (between 60 and 120 -> MODERATE)
    delayed_dep = base_time + timedelta(hours=8, minutes=30)

    assessment = watchdog.assess_crew_duty(
        current_leg=current_leg,
        previous_legs=[leg_n1],
        calculated_earliest_departure=delayed_dep,
    )

    assert assessment.timeout_risk == "MODERATE"
    assert 60 <= assessment.remaining_buffer_minutes <= 120
    assert "Further delays will trigger crew legality timeout" in assessment.risk_summary
