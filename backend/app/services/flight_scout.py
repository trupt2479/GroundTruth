from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import List, Optional
import httpx

from app.core.config import settings
from app.schemas.flight import AlternativeFlight

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class AlternativeFlightScout:
    """Service to discover and rank viable alternative flights when rebooking is required."""

    def __init__(
        self,
        mock_mode: Optional[bool] = None,
        timeout: float = 5.0,
    ):
        self.mock_mode = (
            mock_mode if mock_mode is not None else settings.MOCK_INGESTION
        )
        self.timeout = timeout

    async def find_alternative_flights(
        self,
        carrier: str,
        origin_iata: str,
        destination_iata: str,
        after_time: datetime,
    ) -> List[AlternativeFlight]:
        """Searches carrier schedule for the same city pair departing after `after_time`.

        Ranks and returns the next 2 viable alternative flights.
        """
        carrier_clean = carrier.strip().upper()
        origin_clean = origin_iata.strip().upper()
        dest_clean = destination_iata.strip().upper()

        if self.mock_mode:
            logger.info(
                "AlternativeFlightScout: Returning mock alternative flights for %s %s->%s",
                carrier_clean,
                origin_clean,
                dest_clean,
            )
            fixture_path = FIXTURES_DIR / "sample_alternate_flights.json"
            if not fixture_path.exists():
                raise FileNotFoundError(f"Fixture not found at {fixture_path}")

            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            candidates: List[AlternativeFlight] = []
            for item in raw_data:
                dep_dt = datetime.fromisoformat(item["departure_time"].replace("Z", "+00:00"))
                arr_dt = datetime.fromisoformat(item["arrival_time"].replace("Z", "+00:00"))

                # Match carrier and route
                if (
                    item.get("carrier", "").upper() == carrier_clean
                    and item.get("origin_iata", "").upper() == origin_clean
                    and item.get("destination_iata", "").upper() == dest_clean
                ):
                    # Ensure departing after or around after_time
                    if dep_dt >= after_time:
                        candidates.append(
                            AlternativeFlight(
                                flight_number=item["flight_number"],
                                carrier=item["carrier"],
                                departure_time=dep_dt,
                                arrival_time=arr_dt,
                                origin_iata=item["origin_iata"],
                                destination_iata=item["destination_iata"],
                                seats_available=item.get("seats_available", True),
                                standby_recommended=item.get("standby_recommended", False),
                            )
                        )

            # Sort chronologically by departure time and return next 2 viable alternatives
            candidates.sort(key=lambda x: x.departure_time)
            return candidates[:2]

        # In production mode with external schedules (stubbed for live flight query API)
        return []
