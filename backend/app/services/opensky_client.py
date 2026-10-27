import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class OpenSkyClient:
    """Client for querying live flight state vectors from OpenSky Network."""

    def __init__(
        self,
        timeout: Optional[float] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.timeout = timeout if timeout is not None else settings.OPENSKY_TIMEOUT
        self.mock_mode = (
            mock_mode if mock_mode is not None else settings.MOCK_INGESTION
        )
        self.base_url = "https://opensky-network.org/api/states/all"
        logger.info("OpenSkyClient initialized (mock_mode=%s)", self.mock_mode)

    async def get_aircraft_state(
        self, icao24_or_callsign: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch live state vector:

        callsign, baro_altitude_ft, ground_speed_kts, on_ground, latitude, longitude, last_contact_epoch
        """
        if self.mock_mode:
            logger.info(
                "OpenSkyClient: [MOCK REPLAY] Loading local telemetry fixture for %s",
                icao24_or_callsign,
            )
            fixture_path = FIXTURES_DIR / "sample_opensky_state.json"
            if not fixture_path.exists():
                raise FileNotFoundError(f"Fixture not found at {fixture_path}")
            with open(fixture_path, "r", encoding="utf-8") as f:
                return json.load(f)

        target = icao24_or_callsign.strip().lower()
        params = {}
        if len(target) == 6 and all(c in "0123456789abcdef" for c in target):
            params["icao24"] = target

        logger.info(
            "OpenSkyClient: [LIVE INGESTION] Dispatching outbound request to %s for target %s",
            self.base_url,
            target,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(self.base_url, params=params)
                logger.info(
                    "OpenSkyClient: [LIVE INGESTION] Response received with status %s",
                    response.status_code,
                )
                if response.status_code != 200:
                    logger.warning("OpenSky API returned HTTP %s", response.status_code)
                    return None

                data = response.json()
                states = data.get("states", [])
                if not states:
                    return None

                # Find matching state
                for st in states:
                    # OpenSky state vector fields:
                    # 0: icao24, 1: callsign, 2: origin_country, 3: time_position,
                    # 4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude (meters),
                    # 8: on_ground, 9: velocity (m/s)
                    st_icao = (st[0] or "").strip().lower()
                    st_callsign = (st[1] or "").strip().lower()
                    if st_icao == target or st_callsign == target:
                        baro_alt_m = st[7]
                        baro_alt_ft = (
                            round(baro_alt_m * 3.28084, 1) if baro_alt_m is not None else None
                        )
                        velocity_mps = st[9]
                        ground_speed_kts = (
                            round(velocity_mps * 1.94384, 1)
                            if velocity_mps is not None
                            else None
                        )
                        return {
                            "callsign": (st[1] or "").strip(),
                            "baro_altitude_ft": baro_alt_ft,
                            "ground_speed_kts": ground_speed_kts,
                            "on_ground": bool(st[8]),
                            "latitude": st[6],
                            "longitude": st[5],
                            "last_contact_epoch": st[4],
                        }
                return None
            except Exception as exc:
                logger.error("OpenSky fetch failed: %s", exc)
                return None
