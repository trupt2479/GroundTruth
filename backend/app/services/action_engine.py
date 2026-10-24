from typing import Literal, Optional
from app.schemas.flight import SwapHeuristic

RebookingDirective = Literal["RELAX_IN_LOUNGE", "MONITOR_CLOSELY", "EXPEDITE_REBOOKING"]


class ActionEngine:
    """Layover compression and prescriptive travel guidance engine."""

    def determine_action(
        self,
        is_unavoidable_delay: bool,
        delay_lead_time_minutes: int,
        swap_heuristic: SwapHeuristic,
        downstream_connection_layover_minutes: Optional[int] = None,
        minimum_connection_time_minutes: int = 40,
    ) -> RebookingDirective:
        """Determines prescriptive action directive for traveler.

        Directives:
        - 'RELAX_IN_LOUNGE': On-time or minor delay with intact buffer.
        - 'MONITOR_CLOSELY': Tightening turnaround/connection, potential equipment swap at hub.
        - 'EXPEDITE_REBOOKING': Inbound delayed at outstation with guaranteed misconnection;
          proceed to customer service immediately before seats vanish.
        """
        # Case 1: No unavoidable delay
        if not is_unavoidable_delay:
            return "RELAX_IN_LOUNGE"

        # Check downstream connection compression if specified
        guaranteed_misconnection = False
        if downstream_connection_layover_minutes is not None:
            remaining_layover = (
                downstream_connection_layover_minutes - delay_lead_time_minutes
            )
            if remaining_layover < minimum_connection_time_minutes:
                guaranteed_misconnection = True

        # Case 2: Outstation Trap or severe unrecoverable delay
        # If at outstation with unavoidable delay (no spare tail) -> EXPEDITE_REBOOKING
        if swap_heuristic.swap_probability == "NEAR_ZERO":
            return "EXPEDITE_REBOOKING"

        # If there is a guaranteed misconnection on downstream itinerary
        if guaranteed_misconnection:
            if swap_heuristic.swap_probability in ("HIGH", "MODERATE"):
                return "MONITOR_CLOSELY"
            return "EXPEDITE_REBOOKING"

        # Case 3: At a Fortress Hub with spare availability
        if swap_heuristic.origin_is_hub:
            if swap_heuristic.swap_probability in ("HIGH", "MODERATE"):
                return "MONITOR_CLOSELY"

        # Case 4: Severe delay lead time (> 60 mins)
        if delay_lead_time_minutes > 60:
            return "EXPEDITE_REBOOKING"

        return "MONITOR_CLOSELY"
