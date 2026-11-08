import logging
from datetime import date, datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.watchlist import WatchlistItem
from app.schemas.flight import AirspaceAdvisory, FlightQuery
from app.schemas.watchlist import (
    MilestoneCheckResponse,
    WatchlistCreate,
    WatchlistResponse,
)
from app.services.faa_nas_client import FaaNasClient
from app.services.flight_aggregator import FlightAggregator
from app.services.prediction_engine import PredictionEngine

logger = logging.getLogger(__name__)

router = APIRouter()


def get_flight_aggregator() -> FlightAggregator:
    return FlightAggregator()


def get_prediction_engine() -> PredictionEngine:
    return PredictionEngine()


def get_faa_nas_client() -> FaaNasClient:
    return FaaNasClient()


@router.post("/", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist_item(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    aggregator: FlightAggregator = Depends(get_flight_aggregator),
    engine: PredictionEngine = Depends(get_prediction_engine),
    faa_client: FaaNasClient = Depends(get_faa_nas_client),
):
    """Save a flight to the persistent watchlist and compute T-2h milestone schedule."""
    carrier = payload.carrier.strip().upper()
    flight_number = payload.flight_number.strip()
    departure_date = payload.departure_date.strip()
    user_name = payload.user_name.strip()

    # 1. Check if already exists for this user
    existing = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.user_name == user_name,
            WatchlistItem.carrier == carrier,
            WatchlistItem.flight_number == flight_number,
            WatchlistItem.departure_date == departure_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Flight {carrier} {flight_number} on {departure_date} is already on your watchlist.",
        )

    # 2. Run initial assessment via FlightAggregator
    try:
        query = FlightQuery(
            carrier=carrier,
            flight_number=flight_number,
            departure_date=date.fromisoformat(departure_date),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid flight query: {exc}",
        )

    current_leg, turnaround, telemetry = await aggregator.get_flight_context(query)
    if not current_leg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight {carrier} {flight_number} on {departure_date} not found.",
        )

    airspace_advisory = None
    try:
        advisory_data = await faa_client.get_airport_airspace_status(current_leg.origin_iata)
        if advisory_data and advisory_data.get("advisory_active"):
            airspace_advisory = AirspaceAdvisory(
                airport_iata=advisory_data["airport_iata"],
                program_type=advisory_data["status_type"],
                reason=advisory_data.get("reason"),
                avg_delay_minutes=advisory_data.get("avg_delay_minutes", 0),
                advisory_active=True,
            )
    except Exception as exc:
        logger.warning("Could not retrieve FAA advisory for watchlist add: %s", exc)

    assessment = await engine.assess_flight_async(
        current_leg=current_leg,
        turnaround=turnaround,
        flight_query=query,
        airspace_advisory=airspace_advisory,
        live_telemetry=telemetry,
    )

    sched_dep = assessment.scheduled_departure or current_leg.scheduled_departure
    # 3. Calculate t2_scheduled_fetch = scheduled_departure - timedelta(hours=2)
    t2_fetch = sched_dep - timedelta(hours=2) if sched_dep else None

    # 4. Persist in database
    item = WatchlistItem(
        user_name=user_name,
        carrier=carrier,
        flight_number=flight_number,
        departure_date=departure_date,
        origin_iata=assessment.origin_iata,
        destination_iata=assessment.destination_iata,
        origin_name=assessment.origin_name,
        destination_name=assessment.destination_name,
        scheduled_departure=sched_dep,
        t2_scheduled_fetch=t2_fetch,
        status="ARMED",
        latest_assessment=assessment.model_dump(mode="json"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/", response_model=List[WatchlistResponse])
def get_watchlist(
    user_name: str = Query(default="Trupti", description="User watchlist owner identifier"),
    db: Session = Depends(get_db),
):
    """Retrieve all watched flights for the given user, ordered by created_at DESC."""
    return (
        db.query(WatchlistItem)
        .filter(WatchlistItem.user_name == user_name)
        .order_by(WatchlistItem.created_at.desc())
        .all()
    )


@router.delete("/{item_id}", status_code=status.HTTP_200_OK)
def delete_watchlist_item(
    item_id: str,
    db: Session = Depends(get_db),
):
    """Remove a flight from the persistent watchlist."""
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Watchlist item '{item_id}' not found.",
        )
    db.delete(item)
    db.commit()
    return {"status": "success", "message": f"Watchlist item '{item_id}' removed."}


@router.post("/check-milestones", response_model=MilestoneCheckResponse)
async def check_milestones(
    db: Session = Depends(get_db),
    aggregator: FlightAggregator = Depends(get_flight_aggregator),
    engine: PredictionEngine = Depends(get_prediction_engine),
    faa_client: FaaNasClient = Depends(get_faa_nas_client),
):
    """Scan and evaluate flights that reached their T-2h milestone."""
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.status == "ARMED",
            WatchlistItem.t2_scheduled_fetch <= now,
        )
        .all()
    )

    evaluated_items = []
    for item in candidates:
        try:
            q = FlightQuery(
                carrier=item.carrier,
                flight_number=item.flight_number,
                departure_date=date.fromisoformat(item.departure_date),
            )
            current_leg, turnaround, telemetry = await aggregator.get_flight_context(q)
            if current_leg:
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
                except Exception:
                    pass

                assessment = await engine.assess_flight_async(
                    current_leg=current_leg,
                    turnaround=turnaround,
                    flight_query=q,
                    airspace_advisory=advisory,
                    live_telemetry=telemetry,
                )

                item.latest_assessment = assessment.model_dump(mode="json")
                item.status = "EVALUATED_T2"
                item.updated_at = datetime.now(timezone.utc)
                db.add(item)
                evaluated_items.append(item)
        except Exception as exc:
            logger.error("Failed to check milestone for watchlist item %s: %s", item.id, exc)

    db.commit()
    for it in evaluated_items:
        db.refresh(it)

    return MilestoneCheckResponse(
        checked_count=len(candidates),
        evaluated_count=len(evaluated_items),
        items=evaluated_items,
    )
