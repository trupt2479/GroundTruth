from datetime import datetime, timedelta, timezone
from typing import NamedTuple
from app.schemas.flight import AircraftInfo


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime carries timezone.utc for safe epoch math."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TurnaroundResult(NamedTuple):
    mtt_minutes: int
    calculated_earliest_departure: datetime
    is_unavoidable_delay: bool
    delay_lead_time_minutes: int


# Fleet turn buffer matrix lookup
FLEET_MTT_BUFFER_MINUTES = {
    "REGIONAL": 35,
    "NARROWBODY": 45,
    "WIDEBODY": 75,
}


class TurnaroundEngine:
    """Calculates physical turnaround limits and detects unavoidable delays."""

    @staticmethod
    def get_mtt_minutes(aircraft_category: str) -> int:
        """Look up MTT buffer minutes for aircraft category."""
        return FLEET_MTT_BUFFER_MINUTES.get(aircraft_category.upper(), 45)

    def calculate_turnaround(
        self,
        inbound_touchdown: datetime,
        scheduled_departure: datetime,
        aircraft: AircraftInfo,
    ) -> TurnaroundResult:
        """Dynamic calculation:

        Earliest Possible Departure = Inbound Actual Touchdown + MTT Buffer.
        If Earliest Possible Departure > Scheduled Departure:
          Unavoidable Delay = True
          Delay Lead Time Delta = (Earliest Possible Departure - Scheduled Departure)
        """
        mtt_minutes = self.get_mtt_minutes(aircraft.category)
        inbound_utc = _ensure_utc(inbound_touchdown)
        sched_dep_utc = _ensure_utc(scheduled_departure)
        earliest_possible_departure = inbound_utc + timedelta(
            minutes=mtt_minutes
        )

        delay_delta_seconds = (
            earliest_possible_departure - sched_dep_utc
        ).total_seconds()
        delay_lead_time_minutes = int(delay_delta_seconds // 60)

        is_unavoidable_delay = earliest_possible_departure > sched_dep_utc

        return TurnaroundResult(
            mtt_minutes=mtt_minutes,
            calculated_earliest_departure=earliest_possible_departure,
            is_unavoidable_delay=is_unavoidable_delay,
            delay_lead_time_minutes=max(0, delay_lead_time_minutes),
        )
