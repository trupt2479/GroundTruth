from datetime import date, timedelta
from typing import List, Optional

from app.schemas.flight import (
    AirspaceAdvisory,
    AlternativeFlight,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
)
from app.services.action_engine import ActionEngine
from app.services.flight_scout import AlternativeFlightScout
from app.services.swap_evaluator import SwapEvaluator
from app.services.turnaround_engine import TurnaroundEngine


class PredictionEngine:
    """Orchestrates turnaround physics, FAA airspace programs, hub swap evaluation, and prescriptive action directives."""

    def __init__(
        self,
        turnaround_engine: Optional[TurnaroundEngine] = None,
        swap_evaluator: Optional[SwapEvaluator] = None,
        action_engine: Optional[ActionEngine] = None,
        flight_scout: Optional[AlternativeFlightScout] = None,
    ):
        self.turnaround = turnaround_engine or TurnaroundEngine()
        self.swap_evaluator = swap_evaluator or SwapEvaluator()
        self.action = action_engine or ActionEngine()
        self.scout = flight_scout or AlternativeFlightScout()

    async def assess_flight_async(
        self,
        current_leg: FlightLeg,
        turnaround: InboundTurnaround,
        flight_query: Optional[FlightQuery] = None,
        downstream_connection_layover_minutes: Optional[int] = None,
        airspace_advisory: Optional[AirspaceAdvisory] = None,
    ) -> RealityAssessment:
        """Asynchronously assesses flight reality and scout alternative flights when rebooking is expedited."""
        assessment = self.assess_flight(
            current_leg=current_leg,
            turnaround=turnaround,
            flight_query=flight_query,
            downstream_connection_layover_minutes=downstream_connection_layover_minutes,
            airspace_advisory=airspace_advisory,
        )

        # Trigger flight scout when directive is EXPEDITE_REBOOKING
        if assessment.rebooking_directive == "EXPEDITE_REBOOKING":
            carrier = assessment.flight_query.carrier
            origin = current_leg.origin_iata
            dest = current_leg.destination_iata
            after_time = current_leg.scheduled_departure

            alternatives = await self.scout.find_alternative_flights(
                carrier=carrier,
                origin_iata=origin,
                destination_iata=dest,
                after_time=after_time,
            )
            assessment.alternative_flights = alternatives

        return assessment

    def assess_flight(
        self,
        current_leg: FlightLeg,
        turnaround: InboundTurnaround,
        flight_query: Optional[FlightQuery] = None,
        downstream_connection_layover_minutes: Optional[int] = None,
        airspace_advisory: Optional[AirspaceAdvisory] = None,
        alternative_flights: Optional[List[AlternativeFlight]] = None,
    ) -> RealityAssessment:
        """Contrasts official airline schedule against turnaround physics, FAA airspace programs, and spare capacity."""
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

        calculated_earliest_departure = turnaround_result.calculated_earliest_departure
        delay_lead_time_minutes = turnaround_result.delay_lead_time_minutes
        is_unavoidable_delay = turnaround_result.is_unavoidable_delay

        # 3. Incorporate FAA Airspace Programs (Ground Stops & Ground Delay Programs)
        airspace_escalation = False
        if airspace_advisory and airspace_advisory.advisory_active:
            if airspace_advisory.program_type == "GROUND_STOP":
                is_unavoidable_delay = True
                airspace_escalation = True
                # Inject ground stop delay if lead time is smaller
                if airspace_advisory.avg_delay_minutes > delay_lead_time_minutes:
                    delay_lead_time_minutes = airspace_advisory.avg_delay_minutes
                    calculated_earliest_departure = current_leg.scheduled_departure + timedelta(
                        minutes=delay_lead_time_minutes
                    )
            elif airspace_advisory.program_type == "GROUND_DELAY_PROGRAM":
                # Inject GDP average delay into earliest departure
                gdp_earliest = current_leg.scheduled_departure + timedelta(
                    minutes=airspace_advisory.avg_delay_minutes
                )
                if gdp_earliest > calculated_earliest_departure:
                    calculated_earliest_departure = gdp_earliest
                    delay_lead_time_minutes = max(
                        delay_lead_time_minutes, airspace_advisory.avg_delay_minutes
                    )
                    is_unavoidable_delay = True

        # 4. Inbound delay magnitude
        inbound_delay_minutes = delay_lead_time_minutes

        # 5. Evaluate tail swap likelihood
        swap_heuristic = self.swap_evaluator.evaluate_swap(
            origin_iata=current_leg.origin_iata,
            inbound_delay_minutes=inbound_delay_minutes,
        )

        # 6. Determine prescriptive rebooking directive
        if airspace_escalation:
            rebooking_directive = "EXPEDITE_REBOOKING"
        else:
            rebooking_directive = self.action.determine_action(
                is_unavoidable_delay=is_unavoidable_delay,
                delay_lead_time_minutes=delay_lead_time_minutes,
                swap_heuristic=swap_heuristic,
                downstream_connection_layover_minutes=downstream_connection_layover_minutes,
            )

        # 7. Official airline departure (actual/revised if published, else scheduled)
        official_airline_departure = (
            current_leg.actual_departure or current_leg.scheduled_departure
        )

        return RealityAssessment(
            flight_query=flight_query,
            official_airline_departure=official_airline_departure,
            calculated_earliest_departure=calculated_earliest_departure,
            delay_lead_time_minutes=delay_lead_time_minutes,
            is_unavoidable_delay=is_unavoidable_delay,
            swap_evaluation=swap_heuristic,
            rebooking_directive=rebooking_directive,
            airspace_advisory=airspace_advisory,
            alternative_flights=alternative_flights or [],
        )
