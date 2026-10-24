from datetime import datetime, timedelta
from typing import NamedTuple
from app.schemas.flight import AircraftInfo


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
        earliest_possible_departure = inbound_touchdown + timedelta(
            minutes=mtt_minutes
        )

        delay_delta_seconds = (
            earliest_possible_departure - scheduled_departure
        ).total_seconds()
        delay_lead_time_minutes = int(delay_delta_seconds // 60)

        is_unavoidable_delay = earliest_possible_departure > scheduled_departure

        return TurnaroundResult(
            mtt_minutes=mtt_minutes,
            calculated_earliest_departure=earliest_possible_departure,
            is_unavoidable_delay=is_unavoidable_delay,
            delay_lead_time_minutes=max(0, delay_lead_time_minutes),
        )
