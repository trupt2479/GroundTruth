import asyncio
from datetime import date
import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.schemas.flight import FlightQuery
from app.services.flight_aggregator import FlightAggregator
from app.services.prediction_engine import PredictionEngine

logger = logging.getLogger(__name__)

router = APIRouter()


def get_flight_aggregator() -> FlightAggregator:
    return FlightAggregator()


def get_prediction_engine() -> PredictionEngine:
    return PredictionEngine()


async def flight_event_generator(
    flight_query: FlightQuery,
    aggregator: FlightAggregator,
    engine: PredictionEngine,
    request: Request,
    heartbeat_interval: float = 15.0,
    poll_interval: float = 5.0,
) -> AsyncGenerator[str, None]:
    """Generates Server-Sent Events (SSE) for real-time flight assessment monitoring.

    - Initial message with full RealityAssessment.
    - Periodic heartbeats (: keep-alive) every heartbeat_interval seconds.
    - TICK/UPDATE delta events.
    - Clean cancellation when client disconnects.
    """
    last_assessment_json = None
    last_heartbeat_time = asyncio.get_event_loop().time()

    try:
        # 1. Fetch initial context
        current_leg, turnaround, telemetry = await aggregator.get_flight_context(
            flight_query
        )
        assessment = engine.assess_flight(
            current_leg=current_leg,
            turnaround=turnaround,
            flight_query=flight_query,
        )
        initial_payload = assessment.model_dump(mode="json")
        last_assessment_json = json.dumps(initial_payload, sort_keys=True)

        yield f"event: INITIAL\ndata: {json.dumps(initial_payload)}\n\n"

        # 2. Continuous event stream
        while True:
            # Check client disconnect
            if await request.is_disconnected():
                logger.info("SSE client disconnected for flight %s", flight_query)
                break

            await asyncio.sleep(poll_interval)

            now = asyncio.get_event_loop().time()

            # Heartbeat check
            if now - last_heartbeat_time >= heartbeat_interval:
                yield ": keep-alive\n\n"
                last_heartbeat_time = now

            # Fetch context update
            try:
                current_leg, turnaround, telemetry = await aggregator.get_flight_context(
                    flight_query
                )
                assessment = engine.assess_flight(
                    current_leg=current_leg,
                    turnaround=turnaround,
                    flight_query=flight_query,
                )
                current_payload = assessment.model_dump(mode="json")
                current_json = json.dumps(current_payload, sort_keys=True)

                if current_json != last_assessment_json:
                    last_assessment_json = current_json
                    yield f"event: UPDATE\ndata: {json.dumps(current_payload)}\n\n"
                else:
                    # Emitted heartbeat tick
                    tick_payload = {
                        "flight": f"{flight_query.carrier}{flight_query.flight_number}",
                        "timestamp": now,
                        "status": current_leg.status,
                        "earliest_departure": str(assessment.calculated_earliest_departure),
                    }
                    yield f"event: TICK\ndata: {json.dumps(tick_payload)}\n\n"
            except Exception as exc:
                logger.warning("Error fetching stream update for %s: %s", flight_query, exc)
                yield f": update-error: {exc}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE flight stream task cancelled for %s", flight_query)
        raise
    except Exception as exc:
        logger.error("SSE stream encountered fatal error: %s", exc)
        yield f"event: ERROR\ndata: {json.dumps({'error': str(exc)})}\n\n"


@router.get(
    "/{carrier}/{flight_num}/{date_str}/stream",
    summary="Stream Flight Reality Updates (SSE)",
    description="Subscribes to real-time Server-Sent Events (SSE) emitting initial assessment, periodic heartbeats, and updates.",
    response_class=StreamingResponse,
)
async def stream_flight_assessment(
    carrier: str,
    flight_num: str,
    date_str: str,
    request: Request,
    aggregator: FlightAggregator = Depends(get_flight_aggregator),
    engine: PredictionEngine = Depends(get_prediction_engine),
):
    try:
        flight_query = FlightQuery(
            carrier=carrier,
            flight_number=flight_num,
            departure_date=date.fromisoformat(date_str),
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed flight query: {exc}",
        )

    return StreamingResponse(
        flight_event_generator(
            flight_query=flight_query,
            aggregator=aggregator,
            engine=engine,
            request=request,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        },
    )
