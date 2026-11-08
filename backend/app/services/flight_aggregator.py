from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional, Tuple

from app.schemas.flight import (
    AircraftInfo,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
)
from app.services.aerodatabox_client import (
    AeroDataBoxClient,
    parse_iso_datetime,
)
from app.services.cache_service import CacheService
from app.services.opensky_client import OpenSkyClient

logger = logging.getLogger(__name__)

# TTL Policies
FLIGHT_AGGREGATE_TTL = 120  # 120 seconds
LIVE_STATE_TTL = 60  # 60 seconds

# Aircraft category mapping to MTT
MTT_MAP = {
    "REGIONAL": 35,
    "NARROWBODY": 45,
    "WIDEBODY": 75,
}

CARRIER_ICAO_MAP = {
    "DL": "DAL",
    "UA": "UAL",
    "AA": "AAL",
    "WN": "SWA",
    "B6": "JBU",
    "AS": "ASA",
    "NK": "NKS",
    "F9": "FFT",
}


def categorize_aircraft(type_code: str) -> str:
    """Classify aircraft ICAO type code into REGIONAL, NARROWBODY, or WIDEBODY."""
    widebodies = {
        "A332", "A333", "A338", "A339", "A340", "A359", "A35K", "A388",
        "B762", "B763", "B764", "B772", "B773", "B778", "B779", "B77W", "B788", "B789", "B78X",
        "MD11", "DC10", "B744", "B748"
    }
    regionals = {
        "E170", "E175", "E190", "E195", "CRJ2", "CRJ7", "CRJ9", "CRJX", "AT76", "DH8D"
    }
    cleaned = (type_code or "").strip().upper()
    if cleaned in widebodies:
        return "WIDEBODY"
    if cleaned in regionals:
        return "REGIONAL"
    # Default to narrowbody (e.g. A320, B738, A220, etc.)
    return "NARROWBODY"


def _safe_get_utc(container: Optional[Dict[str, Any]], field: str) -> Optional[str]:
    """Helper to safely extract a UTC time string from nested dictionaries."""
    if not isinstance(container, dict):
        return None
    val = container.get(field)
    if isinstance(val, dict):
        return val.get("utc")
    if isinstance(val, str):
        return val
    return None


class FlightAggregator:
    """Orchestrates flight data ingestion across AeroDataBox and OpenSky with Redis cache-aside."""

    def __init__(
        self,
        aerodatabox_client: Optional[AeroDataBoxClient] = None,
        opensky_client: Optional[OpenSkyClient] = None,
        cache_service: Optional[CacheService] = None,
    ):
        self.aerodatabox = aerodatabox_client or AeroDataBoxClient()
        self.opensky = opensky_client or OpenSkyClient()
        self.cache = cache_service or CacheService()

    async def get_flight_context(
        self, query: FlightQuery
    ) -> Tuple[Optional[FlightLeg], Optional[InboundTurnaround], Optional[Dict[str, Any]]]:
        """Aggregate current flight leg, inbound turnaround, and live transponder telemetry.

        Uses cache-aside pattern with Redis (TTL = 120s for aggregate).
        """
        cache_key = f"flight:{query.carrier}_{query.flight_number}_{query.departure_date}"
        if query.origin:
            cache_key += f"_{query.origin.upper()}"
        if query.destination:
            cache_key += f"_{query.destination.upper()}"

        # 1. Check Redis cache
        cached_data = await self.cache.get_json(cache_key)
        if cached_data:
            logger.info("FlightAggregator: Cache HIT for %s", cache_key)
            flight_leg = FlightLeg.model_validate(cached_data["current_leg"])
            turnaround = InboundTurnaround.model_validate(cached_data["turnaround"])
            live_telemetry = cached_data.get("live_telemetry")
            return flight_leg, turnaround, live_telemetry

        logger.info("FlightAggregator: Cache MISS for %s", cache_key)

        # 2. Query AeroDataBox for targeted flight status
        flight_raw = await self.aerodatabox.get_flight_status(
            carrier=query.carrier,
            flight_num=query.flight_number,
            date=str(query.departure_date),
            origin=query.origin,
            destination=query.destination,
        )

        if not flight_raw and not self.aerodatabox.mock_mode:
            logger.warning("Flight %s%s on %s returned empty data in live mode", query.carrier, query.flight_number, query.departure_date)
            return None, None, None

        dep_info = flight_raw.get("departure") or {}
        arr_info = flight_raw.get("arrival") or {}
        movement = flight_raw.get("movement") or {}

        dep_airport = dep_info.get("airport") or {}
        arr_airport = arr_info.get("airport") or {}
        movement_airport = movement.get("airport") or {}

        origin_iata = (
            dep_airport.get("iata")
            or movement_airport.get("iata")
            or ("ORD" if self.aerodatabox.mock_mode else None)
        )
        origin_name = (
            dep_airport.get("name")
            or movement_airport.get("name")
        )
        destination_iata = (
            arr_airport.get("iata")
            or ("EWR" if self.aerodatabox.mock_mode else None)
        )
        destination_name = arr_airport.get("name")

        if not origin_iata or not destination_iata:
            if not self.aerodatabox.mock_mode:
                logger.warning("Missing origin or destination IATA for %s%s", query.carrier, query.flight_number)
                return None, None, None
            origin_iata = origin_iata or "ORD"
            destination_iata = destination_iata or "EWR"

        sched_dep_str = (
            _safe_get_utc(dep_info, "scheduledTime")
            or dep_info.get("scheduledTimeUtc")
            or dep_info.get("scheduledTimeLocal")
            or _safe_get_utc(movement, "scheduledTime")
            or (f"{query.departure_date}T12:00:00Z" if self.aerodatabox.mock_mode else None)
        )
        sched_arr_str = (
            _safe_get_utc(arr_info, "scheduledTime")
            or arr_info.get("scheduledTimeUtc")
            or arr_info.get("scheduledTimeLocal")
            or (f"{query.departure_date}T14:30:00Z" if self.aerodatabox.mock_mode else None)
        )
        act_dep_str = (
            _safe_get_utc(dep_info, "actualTime")
            or dep_info.get("actualTimeUtc")
            or dep_info.get("actualTimeLocal")
            or _safe_get_utc(dep_info, "revisedTime")
            or _safe_get_utc(movement, "revisedTime")
        )
        act_arr_str = (
            _safe_get_utc(arr_info, "actualTime")
            or arr_info.get("actualTimeUtc")
            or arr_info.get("actualTimeLocal")
            or _safe_get_utc(arr_info, "revisedTime")
        )

        sched_dep = parse_iso_datetime(sched_dep_str) or datetime.now(timezone.utc)
        sched_arr = parse_iso_datetime(sched_arr_str) or (datetime.now(timezone.utc) + timedelta(hours=2))
        act_dep = parse_iso_datetime(act_dep_str)
        act_arr = parse_iso_datetime(act_arr_str)
        status = str(flight_raw.get("status", "SCHEDULED")).upper()

        current_leg = FlightLeg(
            flight_number=f"{query.carrier}{query.flight_number}",
            origin_iata=origin_iata,
            destination_iata=destination_iata,
            origin_name=origin_name,
            destination_name=destination_name,
            scheduled_departure=sched_dep,
            scheduled_arrival=sched_arr,
            actual_departure=act_dep,
            actual_arrival=act_arr,
            status=status,
        )

        # 3. Aircraft info & Inbound Rotations
        aircraft_raw = flight_raw.get("aircraft") or {}
        tail_number = aircraft_raw.get("reg")
        if not tail_number:
            tail_number = "N123UA" if self.aerodatabox.mock_mode else "UNAVAILABLE"

        icao_type = aircraft_raw.get("typeCode")
        if not icao_type:
            icao_type = "B738" if self.aerodatabox.mock_mode else "UNKNOWN"

        mode_s = aircraft_raw.get("modeS") or aircraft_raw.get("icao24")
        if not mode_s and self.aerodatabox.mock_mode:
            mode_s = "a06041"

        category = categorize_aircraft(icao_type)
        mtt_minutes = MTT_MAP[category]

        aircraft_info = AircraftInfo(
            icao_type=icao_type,
            tail_number=tail_number,
            category=category,
        )

        if tail_number.upper() in ("PENDING", "UNAVAILABLE", "UNKNOWN"):
            previous_legs = []
        else:
            previous_legs = await self.aerodatabox.get_inbound_rotations(
                tail_number=tail_number,
                date=str(query.departure_date),
            )

        # 4. Live telemetry via OpenSky (Prioritize user's booked flight callsign)
        raw_callsign = flight_raw.get("callsign")
        carrier_upper = query.carrier.upper()
        icao_prefix = CARRIER_ICAO_MAP.get(carrier_upper, carrier_upper)
        active_callsign = raw_callsign or f"{icao_prefix}{query.flight_number}"

        booked_telemetry: Optional[Dict[str, Any]] = None
        inbound_telemetry: Optional[Dict[str, Any]] = None

        if self.opensky.mock_mode:
            # Mock mode: Handle DL 783 live cruise vs prior leg demonstration
            if query.carrier == "DL" and query.flight_number == "783":
                booked_telemetry = {
                    "callsign": "DAL783",
                    "baro_altitude_ft": 33100.0,
                    "ground_speed_kts": 430.0,
                    "on_ground": False,
                    "latitude": 34.5,
                    "longitude": -111.8,
                    "last_contact_epoch": 1792842000,
                    "telemetry_source": "BOOKED_FLIGHT",
                    "telemetry_phase": "ACTIVE_FLIGHT",
                    "flight_status": "AIRBORNE",
                }
                current_leg.status = "AIRBORNE"

                inbound_telemetry = {
                    "callsign": "DAL656",
                    "tail_number": tail_number or "N596NW",
                    "baro_altitude_ft": 40000.0,
                    "ground_speed_kts": 413.7,
                    "on_ground": False,
                    "latitude": 39.5,
                    "longitude": -116.5,
                    "last_contact_epoch": 1792842000,
                    "telemetry_source": "INBOUND_ROTATION",
                    "telemetry_phase": "INBOUND_ROTATION",
                }
            elif query.carrier == "UA" and query.flight_number == "1422":
                mock_state = await self.opensky.get_aircraft_state(active_callsign)
                if mock_state:
                    mock_state["telemetry_source"] = "BOOKED_FLIGHT"
                    mock_state["telemetry_phase"] = "ACTIVE_FLIGHT"
                    mock_state["flight_status"] = "AIRBORNE"
                    booked_telemetry = mock_state
                    current_leg.status = "AIRBORNE"
            else:
                # Other flights (e.g. DL 450, AA 1200) not yet airborne; isolate inbound airframe
                target_inbound = mode_s or tail_number or active_callsign
                mock_state = await self.opensky.get_aircraft_state(target_inbound)
                if mock_state:
                    mock_state["telemetry_source"] = "INBOUND_ROTATION"
                    mock_state["telemetry_phase"] = "INBOUND_ROTATION"
                    mock_state["inbound_callsign"] = mock_state.get("callsign")
                    inbound_telemetry = mock_state
        else:
            # Live Ingestion: Prioritize booked flight callsign in OpenSky
            active_state = await self.opensky.get_aircraft_state(active_callsign)
            if (
                active_state
                and not active_state.get("on_ground")
                and active_state.get("baro_altitude_ft") is not None
                and (active_state.get("baro_altitude_ft") or 0) > 0
            ):
                active_state["telemetry_source"] = "BOOKED_FLIGHT"
                active_state["telemetry_phase"] = "ACTIVE_FLIGHT"
                active_state["flight_status"] = "AIRBORNE"
                current_leg.status = "AIRBORNE"
                booked_telemetry = active_state

            # Query inbound airframe separately as background turnaround check
            target_inbound = mode_s or tail_number
            if target_inbound and target_inbound.upper() not in ("PENDING", "UNAVAILABLE", "UNKNOWN"):
                inbound_state = await self.opensky.get_aircraft_state(target_inbound)
                if inbound_state:
                    inbound_state["telemetry_source"] = "INBOUND_ROTATION"
                    inbound_state["telemetry_phase"] = "INBOUND_ROTATION"
                    inbound_state["inbound_callsign"] = inbound_state.get("callsign")
                    inbound_telemetry = inbound_state

        # Primary live telemetry represents the BOOKED flight only.
        # Inbound telemetry is strictly isolated to turnaround.live_telemetry.
        live_telemetry = booked_telemetry

        # Write live telemetry to Redis with 60s TTL
        if live_telemetry:
            tail_key = f"tail:{tail_number}:state"
            await self.cache.set_json(tail_key, live_telemetry, ttl_seconds=LIVE_STATE_TTL)
        elif inbound_telemetry:
            tail_key = f"tail:{tail_number}:state"
            await self.cache.set_json(tail_key, inbound_telemetry, ttl_seconds=LIVE_STATE_TTL)

        # 5. Calculate estimated touchdown and earliest possible departure
        if previous_legs:
            last_prior_leg = previous_legs[-1]
            estimated_touchdown = (
                last_prior_leg.actual_arrival
                or last_prior_leg.scheduled_arrival
            )
        else:
            estimated_touchdown = sched_dep - timedelta(minutes=mtt_minutes + 15)

        earliest_possible_departure = estimated_touchdown + timedelta(
            minutes=mtt_minutes
        )

        inbound_turnaround = InboundTurnaround(
            previous_legs=previous_legs[-2:],
            assigned_aircraft=aircraft_info,
            mtt_minutes=mtt_minutes,
            estimated_touchdown=estimated_touchdown,
            earliest_possible_departure=earliest_possible_departure,
            live_telemetry=inbound_telemetry,
        )

        # 6. Store aggregate in Redis with 120s TTL
        payload_to_cache = {
            "current_leg": current_leg.model_dump(mode="json"),
            "turnaround": inbound_turnaround.model_dump(mode="json"),
            "live_telemetry": live_telemetry,
        }
        await self.cache.set_json(
            cache_key, payload_to_cache, ttl_seconds=FLIGHT_AGGREGATE_TTL
        )

        return current_leg, inbound_turnaround, live_telemetry
