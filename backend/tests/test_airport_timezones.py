from datetime import datetime, timedelta, timezone

from app.schemas.flight import AircraftInfo, FlightLeg, FlightQuery, InboundTurnaround
from app.services.airport_timezones import get_airport_timezone, to_local_iso
from app.services.prediction_engine import PredictionEngine


def _turnaround(dep):
    return InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=AircraftInfo(icao_type="B738", tail_number="N123DL", category="NARROWBODY"),
        mtt_minutes=45,
        estimated_touchdown=dep - timedelta(hours=2),
        earliest_possible_departure=dep - timedelta(hours=1, minutes=15),
    )



def test_airport_timezone_lookup():
    assert get_airport_timezone("LAX") == "America/Los_Angeles"
    assert get_airport_timezone("atl") == "America/New_York"
    assert get_airport_timezone("PHX") == "America/Phoenix"
    assert get_airport_timezone("ZZZ") is None
    assert get_airport_timezone(None) is None


def test_to_local_iso_offsets_and_dst():
    # Nov 8 2026 02:15 UTC -> LAX is PST (-08:00) after DST ends Nov 1
    dt = datetime(2026, 11, 8, 5, 15, tzinfo=timezone.utc)
    assert to_local_iso(dt, "America/Los_Angeles") == "2026-11-07T21:15:00-08:00"
    assert to_local_iso(dt, "America/New_York") == "2026-11-08T00:15:00-05:00"
    # Summer DST
    summer = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    assert to_local_iso(summer, "America/New_York") == "2026-07-01T08:00:00-04:00"
    # Naive treated as UTC; missing/invalid -> None
    assert to_local_iso(datetime(2026, 11, 8, 5, 15), "America/Los_Angeles") == "2026-11-07T21:15:00-08:00"
    assert to_local_iso(None, "America/Los_Angeles") is None
    assert to_local_iso(dt, None) is None
    assert to_local_iso(dt, "Not/AZone") is None


def test_assessment_exposes_airport_local_times():
    dep = datetime(2026, 11, 8, 5, 15, tzinfo=timezone.utc)
    arr = datetime(2026, 11, 8, 9, 30, tzinfo=timezone.utc)
    leg = FlightLeg(
        flight_number="DL783",
        origin_iata="LAX",
        destination_iata="ATL",
        scheduled_departure=dep,
        scheduled_arrival=arr,
        actual_departure=dep + timedelta(minutes=25),
        actual_arrival=arr + timedelta(minutes=12),
        status="SCHEDULED",
    )
    q = FlightQuery(carrier="DL", flight_number="783", departure_date=dep.date())
    a = PredictionEngine().assess_flight(current_leg=leg, turnaround=_turnaround(dep), flight_query=q)

    assert a.origin_tz == "America/Los_Angeles"
    assert a.destination_tz == "America/New_York"
    assert a.scheduled_departure_local == "2026-11-07T21:15:00-08:00"
    assert a.actual_departure_local == "2026-11-07T21:40:00-08:00"
    assert a.scheduled_arrival_local == "2026-11-08T04:30:00-05:00"
    assert a.actual_arrival_local == "2026-11-08T04:42:00-05:00"
    # UTC fields untouched
    assert a.scheduled_departure == dep


def test_unknown_airport_yields_null_local_fields():
    dep = datetime(2026, 11, 8, 5, 15, tzinfo=timezone.utc)
    leg = FlightLeg(
        flight_number="DL1",
        origin_iata="ZZZ",
        destination_iata="ATL",
        scheduled_departure=dep,
        scheduled_arrival=dep + timedelta(hours=3),
        status="SCHEDULED",
    )
    q = FlightQuery(carrier="DL", flight_number="1", departure_date=dep.date())
    a = PredictionEngine().assess_flight(current_leg=leg, turnaround=_turnaround(dep), flight_query=q)
    assert a.origin_tz is None
    assert a.scheduled_departure_local is None
    assert a.destination_tz == "America/New_York"
    assert a.scheduled_arrival_local is not None


def test_unknown_airport_falls_back_to_aerodatabox_raw_local():
    dep = datetime(2026, 11, 8, 5, 15, tzinfo=timezone.utc)
    leg = FlightLeg(
        flight_number="DL1",
        origin_iata="ZZZ",
        destination_iata="QQQ",
        scheduled_departure=dep,
        scheduled_arrival=dep + timedelta(hours=3),
        scheduled_departure_local="2026-11-08T05:15:00",
        actual_departure_local="2026-11-08T05:40:00",
        scheduled_arrival_local="2026-11-08T08:15:00",
        actual_arrival_local="2026-11-08T08:35:00",
        status="SCHEDULED",
    )
    q = FlightQuery(carrier="DL", flight_number="1", departure_date=dep.date())
    a = PredictionEngine().assess_flight(current_leg=leg, turnaround=_turnaround(dep), flight_query=q)
    assert a.origin_tz is None
    assert a.destination_tz is None
    assert a.scheduled_departure_local == "2026-11-08T05:15:00"
    assert a.actual_departure_local == "2026-11-08T05:40:00"
    assert a.scheduled_arrival_local == "2026-11-08T08:15:00"
    assert a.actual_arrival_local == "2026-11-08T08:35:00"


def test_airborne_equipment_swap_reconciliation():
    dep = datetime(2026, 11, 8, 5, 15, tzinfo=timezone.utc)
    arr = datetime(2026, 11, 8, 9, 30, tzinfo=timezone.utc)
    leg = FlightLeg(
        flight_number="DL783",
        origin_iata="LAX",
        destination_iata="ATL",
        scheduled_departure=dep,
        scheduled_arrival=arr,
        actual_departure=dep,
        actual_arrival=arr,
        status="ACTIVE",
    )
    # Stale turnaround had an inbound delay
    stale_turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=AircraftInfo(icao_type="B738", tail_number="N123DL", category="NARROWBODY"),
        mtt_minutes=45,
        estimated_touchdown=dep + timedelta(minutes=30),
        earliest_possible_departure=dep + timedelta(minutes=75),
    )
    live_telemetry = {
        "flight_status": "AIRBORNE",
        "telemetry_source": "BOOKED_FLIGHT",
        "baro_altitude_ft": 34000,
        "ground_speed_kts": 480,
    }
    q = FlightQuery(carrier="DL", flight_number="783", departure_date=dep.date())
    a = PredictionEngine().assess_flight(
        current_leg=leg,
        turnaround=stale_turnaround,
        flight_query=q,
        live_telemetry=live_telemetry,
    )
    assert a.is_unavoidable_delay is False
    assert a.rebooking_directive == "EN_ROUTE_ON_TIME"
    assert a.delay_lead_time_minutes == 0


def test_rollover_epoch_math_guard():
    # Departs 23:50 UTC on Nov 8; Inbound lands 00:15 UTC on Nov 9 (+45m MTT -> 01:00 UTC)
    dep = datetime(2026, 11, 8, 23, 50, tzinfo=timezone.utc)
    touchdown = datetime(2026, 11, 9, 0, 15, tzinfo=timezone.utc)
    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=AircraftInfo(icao_type="B738", tail_number="N123DL", category="NARROWBODY"),
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )
    leg = FlightLeg(
        flight_number="UA200",
        origin_iata="SFO",
        destination_iata="ORD",
        scheduled_departure=dep,
        scheduled_arrival=datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc),
        status="SCHEDULED",
    )
    q = FlightQuery(carrier="UA", flight_number="200", departure_date=dep.date())
    a = PredictionEngine().assess_flight(current_leg=leg, turnaround=turnaround, flight_query=q)

    # 01:00 - 23:50 = 70 minutes
    assert a.is_unavoidable_delay is True
    assert a.delay_lead_time_minutes == 70
