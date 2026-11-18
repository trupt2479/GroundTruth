from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from app.schemas.flight import (
    AirspaceAdvisory,
    AlternativeFlight,
    CrewDutyAssessment,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
)
from app.services.airport_timezones import get_airport_timezone, to_local_iso
from app.services.action_engine import ActionEngine
from app.services.crew_duty_watchdog import CrewDutyWatchdog
from app.services.flight_scout import AlternativeFlightScout
from app.services.swap_evaluator import SwapEvaluator
from app.services.turnaround_engine import TurnaroundEngine


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime carries timezone.utc for safe epoch math across date rollovers."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class PredictionEngine:
    """Orchestrates turnaround physics, FAA airspace programs, crew duty legality, hub swap evaluation, and prescriptive action directives."""

    def __init__(
        self,
        turnaround_engine: Optional[TurnaroundEngine] = None,
        swap_evaluator: Optional[SwapEvaluator] = None,
        action_engine: Optional[ActionEngine] = None,
        flight_scout: Optional[AlternativeFlightScout] = None,
        crew_watchdog: Optional[CrewDutyWatchdog] = None,
    ):
        self.turnaround = turnaround_engine or TurnaroundEngine()
        self.swap_evaluator = swap_evaluator or SwapEvaluator()
        self.action = action_engine or ActionEngine()
        self.scout = flight_scout or AlternativeFlightScout()
        self.crew_watchdog = crew_watchdog or CrewDutyWatchdog()

    async def assess_flight_async(
        self,
        current_leg: FlightLeg,
        turnaround: InboundTurnaround,
        flight_query: Optional[FlightQuery] = None,
        downstream_connection_layover_minutes: Optional[int] = None,
        airspace_advisory: Optional[AirspaceAdvisory] = None,
        live_telemetry: Optional[dict] = None,
    ) -> RealityAssessment:
        """Asynchronously assesses flight reality, calculates crew duty limits, and scouts alternative flights when rebooking is expedited."""
        assessment = self.assess_flight(
            current_leg=current_leg,
            turnaround=turnaround,
            flight_query=flight_query,
            downstream_connection_layover_minutes=downstream_connection_layover_minutes,
            airspace_advisory=airspace_advisory,
            live_telemetry=live_telemetry,
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
        live_telemetry: Optional[dict] = None,
    ) -> RealityAssessment:
        """Contrasts official airline schedule against turnaround physics, FAA airspace programs, crew duty legality, and spare capacity."""
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

        # Rollover Epoch Math Guard: compute delay strictly from timezone-aware UTC epoch differences
        earliest_dep_utc = _ensure_utc(calculated_earliest_departure)
        scheduled_dep_utc = _ensure_utc(current_leg.scheduled_departure)
        if earliest_dep_utc and scheduled_dep_utc:
            delta_seconds = (earliest_dep_utc - scheduled_dep_utc).total_seconds()
            delay_lead_time_minutes = max(0, int(delta_seconds // 60))
            is_unavoidable_delay = is_unavoidable_delay or (earliest_dep_utc > scheduled_dep_utc)

        # 4. Inbound delay magnitude
        inbound_delay_minutes = delay_lead_time_minutes

        # 5. Evaluate FAA Part 117 Crew Duty Limits
        crew_duty = self.crew_watchdog.assess_crew_duty(
            current_leg=current_leg,
            previous_legs=turnaround.previous_legs,
            calculated_earliest_departure=calculated_earliest_departure,
        )

        crew_timeout_escalation = False
        if crew_duty.timeout_risk == "HIGH":
            is_unavoidable_delay = True
            crew_timeout_escalation = True

        # 6. Evaluate tail swap likelihood
        swap_heuristic = self.swap_evaluator.evaluate_swap(
            origin_iata=current_leg.origin_iata,
            inbound_delay_minutes=inbound_delay_minutes,
        )

        # 7. Determine prescriptive rebooking directive
        if airspace_escalation or crew_timeout_escalation:
            rebooking_directive = "EXPEDITE_REBOOKING"
        else:
            rebooking_directive = self.action.determine_action(
                is_unavoidable_delay=is_unavoidable_delay,
                delay_lead_time_minutes=delay_lead_time_minutes,
                swap_heuristic=swap_heuristic,
                downstream_connection_layover_minutes=downstream_connection_layover_minutes,
            )

        # 8. Official airline departure (actual/revised if published, else scheduled)
        official_airline_departure = (
            current_leg.actual_departure or current_leg.scheduled_departure
        )

        # 9. Airborne Equipment Swap Reconciliation
        is_booked_airborne = False
        if live_telemetry and isinstance(live_telemetry, dict):
            status = str(live_telemetry.get("flight_status") or "").upper()
            source = str(live_telemetry.get("telemetry_source") or "").upper()
            if status == "AIRBORNE" and source == "BOOKED_FLIGHT":
                is_booked_airborne = True

        if is_booked_airborne:
            is_unavoidable_delay = False
            rebooking_directive = "EN_ROUTE_ON_TIME"
            calculated_earliest_departure = official_airline_departure
            if current_leg.actual_arrival and current_leg.scheduled_arrival:
                act_arr_utc = _ensure_utc(current_leg.actual_arrival)
                sched_arr_utc = _ensure_utc(current_leg.scheduled_arrival)
                if act_arr_utc and sched_arr_utc and act_arr_utc > sched_arr_utc:
                    arr_delay = int((act_arr_utc - sched_arr_utc).total_seconds() // 60)
                    delay_lead_time_minutes = max(0, arr_delay)
                else:
                    delay_lead_time_minutes = 0
            else:
                delay_lead_time_minutes = 0

        # 10. Airport-local timezones and AeroDataBox native fallback
        origin_tz = get_airport_timezone(current_leg.origin_iata)
        destination_tz = get_airport_timezone(current_leg.destination_iata)

        scheduled_departure_local = (
            to_local_iso(current_leg.scheduled_departure, origin_tz)
            or current_leg.scheduled_departure_local
        )
        actual_departure_local = (
            to_local_iso(current_leg.actual_departure, origin_tz)
            or current_leg.actual_departure_local
        )
        scheduled_arrival_local = (
            to_local_iso(current_leg.scheduled_arrival, destination_tz)
            or current_leg.scheduled_arrival_local
        )
        actual_arrival_local = (
            to_local_iso(current_leg.actual_arrival, destination_tz)
            or current_leg.actual_arrival_local
        )

        return RealityAssessment(
            flight_query=flight_query,
            origin_iata=current_leg.origin_iata,
            destination_iata=current_leg.destination_iata,
            origin_name=current_leg.origin_name,
            destination_name=current_leg.destination_name,
            scheduled_departure=current_leg.scheduled_departure,
            actual_or_estimated_departure=current_leg.actual_departure,
            scheduled_arrival=current_leg.scheduled_arrival,
            actual_or_estimated_arrival=current_leg.actual_arrival,
            official_airline_departure=official_airline_departure,
            calculated_earliest_departure=calculated_earliest_departure,
            delay_lead_time_minutes=delay_lead_time_minutes,
            is_unavoidable_delay=is_unavoidable_delay,
            swap_evaluation=swap_heuristic,
            rebooking_directive=rebooking_directive,
            airspace_advisory=airspace_advisory,
            alternative_flights=alternative_flights or [],
            crew_duty=crew_duty,
            inbound_turnaround=turnaround,
            live_telemetry=live_telemetry,
            origin_tz=origin_tz,
            destination_tz=destination_tz,
            scheduled_departure_local=scheduled_departure_local,
            actual_departure_local=actual_departure_local,
            scheduled_arrival_local=scheduled_arrival_local,
            actual_arrival_local=actual_arrival_local,
        )
