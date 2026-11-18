"""Airport IATA -> IANA timezone mapping and airport-local timestamp helpers."""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ET, CT, MT, PT = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"

AIRPORT_TIMEZONES = {
    # Eastern
    "ATL": ET, "JFK": ET, "LGA": ET, "EWR": ET, "BOS": ET, "PHL": ET, "DCA": ET, "IAD": ET,
    "BWI": ET, "CLT": ET, "MIA": ET, "FLL": ET, "MCO": ET, "TPA": ET, "DTW": ET, "BDL": ET,
    "RDU": ET, "PIT": ET, "CLE": ET, "CVG": ET, "JAX": ET, "RSW": ET, "PBI": ET, "BUF": ET,
    # Central
    "ORD": CT, "MDW": CT, "DFW": CT, "DAL": CT, "IAH": CT, "HOU": CT, "AUS": CT, "SAT": CT,
    "MSP": CT, "STL": CT, "MCI": CT, "MSY": CT, "BNA": CT, "MEM": CT, "MKE": CT, "OMA": CT,
    # Mountain
    "DEN": MT, "SLC": MT, "ABQ": MT, "BOI": MT, "PHX": "America/Phoenix",
    # Pacific
    "LAX": PT, "SFO": PT, "SJC": PT, "OAK": PT, "SAN": PT, "SEA": PT, "PDX": PT, "LAS": PT,
    "SMF": PT, "SNA": PT, "BUR": PT,
    # Other
    "ANC": "America/Anchorage", "HNL": "Pacific/Honolulu", "OGG": "Pacific/Honolulu",
    "LHR": "Europe/London", "CDG": "Europe/Paris", "FRA": "Europe/Berlin",
    "AMS": "Europe/Amsterdam", "NRT": "Asia/Tokyo", "HND": "Asia/Tokyo",
    "YYZ": "America/Toronto", "YVR": "America/Vancouver", "MEX": "America/Mexico_City",
}


def get_airport_timezone(iata: Optional[str]) -> Optional[str]:
    """Return the IANA timezone for an airport, or None if unknown (never guessed)."""
    if not iata:
        return None
    return AIRPORT_TIMEZONES.get(iata.strip().upper())


def to_local_iso(dt: Optional[datetime], tz_name: Optional[str]) -> Optional[str]:
    """Convert a datetime to an ISO-8601 string with UTC offset in the given IANA zone.

    Naive datetimes are treated as UTC. Returns None when dt or tz is missing/invalid.
    """
    if dt is None or not tz_name:
        return None
    try:
        zone = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(zone).isoformat(timespec="seconds")
