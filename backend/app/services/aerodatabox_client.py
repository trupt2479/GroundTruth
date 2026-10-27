import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.flight import FlightLeg

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class AeroDataBoxError(Exception):
    """Base exception for AeroDataBox client errors."""


class AeroDataBoxRateLimitError(AeroDataBoxError):
    """Raised when AeroDataBox responds with HTTP 429 Too Many Requests."""


class AeroDataBoxServiceUnavailableError(AeroDataBoxError):
    """Raised when AeroDataBox responds with HTTP 503 Service Unavailable."""


def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    cleaned = dt_str.strip().replace(" ", "T").rstrip("Z")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class AeroDataBoxClient:
    """Client for querying flight status and aircraft rotations via AeroDataBox API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        timeout: Optional[float] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.api_key = api_key or settings.AERODATABOX_API_KEY
        self.api_host = api_host or settings.AERODATABOX_API_HOST
        self.timeout = timeout if timeout is not None else settings.AERODATABOX_TIMEOUT
        self.mock_mode = (
            mock_mode if mock_mode is not None else settings.MOCK_INGESTION
        )
        self.base_url = f"https://{self.api_host}"
        logger.info(
            "AeroDataBoxClient initialized (mock_mode=%s, host=%s)",
            self.mock_mode,
            self.api_host,
        )

    def _load_fixture(
        self, filename: str, target_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load local mock fixture and adapt dates to the requested target_date."""
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found at {fixture_path}")
        with open(fixture_path, "r", encoding="utf-8") as f:
            content = f.read()

        if target_date:
            # Dynamically replace sample date 2026-10-24 with target_date
            content = content.replace("2026-10-24", target_date)

        data = json.loads(content)
        if isinstance(data, list):
            return data[0] if data else {}
        return data

    def _load_rotations_fixture(
        self, filename: str, target_date: Optional[str] = None
    ) -> List[FlightLeg]:
        """Load local rotation fixtures and adapt timestamps to target_date."""
        fixture_path = FIXTURES_DIR / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found at {fixture_path}")
        with open(fixture_path, "r", encoding="utf-8") as f:
            content = f.read()

        if target_date:
            content = content.replace("2026-10-24", target_date)

        items = json.loads(content)
        legs = [FlightLeg.model_validate(item) for item in items]
        return legs[-2:]

    async def get_flight_status(
        self, carrier: str, flight_num: str, date: str
    ) -> Dict[str, Any]:
        """Fetch raw flight status payload.

        Endpoint: GET /flights/number/{carrier}{flight_num}/{date}
        """
        if self.mock_mode:
            logger.info(
                "AeroDataBoxClient: [MOCK REPLAY] Loading local fixture for %s%s on %s",
                carrier,
                flight_num,
                date,
            )
            return self._load_fixture("sample_aerodatabox_flight.json", date)

        url = f"{self.base_url}/flights/number/{carrier}{flight_num}/{date}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }
        logger.info("AeroDataBoxClient: [LIVE INGESTION] Dispatching outbound request to %s", url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                logger.info("AeroDataBoxClient: [LIVE INGESTION] Response received with status %s", response.status_code)
                if response.status_code == 429:
                    raise AeroDataBoxRateLimitError(
                        "Rate limit exceeded (HTTP 429) for AeroDataBox API."
                    )
                if response.status_code == 503:
                    raise AeroDataBoxServiceUnavailableError(
                        "AeroDataBox service temporarily unavailable (HTTP 503)."
                    )
                response.raise_for_status()
                data = response.json()
                if isinstance(data, list):
                    return data[0] if data else {}
                return data
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise AeroDataBoxRateLimitError(str(exc)) from exc
                if exc.response.status_code == 503:
                    raise AeroDataBoxServiceUnavailableError(str(exc)) from exc
                raise AeroDataBoxError(f"HTTP error: {exc}") from exc
            except httpx.RequestError as exc:
                raise AeroDataBoxError(f"Network error: {exc}") from exc

    async def get_inbound_rotations(
        self, tail_number: str, date: str
    ) -> List[FlightLeg]:
        """Fetch up to 2 preceding legs for the assigned aircraft tail."""
        if self.mock_mode:
            logger.info(
                "AeroDataBoxClient: [MOCK REPLAY] Loading local rotation fixture for tail %s on %s",
                tail_number,
                date,
            )
            return self._load_rotations_fixture("sample_aerodatabox_rotations.json", date)

        url = f"{self.base_url}/flights/reg/{tail_number}/{date}"
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }
        logger.info("AeroDataBoxClient: [LIVE INGESTION] Dispatching outbound rotation request to %s", url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                logger.info("AeroDataBoxClient: [LIVE INGESTION] Rotation response received with status %s", response.status_code)
                if response.status_code == 429:
                    raise AeroDataBoxRateLimitError("Rate limit exceeded (HTTP 429)")
                if response.status_code == 503:
                    raise AeroDataBoxServiceUnavailableError("Service unavailable (HTTP 503)")
                response.raise_for_status()
                raw_legs = response.json()
                if not isinstance(raw_legs, list):
                    return []

                parsed_legs: List[FlightLeg] = []
                for leg_data in raw_legs:
                    flight_no = leg_data.get("number") or leg_data.get("flight_number") or "UNKNOWN"
                    dep = leg_data.get("departure", {})
                    arr = leg_data.get("arrival", {})
                    origin = (
                        dep.get("airport", {}).get("iata")
                        or dep.get("origin_iata")
                        or "ZZZ"
                    )
                    dest = (
                        arr.get("airport", {}).get("iata")
                        or arr.get("destination_iata")
                        or "ZZZ"
                    )
                    sched_dep = parse_iso_datetime(
                        dep.get("scheduledTime", {}).get("utc")
                        or leg_data.get("scheduled_departure")
                    )
                    sched_arr = parse_iso_datetime(
                        arr.get("scheduledTime", {}).get("utc")
                        or leg_data.get("scheduled_arrival")
                    )
                    act_dep = parse_iso_datetime(
                        dep.get("actualTime", {}).get("utc")
                        or dep.get("revisedTime", {}).get("utc")
                        or leg_data.get("actual_departure")
                    )
                    act_arr = parse_iso_datetime(
                        arr.get("actualTime", {}).get("utc")
                        or arr.get("revisedTime", {}).get("utc")
                        or leg_data.get("actual_arrival")
                    )
                    status = leg_data.get("status", "SCHEDULED").upper()

                    if sched_dep and sched_arr:
                        parsed_legs.append(
                            FlightLeg(
                                flight_number=flight_no,
                                origin_iata=origin,
                                destination_iata=dest,
                                scheduled_departure=sched_dep,
                                scheduled_arrival=sched_arr,
                                actual_departure=act_dep,
                                actual_arrival=act_arr,
                                status=status,
                            )
                        )
                return parsed_legs[-2:]
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise AeroDataBoxRateLimitError(str(exc)) from exc
                if exc.response.status_code == 503:
                    raise AeroDataBoxServiceUnavailableError(str(exc)) from exc
                raise AeroDataBoxError(f"HTTP error: {exc}") from exc
            except httpx.RequestError as exc:
                raise AeroDataBoxError(f"Network error: {exc}") from exc
