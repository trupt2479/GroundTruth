from datetime import datetime, timedelta
import logging
from typing import List, Optional

from app.schemas.flight import CrewDutyAssessment, FlightLeg

logger = logging.getLogger(__name__)

# Standard domestic maximum Flight Duty Period (FDP) buffer: 14 hours (840 minutes)
FAA_PART_117_MAX_FDP_MINUTES = 840
REPORT_TIME_BUFFER_MINUTES = 60  # Typical show-up/report time 1 hour before first departure


class CrewDutyWatchdog:
    """Evaluates flight crew legal duty hours and timeout risks under FAA Part 117 rules."""

    def __init__(self, max_fdp_minutes: int = FAA_PART_117_MAX_FDP_MINUTES):
        self.max_fdp_minutes = max_fdp_minutes

    def assess_crew_duty(
        self,
        current_leg: FlightLeg,
        previous_legs: List[FlightLeg],
        calculated_earliest_departure: datetime,
    ) -> CrewDutyAssessment:
        """Calculates elapsed duty time across preceding rotation legs and current leg.

        - Initial crew report time: 60 mins before the earliest preceding rotation leg (or current leg if none).
        - Estimated end of duty: calculated departure of current leg + flight duration.
        - Computes remaining buffer minutes and evaluates timeout risk:
          * HIGH: Remaining duty buffer < 60 minutes.
          * MODERATE: Remaining duty buffer between 60 and 120 minutes.
          * LOW: Remaining duty buffer > 120 minutes.
        """
        # 1. Determine initial report time
        if previous_legs:
            first_leg = previous_legs[0]
            first_departure = first_leg.scheduled_departure
            initial_report_time = first_departure - timedelta(minutes=REPORT_TIME_BUFFER_MINUTES)
        else:
            initial_report_time = current_leg.scheduled_departure - timedelta(
                minutes=REPORT_TIME_BUFFER_MINUTES
            )

        # 2. Determine current leg flight duration
        flight_duration = (
            current_leg.scheduled_arrival - current_leg.scheduled_departure
        )
        if flight_duration.total_seconds() <= 0:
            flight_duration = timedelta(hours=2)  # Default fallback 2h

        # 3. Estimated completion of duty period
        projected_duty_end = calculated_earliest_departure + flight_duration
        total_duty_seconds = (projected_duty_end - initial_report_time).total_seconds()
        elapsed_duty_minutes = max(0, int(total_duty_seconds // 60))

        remaining_buffer_minutes = self.max_fdp_minutes - elapsed_duty_minutes

        # 4. Determine timeout risk level
        if remaining_buffer_minutes < 60:
            timeout_risk = "HIGH"
            risk_summary = (
                f"CRITICAL: Flight crew is within {remaining_buffer_minutes}m of FAA Part 117 "
                f"14-hour duty limit. Severe flight cancellation / crew timeout risk."
            )
        elif remaining_buffer_minutes <= 120:
            timeout_risk = "MODERATE"
            risk_summary = (
                f"WARNING: Flight crew has {remaining_buffer_minutes}m of duty buffer remaining. "
                f"Further delays will trigger crew legality timeout."
            )
        else:
            timeout_risk = "LOW"
            risk_summary = (
                f"NORMAL: Flight crew has {remaining_buffer_minutes}m of duty buffer remaining. "
                f"Well within FAA Part 117 limits."
            )

        return CrewDutyAssessment(
            elapsed_duty_minutes=elapsed_duty_minutes,
            remaining_buffer_minutes=remaining_buffer_minutes,
            timeout_risk=timeout_risk,
            risk_summary=risk_summary,
        )
