import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.watchlist import WatchlistItem
from app.schemas.flight import FlightLeg, FlightQuery, InboundTurnaround, RealityAssessment, SwapHeuristic
from app.services.watchlist_scheduler import run_milestone_check, start_watchlist_scheduler

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def create_sample_item(
    db,
    status="ARMED",
    t2_offset_hours=-1,
    sched_dep_offset_hours=1,
    carrier="DL",
    flight_number="450",
    departure_date="2026-10-24",
):
    now = datetime.now(timezone.utc)
    item = WatchlistItem(
        id=uuid.uuid4(),
        user_name="Trupti",
        carrier=carrier,
        flight_number=flight_number,
        departure_date=departure_date,
        origin_iata="ATL",
        destination_iata="MCO",
        origin_name="Atlanta",
        destination_name="Orlando",
        scheduled_departure=now + timedelta(hours=sched_dep_offset_hours),
        t2_scheduled_fetch=now + timedelta(hours=t2_offset_hours),
        status=status,
        latest_assessment=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.mark.asyncio
async def test_scheduler_task_start_and_clean_cancellation():
    """Verify background task initialization and clean graceful cancellation."""
    with patch("app.services.watchlist_scheduler.SessionLocal", TestingSessionLocal):
        task = asyncio.create_task(start_watchlist_scheduler(poll_interval=1))
        await asyncio.sleep(0.05)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_milestone_check_transitions_armed_to_evaluated_t2(db):
    """Verify flights past t2_scheduled_fetch transition from ARMED to EVALUATED_T2."""
    item = create_sample_item(db, status="ARMED", t2_offset_hours=-1, sched_dep_offset_hours=1)

    mock_aggregator = MagicMock()
    mock_leg = FlightLeg(
        flight_number="DL450",
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(hours=3),
        status="SCHEDULED",
    )
    mock_aggregator.get_flight_context = AsyncMock(return_value=(mock_leg, None, None))

    mock_engine = MagicMock()
    mock_assessment = RealityAssessment(
        flight_query=FlightQuery(carrier="DL", flight_number="450", departure_date="2026-10-24"),
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        official_airline_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        calculated_earliest_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        delay_lead_time_minutes=0,
        is_unavoidable_delay=False,
        swap_evaluation=SwapHeuristic(origin_is_hub=True, hub_type="FORTRESS_HUB", swap_probability="HIGH"),
        rebooking_directive="RELAX_IN_LOUNGE",
    )
    mock_engine.assess_flight_async = AsyncMock(return_value=mock_assessment)
    mock_notification = MagicMock()
    mock_notification.dispatch_assessment_alerts = AsyncMock(return_value=0)

    count, items, alerts, evaluated = await run_milestone_check(
        db=db,
        aggregator=mock_aggregator,
        engine=mock_engine,
        notification_service=mock_notification,
    )

    assert count == 1
    assert items == ["DL 450"]
    assert alerts == 0

    db.refresh(item)
    assert item.status == "EVALUATED_T2"
    assert item.latest_assessment is not None
    assert item.latest_assessment["rebooking_directive"] == "RELAX_IN_LOUNGE"


@pytest.mark.asyncio
async def test_milestone_check_triggers_alert_dispatch_on_unavoidable_delay(db):
    """Verify notification alert dispatch triggers when flight has unavoidable delay."""
    item = create_sample_item(db, status="ARMED", t2_offset_hours=-1, sched_dep_offset_hours=1)

    mock_aggregator = MagicMock()
    mock_leg = FlightLeg(
        flight_number="DL450",
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(hours=3),
        status="SCHEDULED",
    )
    mock_aggregator.get_flight_context = AsyncMock(return_value=(mock_leg, None, None))

    mock_engine = MagicMock()
    mock_assessment = RealityAssessment(
        flight_query=FlightQuery(carrier="DL", flight_number="450", departure_date="2026-10-24"),
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        official_airline_departure=datetime.now(timezone.utc) + timedelta(hours=1),
        calculated_earliest_departure=datetime.now(timezone.utc) + timedelta(hours=1, minutes=45),
        delay_lead_time_minutes=45,
        is_unavoidable_delay=True,
        swap_evaluation=SwapHeuristic(origin_is_hub=False, hub_type="OUTSTATION", swap_probability="NEAR_ZERO"),
        rebooking_directive="EXPEDITE_REBOOKING",
    )
    mock_engine.assess_flight_async = AsyncMock(return_value=mock_assessment)
    mock_notification = MagicMock()
    mock_notification.dispatch_assessment_alerts = AsyncMock(return_value=1)

    count, items, alerts, evaluated = await run_milestone_check(
        db=db,
        aggregator=mock_aggregator,
        engine=mock_engine,
        notification_service=mock_notification,
    )

    assert count == 1
    assert alerts == 1
    mock_notification.dispatch_assessment_alerts.assert_awaited_once_with(mock_assessment)

    db.refresh(item)
    assert item.status == "EVALUATED_T2"


@pytest.mark.asyncio
async def test_milestone_check_transitions_past_flight_to_departed(db):
    """Verify flight past scheduled departure transitions to DEPARTED."""
    # Scheduled departure was 30 minutes in the past
    item = create_sample_item(db, status="ARMED", t2_offset_hours=-3, sched_dep_offset_hours=-0.5)

    mock_aggregator = MagicMock()
    mock_leg = FlightLeg(
        flight_number="DL450",
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) - timedelta(minutes=30),
        scheduled_arrival=datetime.now(timezone.utc) + timedelta(hours=1),
        status="DEPARTED",
    )
    mock_aggregator.get_flight_context = AsyncMock(return_value=(mock_leg, None, None))

    mock_engine = MagicMock()
    mock_assessment = RealityAssessment(
        flight_query=FlightQuery(carrier="DL", flight_number="450", departure_date="2026-10-24"),
        origin_iata="ATL",
        destination_iata="MCO",
        scheduled_departure=datetime.now(timezone.utc) - timedelta(minutes=30),
        official_airline_departure=datetime.now(timezone.utc) - timedelta(minutes=30),
        calculated_earliest_departure=datetime.now(timezone.utc) - timedelta(minutes=30),
        delay_lead_time_minutes=0,
        is_unavoidable_delay=False,
        swap_evaluation=SwapHeuristic(origin_is_hub=True, hub_type="FORTRESS_HUB", swap_probability="HIGH"),
        rebooking_directive="RELAX_IN_LOUNGE",
    )
    mock_engine.assess_flight_async = AsyncMock(return_value=mock_assessment)
    mock_notification = MagicMock()
    mock_notification.dispatch_assessment_alerts = AsyncMock(return_value=0)

    count, items, alerts, evaluated = await run_milestone_check(
        db=db,
        aggregator=mock_aggregator,
        engine=mock_engine,
        notification_service=mock_notification,
    )

    assert count == 1
    db.refresh(item)
    assert item.status == "DEPARTED"
