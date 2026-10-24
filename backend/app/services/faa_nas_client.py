import logging
from pathlib import Path
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class FaaNasClient:
    """Async client querying FAA National Airspace System (NAS) status and ground delay programs."""

    def __init__(
        self,
        base_url: str = "https://nasstatus.faa.gov/api/airport-status-information",
        timeout: float = 5.0,
        mock_mode: Optional[bool] = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.mock_mode = (
            mock_mode if mock_mode is not None else settings.MOCK_INGESTION
        )

    def _parse_xml_status(self, xml_text: str, airport_iata: str) -> Optional[Dict[str, Any]]:
        """Parse FAA NAS XML payload and extract status for the requested airport."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("Failed to parse FAA NAS XML: %s", exc)
            return None

        target = airport_iata.strip().upper()

        # Check Ground_Stop entries
        for gs in root.findall(".//Ground_Stop"):
            arpt = gs.findtext("ARPT")
            if arpt and arpt.strip().upper() == target:
                reason = gs.findtext("Reason") or "UNKNOWN"
                avg_delay_str = gs.findtext("Avg_Delay") or "0"
                end_time = gs.findtext("End_Time")
                try:
                    avg_delay = int(avg_delay_str)
                except ValueError:
                    avg_delay = 0

                return {
                    "airport_iata": target,
                    "status_type": "GROUND_STOP",
                    "reason": reason.strip(),
                    "avg_delay_minutes": avg_delay,
                    "end_time_utc": end_time.strip() if end_time else None,
                    "advisory_active": True,
                }

        # Check Ground_Delay entries
        for gd in root.findall(".//Ground_Delay"):
            arpt = gd.findtext("ARPT")
            if arpt and arpt.strip().upper() == target:
                reason = gd.findtext("Reason") or "UNKNOWN"
                avg_delay_str = gd.findtext("Avg_Delay") or "0"
                end_time = gd.findtext("End_Time")
                try:
                    avg_delay = int(avg_delay_str)
                except ValueError:
                    avg_delay = 0

                return {
                    "airport_iata": target,
                    "status_type": "GROUND_DELAY_PROGRAM",
                    "reason": reason.strip(),
                    "avg_delay_minutes": avg_delay,
                    "end_time_utc": end_time.strip() if end_time else None,
                    "advisory_active": True,
                }

        # Check Deicing entries
        for deice in root.findall(".//Deicing"):
            arpt = deice.findtext("ARPT")
            if arpt and arpt.strip().upper() == target:
                reason = deice.findtext("Reason") or "DEICING OPERATIONS"
                avg_delay_str = deice.findtext("Avg_Delay") or "0"
                end_time = deice.findtext("End_Time")
                try:
                    avg_delay = int(avg_delay_str)
                except ValueError:
                    avg_delay = 0

                return {
                    "airport_iata": target,
                    "status_type": "DEICING",
                    "reason": reason.strip(),
                    "avg_delay_minutes": avg_delay,
                    "end_time_utc": end_time.strip() if end_time else None,
                    "advisory_active": True,
                }

        # Default to NORMAL if airport has no active advisory in the system
        return {
            "airport_iata": target,
            "status_type": "NORMAL",
            "reason": None,
            "avg_delay_minutes": 0,
            "end_time_utc": None,
            "advisory_active": False,
        }

    async def get_airport_airspace_status(
        self, airport_iata: str
    ) -> Optional[Dict[str, Any]]:
        """Queries or extracts status for specific airport (e.g. ORD, EWR, ATL).

        Extracts:
        - status_type: 'GROUND_STOP' | 'GROUND_DELAY_PROGRAM' | 'DEICING' | 'NORMAL'
        - reason: e.g. 'THUNDERSTORMS', 'LOW CEILINGS'
        - avg_delay_minutes: int
        - end_time_utc: datetime or str
        - advisory_active: bool
        """
        if self.mock_mode:
            logger.info("FaaNasClient: Returning mock FAA NAS status fixture")
            fixture_path = FIXTURES_DIR / "sample_faa_nas_status.xml"
            if not fixture_path.exists():
                raise FileNotFoundError(f"Fixture not found at {fixture_path}")
            with open(fixture_path, "r", encoding="utf-8") as f:
                xml_text = f.read()
            return self._parse_xml_status(xml_text, airport_iata)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(self.base_url)
                if response.status_code != 200:
                    logger.warning("FAA NAS API returned status %s", response.status_code)
                    return None
                return self._parse_xml_status(response.text, airport_iata)
            except Exception as exc:
                logger.error("FAA NAS API request failed: %s", exc)
                return None
