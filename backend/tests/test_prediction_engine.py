from datetime import date, datetime, timedelta, timezone
import pytest

from app.schemas.flight import (
    AircraftInfo,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
)
from app.services.action_engine import ActionEngine
from app.services.prediction_engine import PredictionEngine
from app.services.swap_evaluator import SwapEvaluator
from app.services.turnaround_engine import TurnaroundEngine


@pytest.fixture
def prediction_engine():
    return PredictionEngine()


def test_scenario_a_outstation_trap(prediction_engine):
    """Scenario A (Outstation Trap):

    B738 inbound to BDL delayed 90 mins -> Unavoidable delay = True, Swap = NEAR_ZERO, Directive = EXPEDITE_REBOOKING.
    """
    # Scheduled departure from BDL at 15:00 UTC
    sched_dep = datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc)

    # Inbound B738 touches down 90 mins late relative to the needed turnaround
    # For a 15:00 departure and MTT=45 min, standard touchdown is 14:15.
    # Touchdown is 90 mins delayed from standard -> 15:45 UTC
    touchdown = datetime(2026, 10, 24, 15, 45, tzinfo=timezone.utc)

    aircraft = AircraftInfo(
        icao_type="B738",
        tail_number="N37408",
        category="NARROWBODY",
    )

    current_leg = FlightLeg(
        flight_number="UA1550",
        origin_iata="BDL",  # Outstation
        destination_iata="ORD",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2, minutes=30),
        actual_departure=sched_dep,  # Airline claims still on schedule!
        actual_arrival=None,
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    assessment: RealityAssessment = prediction_engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
    )

    # Assertions
    assert assessment.is_unavoidable_delay is True
    assert assessment.calculated_earliest_departure == touchdown + timedelta(minutes=45)
    # Earliest departure is 16:30, scheduled was 15:00 -> 90 minutes delay lead time
    assert assessment.delay_lead_time_minutes == 90
    assert assessment.swap_evaluation.origin_is_hub is False
    assert assessment.swap_evaluation.hub_type == "OUTSTATION"
    assert assessment.swap_evaluation.swap_probability == "NEAR_ZERO"
    assert assessment.rebooking_directive == "EXPEDITE_REBOOKING"


def test_scenario_b_hub_spare_feasible(prediction_engine):
    """Scenario B (Hub Spare Feasible):

    A320 inbound to ATL delayed 60 mins -> Unavoidable delay = True, Origin = FORTRESS_HUB, Swap = HIGH, Directive = MONITOR_CLOSELY.
    """
    sched_dep = datetime(2026, 10, 24, 18, 0, tzinfo=timezone.utc)
    # Touchdown at 18:15 UTC (60 mins after ideal 17:15 touchdown for 45 min MTT)
    touchdown = datetime(2026, 10, 24, 18, 15, tzinfo=timezone.utc)

    aircraft = AircraftInfo(
        icao_type="A320",
        tail_number="N628DL",
        category="NARROWBODY",
    )

    current_leg = FlightLeg(
        flight_number="DL1234",
        origin_iata="ATL",  # Fortress Hub
        destination_iata="LGA",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2),
        actual_departure=sched_dep,
        actual_arrival=None,
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    assessment: RealityAssessment = prediction_engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
    )

    # Assertions
    assert assessment.is_unavoidable_delay is True
    # Earliest departure is 19:00, scheduled was 18:00 -> 60 minutes delay lead time
    assert assessment.delay_lead_time_minutes == 60
    assert assessment.swap_evaluation.origin_is_hub is True
    assert assessment.swap_evaluation.hub_type == "FORTRESS_HUB"
    assert assessment.swap_evaluation.swap_probability == "HIGH"
    assert assessment.rebooking_directive == "MONITOR_CLOSELY"


def test_scenario_c_ontime_narrowbody(prediction_engine):
    """Scenario C (On-Time Narrowbody):

    Inbound touches down on schedule -> Unavoidable delay = False, Directive = RELAX_IN_LOUNGE.
    """
    sched_dep = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    # Touchdown at 11:00 UTC (60 mins prior, ample buffer for 45 min MTT)
    touchdown = datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc)

    aircraft = AircraftInfo(
        icao_type="B738",
        tail_number="N1422U",
        category="NARROWBODY",
    )

    current_leg = FlightLeg(
        flight_number="UA789",
        origin_iata="DEN",
        destination_iata="ORD",
        scheduled_departure=sched_dep,
        scheduled_arrival=sched_dep + timedelta(hours=2, minutes=20),
        actual_departure=None,
        actual_arrival=None,
        status="SCHEDULED",
    )

    turnaround = InboundTurnaround(
        previous_legs=[],
        assigned_aircraft=aircraft,
        mtt_minutes=45,
        estimated_touchdown=touchdown,
        earliest_possible_departure=touchdown + timedelta(minutes=45),
    )

    assessment: RealityAssessment = prediction_engine.assess_flight(
        current_leg=current_leg,
        turnaround=turnaround,
    )

    # Assertions
    assert assessment.is_unavoidable_delay is False
    assert assessment.delay_lead_time_minutes == 0
    assert assessment.rebooking_directive == "RELAX_IN_LOUNGE"


def test_turnaround_fleet_buffer_lookup():
    engine = TurnaroundEngine()

    reg_ac = AircraftInfo(icao_type="E175", tail_number="N101SY", category="REGIONAL")
    nb_ac = AircraftInfo(icao_type="A320", tail_number="N202DL", category="NARROWBODY")
    wb_ac = AircraftInfo(icao_type="B772", tail_number="N777UA", category="WIDEBODY")

    assert engine.get_mtt_minutes(reg_ac.category) == 35
    assert engine.get_mtt_minutes(nb_ac.category) == 45
    assert engine.get_mtt_minutes(wb_ac.category) == 75

    base_time = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    res_reg = engine.calculate_turnaround(base_time, base_time, reg_ac)
    assert res_reg.mtt_minutes == 35
    assert res_reg.calculated_earliest_departure == base_time + timedelta(minutes=35)
    assert res_reg.is_unavoidable_delay is True
    assert res_reg.delay_lead_time_minutes == 35


def test_swap_evaluator_hubs_and_outstations():
    evaluator = SwapEvaluator()

    # Outstation with > 30 min delay
    out_swap = evaluator.evaluate_swap(origin_iata="IND", inbound_delay_minutes=40)
    assert out_swap.origin_is_hub is False
    assert out_swap.hub_type == "OUTSTATION"
    assert out_swap.swap_probability == "NEAR_ZERO"

    # Outstation with minimal delay
    out_ontime = evaluator.evaluate_swap(origin_iata="IND", inbound_delay_minutes=10)
    assert out_ontime.swap_probability == "LOW"

    # Fortress hub with > 45 min delay
    hub_high = evaluator.evaluate_swap(origin_iata="DFW", inbound_delay_minutes=50)
    assert hub_high.origin_is_hub is True
    assert hub_high.hub_type == "FORTRESS_HUB"
    assert hub_high.swap_probability == "HIGH"

    # Fortress hub with 20 min delay
    hub_mod = evaluator.evaluate_swap(origin_iata="ORD", inbound_delay_minutes=20)
    assert hub_mod.swap_probability == "MODERATE"


def test_action_engine_layover_compression():
    action_engine = ActionEngine()
    swap = SwapEvaluator().evaluate_swap("BDL", 45)

    # 50 min layover, 40 min delay -> remaining 10 min < 40 min MCT -> EXPEDITE_REBOOKING
    directive = action_engine.determine_action(
        is_unavoidable_delay=True,
        delay_lead_time_minutes=40,
        swap_heuristic=swap,
        downstream_connection_layover_minutes=50,
        minimum_connection_time_minutes=40,
    )
    assert directive == "EXPEDITE_REBOOKING"
