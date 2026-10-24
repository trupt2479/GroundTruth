from typing import Set
from app.schemas.flight import SwapHeuristic

# Fortress Hubs database
FORTRESS_HUBS: Set[str] = {
    "ATL",
    "ORD",
    "DFW",
    "DEN",
    "CLT",
    "IAH",
    "DTW",
    "MSP",
    "EWR",
    "SFO",
}


class SwapEvaluator:
    """Evaluates whether an airline can mitigate an inbound physical delay via an equipment swap."""

    @staticmethod
    def is_fortress_hub(airport_iata: str) -> bool:
        return (airport_iata or "").strip().upper() in FORTRESS_HUBS

    def evaluate_swap(
        self,
        origin_iata: str,
        inbound_delay_minutes: int,
    ) -> SwapHeuristic:
        """Swap Probability Logic:

        - If Origin is OUTSTATION and Inbound Delay > 30 minutes:
            Swap Probability = NEAR_ZERO (Airline has no idle spare aircraft).
        - If Origin is FORTRESS_HUB and Inbound Delay > 45 minutes:
            Swap Probability = HIGH (Airline maintains spare tails/crews).
        - If Origin is FORTRESS_HUB and Inbound Delay > 15 minutes:
            Swap Probability = MODERATE.
        - If On-Time or minor turn buffer (<= 15 min at hub, or <= 30 min at outstation):
            Swap Probability = LOW.
        """
        is_hub = self.is_fortress_hub(origin_iata)
        hub_type = "FORTRESS_HUB" if is_hub else "OUTSTATION"

        if not is_hub:
            if inbound_delay_minutes > 30:
                swap_prob = "NEAR_ZERO"
            else:
                swap_prob = "LOW"
        else:
            if inbound_delay_minutes > 45:
                swap_prob = "HIGH"
            elif inbound_delay_minutes > 15:
                swap_prob = "MODERATE"
            else:
                swap_prob = "LOW"

        return SwapHeuristic(
            origin_is_hub=is_hub,
            hub_type=hub_type,
            swap_probability=swap_prob,
        )
