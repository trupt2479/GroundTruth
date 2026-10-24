from datetime import date
from typing import Optional

from app.schemas.flight import (
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
)
from app.services.action_engine import ActionEngine
from app.services.swap_evaluator import SwapEvaluator
from app.services.turnaround_engine import TurnaroundEngine


class PredictionEngine:
    """Orchestrates turnaround physics, hub swap evaluation, and prescriptive action directives."""

    def __init__(
        self,
        turnaround_engine: Optional[TurnaroundEngine] = None,
        swap_evaluator: Optional[SwapEvaluator] = None,
        action_engine: Optional[ActionEngine] = None,
    ):
        self.turnaround = turnaround_engine or TurnaroundEngine()
        self.swap_evaluator = swap_evaluator or SwapEvaluator()
        self.action = action_engine or ActionEngine()

    def assess_flight(
        self,
        current_leg: FlightLeg,
        turnaround: InboundTurnaround,
        flight_query: Optional[FlightQuery] = None,
        downstream_connection_layover_minutes: Optional[int] = None,
    ) -> RealityAssessment:
        """Contrasts official airline schedule against turnaround physics and spare capacity."""
        # 1. Parse or construct flight query if not explicitly passed
        if flight_query is None:
            carrier = current_leg.flight_number[:2].upper()
            flight_num = current_leg.flight_number[2:]
            dep_date = current_leg.scheduled_departure.date()
            flight_query = FlightQuery(
                carrier=carrier,
                flight_number=flight_num,
                departure_date=dep_date,
            )

        # 2. Calculate physical turnaround limits
        turnaround_result = self.turnaround.calculate_turnaround(
            inbound_touchdown=turnaround.estimated_touchdown,
            scheduled_departure=current_leg.scheduled_departure,
            aircraft=turnaround.assigned_aircraft,
        )

        # 3. Inbound delay magnitude
        inbound_delay_minutes = turnaround_result.delay_lead_time_minutes

        # 4. Evaluate tail swap likelihood
        swap_heuristic = self.swap_evaluator.evaluate_swap(
            origin_iata=current_leg.origin_iata,
            inbound_delay_minutes=inbound_delay_minutes,
        )

        # 5. Determine prescriptive rebooking directive
        rebooking_directive = self.action.determine_action(
            is_unavoidable_delay=turnaround_result.is_unavoidable_delay,
            delay_lead_time_minutes=turnaround_result.delay_lead_time_minutes,
            swap_heuristic=swap_heuristic,
            downstream_connection_layover_minutes=downstream_connection_layover_minutes,
        )

        # 6. Official airline departure (actual/revised if published, else scheduled)
        official_airline_departure = (
            current_leg.actual_departure or current_leg.scheduled_departure
        )

        return RealityAssessment(
            flight_query=flight_query,
            official_airline_departure=official_airline_departure,
            calculated_earliest_departure=turnaround_result.calculated_earliest_departure,
            delay_lead_time_minutes=turnaround_result.delay_lead_time_minutes,
            is_unavoidable_delay=turnaround_result.is_unavoidable_delay,
            swap_evaluation=swap_heuristic,
            rebooking_directive=rebooking_directive,
        )
