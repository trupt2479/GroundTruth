from datetime import date
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.schemas.flight import AirspaceAdvisory, FlightQuery, RealityAssessment
from app.services.aerodatabox_client import (
    AeroDataBoxError,
    AeroDataBoxRateLimitError,
    AeroDataBoxServiceUnavailableError,
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


@router.get(
    "/evaluate",
    response_model=RealityAssessment,
    summary="Evaluate Flight Reality",
    description="Contrasts official airline schedule against inbound aircraft turnaround physics, FAA airspace status, and hub tail-swap probability.",
)
async def evaluate_flight(
    carrier: Annotated[
        str,
        Query(
            description="2-letter uppercase airline IATA code (e.g. 'UA', 'DL')",
            examples=["UA"],
        ),
    ],
    flight_num: Annotated[
        str,
        Query(
            description="Alphanumeric flight number (1-4 chars, e.g. '1422')",
            examples=["1422"],
        ),
    ],
    date_str: Annotated[
        str,
        Query(
            alias="date",
            description="Departure date in YYYY-MM-DD format",
            examples=["2026-10-24"],
        ),
    ],
    aggregator: FlightAggregator = Depends(get_flight_aggregator),
    engine: PredictionEngine = Depends(get_prediction_engine),
    faa_client: FaaNasClient = Depends(get_faa_nas_client),
) -> RealityAssessment:
    """Validate query, aggregate live context, correlate FAA airspace programs, scout alternative flights, and produce a RealityAssessment."""
    try:
        flight_query = FlightQuery(
            carrier=carrier,
            flight_number=flight_num,
            departure_date=date.fromisoformat(date_str),
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed flight query parameters: {exc}",
        )

    try:
        current_leg, turnaround, telemetry = await aggregator.get_flight_context(
            flight_query
        )
    except (AeroDataBoxRateLimitError, AeroDataBoxServiceUnavailableError) as exc:
        logger.error("Upstream flight data source unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"External flight telemetry service temporarily unavailable: {exc}",
        )
    except AeroDataBoxError as exc:
        logger.error("Flight data error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream flight data error: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error aggregating flight context: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing flight assessment",
        )

    if not current_leg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flight {carrier}{flight_num} on {date_str} not found.",
        )

    # Check FAA NAS airspace advisory for departure airport
    airspace_advisory: AirspaceAdvisory | None = None
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
        logger.warning("Failed to retrieve FAA airspace advisory: %s", exc)

    assessment = await engine.assess_flight_async(
        current_leg=current_leg,
        turnaround=turnaround,
        flight_query=flight_query,
        airspace_advisory=airspace_advisory,
    )

    return assessment
