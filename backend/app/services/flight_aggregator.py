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

        # 4. Live telemetry via OpenSky
        callsign = flight_raw.get("callsign") or f"{query.carrier}{query.flight_number}"
        telemetry_target = mode_s or (callsign if not self.aerodatabox.mock_mode else None)
        if telemetry_target:
            live_telemetry = await self.opensky.get_aircraft_state(telemetry_target)
        else:
            live_telemetry = None

        # Write live telemetry to Redis with 60s TTL
        if live_telemetry:
            tail_key = f"tail:{tail_number}:state"
            await self.cache.set_json(tail_key, live_telemetry, ttl_seconds=LIVE_STATE_TTL)

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
