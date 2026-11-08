import asyncio
from datetime import date, datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.watchlist import WatchlistItem
from app.schemas.flight import AirspaceAdvisory, FlightQuery, RealityAssessment
from app.services.faa_nas_client import FaaNasClient
from app.services.flight_aggregator import FlightAggregator
from app.services.notification_service import NotificationService
from app.services.prediction_engine import PredictionEngine

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is UTC timezone-aware for cross-database compatibility."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def run_milestone_check(
    db: Session,
    aggregator: Optional[FlightAggregator] = None,
    engine: Optional[PredictionEngine] = None,
    faa_client: Optional[FaaNasClient] = None,
    notification_service: Optional[NotificationService] = None,
) -> Tuple[int, List[str], int, List[WatchlistItem]]:
    """Scan and evaluate watchlist items that have reached their T-2h milestone.

    Returns:
        Tuple of (evaluated_count, items_evaluated_identifiers, alerts_dispatched_count, evaluated_item_objects)
    """
    now = datetime.now(timezone.utc)
    aggregator = aggregator or FlightAggregator()
    engine = engine or PredictionEngine()
    faa_client = faa_client or FaaNasClient()
    notification_service = notification_service or NotificationService()

    armed_items: List[WatchlistItem] = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.status == "ARMED")
        .all()
    )
    candidates: List[WatchlistItem] = [
        item for item in armed_items
        if item.t2_scheduled_fetch and _to_utc(item.t2_scheduled_fetch) <= now
    ]

    evaluated_items: List[WatchlistItem] = []
    items_evaluated: List[str] = []
    alerts_dispatched = 0

    for item in candidates:
        try:
            logger.info(
                "WatchlistScheduler: Processing due flight %s %s (%s) for user %s",
                item.carrier,
                item.flight_number,
                item.departure_date,
                item.user_name,
            )
            q = FlightQuery(
                carrier=item.carrier,
                flight_number=item.flight_number,
                departure_date=date.fromisoformat(item.departure_date),
            )

            current_leg, turnaround, telemetry = await aggregator.get_flight_context(q)
            if not current_leg:
                logger.warning(
                    "WatchlistScheduler: Flight %s%s returned no leg context",
                    item.carrier,
                    item.flight_number,
                )
                continue

            advisory = None
            try:
                adv_data = await faa_client.get_airport_airspace_status(current_leg.origin_iata)
                if adv_data and adv_data.get("advisory_active"):
                    advisory = AirspaceAdvisory(
                        airport_iata=adv_data["airport_iata"],
                        program_type=adv_data["status_type"],
                        reason=adv_data.get("reason"),
                        avg_delay_minutes=adv_data.get("avg_delay_minutes", 0),
                        advisory_active=True,
                    )
            except Exception as exc:
                logger.warning("WatchlistScheduler: Could not retrieve FAA advisory: %s", exc)

            assessment: RealityAssessment = await engine.assess_flight_async(
                current_leg=current_leg,
                turnaround=turnaround,
                flight_query=q,
                airspace_advisory=advisory,
                live_telemetry=telemetry,
            )

            # Check departure transition
            is_departed = False
            act_dep = _to_utc(assessment.actual_or_estimated_departure)
            sched_dep = _to_utc(item.scheduled_departure)

            if current_leg.status in ("DEPARTED", "ARRIVED", "LANDED"):
                is_departed = True
            elif sched_dep and sched_dep < now:
                # If scheduled departure is in the past, verify it didn't get estimated into the future
                if not act_dep or act_dep < now:
                    is_departed = True
            elif act_dep and act_dep < now and (not sched_dep or sched_dep < now):
                is_departed = True

            item.status = "DEPARTED" if is_departed else "EVALUATED_T2"
            item.latest_assessment = assessment.model_dump(mode="json")
            item.updated_at = now
            db.add(item)
            evaluated_items.append(item)
            items_evaluated.append(f"{item.carrier} {item.flight_number}")

            # Proactive Alert Dispatch
            if (
                assessment.is_unavoidable_delay
                or assessment.rebooking_directive == "EXPEDITE_REBOOKING"
                or assessment.delay_lead_time_minutes >= 30
            ):
                try:
                    dispatched = await notification_service.dispatch_assessment_alerts(assessment)
                    alerts_dispatched += dispatched
                    logger.info(
                        "WatchlistScheduler: Dispatched %d alert(s) for flight %s%s",
                        dispatched,
                        item.carrier,
                        item.flight_number,
                    )
                except Exception as exc:
                    logger.error("WatchlistScheduler: Failed to dispatch alert: %s", exc)

        except Exception as exc:
            logger.error(
                "WatchlistScheduler: Error evaluating watchlist item %s (%s%s): %s",
                item.id,
                item.carrier,
                item.flight_number,
                exc,
                exc_info=True,
            )

    if evaluated_items:
        db.commit()
        for it in evaluated_items:
            db.refresh(it)

    return len(evaluated_items), items_evaluated, alerts_dispatched, evaluated_items


async def start_watchlist_scheduler(poll_interval: Optional[int] = None) -> None:
    """Continuous background loop scanning and evaluating watchlist milestones."""
    interval = poll_interval or settings.WATCHLIST_POLL_INTERVAL_SECONDS
    logger.info("WatchlistScheduler: Background loop started with %ds interval", interval)

    while True:
        try:
            db: Session = SessionLocal()
            try:
                evaluated_count, items, alerts, _ = await run_milestone_check(db)
                if evaluated_count > 0:
                    logger.info(
                        "WatchlistScheduler: Cycle complete. Evaluated: %d (%s), Alerts: %d",
                        evaluated_count,
                        ", ".join(items),
                        alerts,
                    )
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("WatchlistScheduler: Task cancelled. Exiting cleanly.")
            raise
        except Exception as exc:
            logger.error("WatchlistScheduler: Unhandled error in scheduler cycle: %s", exc, exc_info=True)

        await asyncio.sleep(interval)
