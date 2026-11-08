from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.flight import AircraftInfo, FlightLeg, FlightQuery, InboundTurnaround
from app.services.aerodatabox_client import AeroDataBoxClient
from app.services.flight_aggregator import FlightAggregator
from app.services.opensky_client import OpenSkyClient
from app.services.prediction_engine import PredictionEngine


@pytest.mark.asyncio
async def test_booked_flight_callsign_prioritization_and_isolation():
    """GT-BOOK-01: Booked flight callsign is queried and airborne telemetry attached as BOOKED_FLIGHT.

    Inbound rotation telemetry must be strictly isolated to turnaround.live_telemetry.
    """
    mock_adb = MagicMock()
    mock_adb.mock_mode = False
    mock_adb.get_flight_status = AsyncMock(
        return_value={
            "status": "Active",
            "callsign": "DAL783",
            "number": "DL783",
            "departure": {
                "airport": {"iata": "LAX", "name": "Los Angeles International"},
                "scheduledTime": {"utc": "2026-11-05 13:00Z"},
                "actualTime": {"utc": "2026-11-05 13:10Z"},
            },
            "arrival": {
                "airport": {"iata": "ATL", "name": "Hartsfield-Jackson Atlanta"},
                "scheduledTime": {"utc": "2026-11-05 18:30Z"},
            },
            "aircraft": {
                "reg": "N596NW",
                "typeCode": "B752",
                "modeS": "a7b123",
            },
        }
    )
    mock_adb.get_inbound_rotations = AsyncMock(
        return_value=[
            FlightLeg(
                flight_number="DL656",
                origin_iata="ATL",
                destination_iata="SFO",
                scheduled_departure=datetime.now(timezone.utc) - timedelta(hours=4),
                scheduled_arrival=datetime.now(timezone.utc) - timedelta(hours=1),
                actual_departure=datetime.now(timezone.utc) - timedelta(hours=4),
                actual_arrival=datetime.now(timezone.utc) - timedelta(hours=1),
                status="LANDED",
            )
        ]
    )

    # Mock OpenSky: DAL783 is airborne at 33,100 ft; inbound tail N596NW is at 40,000 ft
    mock_opensky = MagicMock()
    mock_opensky.mock_mode = False

    async def mock_get_aircraft_state(target: str):
        if target.lower() in ("dal783", "dl783"):
            return {
                "callsign": "DAL783",
                "baro_altitude_ft": 33100.0,
                "ground_speed_kts": 430.0,
                "on_ground": False,
                "latitude": 34.5,
                "longitude": -111.8,
                "last_contact_epoch": 1792842000,
            }
        elif target.lower() in ("a7b123", "n596nw"):
            return {
                "callsign": "DAL656",
                "baro_altitude_ft": 40000.0,
                "ground_speed_kts": 413.7,
                "on_ground": False,
                "latitude": 39.5,
                "longitude": -116.5,
                "last_contact_epoch": 1792842000,
            }
        return None

    mock_opensky.get_aircraft_state = AsyncMock(side_effect=mock_get_aircraft_state)

    aggregator = FlightAggregator(
        aerodatabox_client=mock_adb,
        opensky_client=mock_opensky,
    )

    query = FlightQuery(
        carrier="DL",
        flight_number="783",
        departure_date=date(2026, 11, 5),
        origin="LAX",
        destination="ATL",
    )

    current_leg, turnaround, telemetry = await aggregator.get_flight_context(query)

    assert current_leg is not None
    assert current_leg.origin_iata == "LAX"
    assert current_leg.destination_iata == "ATL"
    assert current_leg.status == "AIRBORNE"

    # Main telemetry matches booked flight
    assert telemetry is not None
    assert telemetry["callsign"] == "DAL783"
    assert telemetry["baro_altitude_ft"] == 33100.0
    assert telemetry["telemetry_source"] == "BOOKED_FLIGHT"

    # Turnaround inbound telemetry matches inbound airframe
    assert turnaround is not None
    assert turnaround.live_telemetry is not None
    assert turnaround.live_telemetry["callsign"] == "DAL656"
    assert turnaround.live_telemetry["baro_altitude_ft"] == 40000.0
    assert turnaround.live_telemetry["telemetry_source"] == "INBOUND_ROTATION"

    # Reality Assessment verification
    engine = PredictionEngine()
    assessment = engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
        flight_query=query,
        live_telemetry=telemetry,
    )

    assert assessment.live_telemetry["baro_altitude_ft"] == 33100.0
    assert assessment.live_telemetry["telemetry_source"] == "BOOKED_FLIGHT"
    assert assessment.inbound_turnaround.live_telemetry["baro_altitude_ft"] == 40000.0
    assert assessment.inbound_turnaround.live_telemetry["telemetry_source"] == "INBOUND_ROTATION"


@pytest.mark.asyncio
async def test_inbound_telemetry_isolation_when_booked_flight_not_airborne():
    """GT-BOOK-01: When booked flight is not airborne, main telemetry is NOT overwritten by inbound airframe."""
    mock_adb = MagicMock()
    mock_adb.mock_mode = False
    mock_adb.get_flight_status = AsyncMock(
        return_value={
            "status": "Scheduled",
            "callsign": "DAL450",
            "number": "DL450",
            "departure": {
                "airport": {"iata": "ATL", "name": "Atlanta"},
                "scheduledTime": {"utc": "2026-11-05 14:00Z"},
            },
            "arrival": {
                "airport": {"iata": "MCO", "name": "Orlando"},
                "scheduledTime": {"utc": "2026-11-05 15:30Z"},
            },
            "aircraft": {
                "reg": "N450DL",
                "typeCode": "A321",
                "modeS": "a450dl",
            },
        }
    )
    mock_adb.get_inbound_rotations = AsyncMock(return_value=[])

    mock_opensky = MagicMock()
    mock_opensky.mock_mode = False

    async def mock_get_aircraft_state(target: str):
        if target.lower() == "dal450":
            # Booked flight is on ground / inactive
            return {
                "callsign": "DAL450",
                "baro_altitude_ft": None,
                "ground_speed_kts": None,
                "on_ground": True,
            }
        elif target.lower() in ("a450dl", "n450dl"):
            # Inbound plane is currently airborne cruising towards ATL
            return {
                "callsign": "DL881",
                "baro_altitude_ft": 29000.0,
                "ground_speed_kts": 420.0,
                "on_ground": False,
            }
        return None

    mock_opensky.get_aircraft_state = AsyncMock(side_effect=mock_get_aircraft_state)

    aggregator = FlightAggregator(
        aerodatabox_client=mock_adb,
        opensky_client=mock_opensky,
    )

    query = FlightQuery(
        carrier="DL",
        flight_number="450",
        departure_date=date(2026, 11, 5),
    )

    current_leg, turnaround, telemetry = await aggregator.get_flight_context(query)

    # Main telemetry must NOT contain the 29,000 ft altitude of the inbound aircraft
    assert telemetry is None
    # Turnaround MUST contain the inbound telemetry
    assert turnaround.live_telemetry is not None
    assert turnaround.live_telemetry["baro_altitude_ft"] == 29000.0
    assert turnaround.live_telemetry["telemetry_source"] == "INBOUND_ROTATION"


@pytest.mark.asyncio
async def test_multileg_city_pair_disambiguation():
    """GT-BOOK-01: Disambiguate multi-hop flight numbers by matching origin and destination filters."""
    client = AeroDataBoxClient(mock_mode=False)

    multileg_payload = [
        {
            "number": "DL783",
            "departure": {"airport": {"iata": "JFK"}},
            "arrival": {"airport": {"iata": "LAX"}},
        },
        {
            "number": "DL783",
            "departure": {"airport": {"iata": "LAX"}},
            "arrival": {"airport": {"iata": "ATL"}},
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json = MagicMock(return_value=multileg_payload)
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_resp)):
        # 1. Query with LAX -> ATL: should pick the second leg
        res_lax_atl = await client.get_flight_status(
            carrier="DL",
            flight_num="783",
            date="2026-11-05",
            origin="LAX",
            destination="ATL",
        )
        assert res_lax_atl["departure"]["airport"]["iata"] == "LAX"
        assert res_lax_atl["arrival"]["airport"]["iata"] == "ATL"

        # 2. Query with JFK -> LAX: should pick the first leg
        res_jfk_lax = await client.get_flight_status(
            carrier="DL",
            flight_num="783",
            date="2026-11-05",
            origin="JFK",
            destination="LAX",
        )
        assert res_jfk_lax["departure"]["airport"]["iata"] == "JFK"
        assert res_jfk_lax["arrival"]["airport"]["iata"] == "LAX"

        # 3. Query without filter: defaults to first leg
        res_default = await client.get_flight_status(
            carrier="DL",
            flight_num="783",
            date="2026-11-05",
        )
        assert res_default["departure"]["airport"]["iata"] == "JFK"
