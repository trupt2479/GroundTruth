# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase0-foundation-contracts`
- **Task ID**: `GT-P0-01`
- **Status**: Completed / Verified

## Monorepo Architecture
GroundTruth is organized as a monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, test suites, and Docker container definition.
- `frontend/`: Placeholder structure for Phase 4 web UI.
- `docker-compose.yml`: Multi-container orchestrator running `backend` (FastAPI, port 8000), `redis` (cache, port 6379), and `postgres` (PostgreSQL 16, port 5432) with operational healthchecks.

## Implemented Schemas (`backend/app/schemas/flight.py`)
- `FlightQuery`: Strict validations for 2-letter uppercase IATA carrier, 1-4 char alphanumeric flight number, and `YYYY-MM-DD` departure date.
- `AircraftInfo`: Tail number, ICAO aircraft type, and aircraft category (`REGIONAL`, `NARROWBODY`, `WIDEBODY`).
- `FlightLeg`: Rotational flight legs tracking origin IATA, destination IATA, scheduled/actual departure and arrival datetimes, and operational status.
- `InboundTurnaround`: Historical rotation legs (constrained to max 2 legs), assigned physical aircraft, categorized minimum turnaround time (MTT: 35m regional, 45m narrowbody, 75m widebody), estimated touchdown, and calculated earliest departure.
- `SwapHeuristic`: Hub detection (`FORTRESS_HUB` vs `OUTSTATION`), hub origin flag, and tail-swap probability assessment (`HIGH`, `MODERATE`, `LOW`, `NEAR_ZERO`).
- `RealityAssessment`: Complete domain assessment contrasting airline-claimed departure against physics-based minimum turnaround departure, computed delay lead time, unavoidability flag, swap feasibility, and actionable traveler rebooking directives (`RELAX_IN_LOUNGE`, `MONITOR_CLOSELY`, `EXPEDITE_REBOOKING`).

## Test Verification
- All 11 unit tests in `backend/tests/test_schemas.py` pass:
  - Carrier uppercase format enforcement & length constraints
  - Alphanumeric flight number length constraints
  - ISO date parsing and validation
  - Aircraft category literal bounds
  - MTT literal values (`35`, `45`, `75`) and leg count limits (`max_length=2`)
  - Swap heuristic literals
  - Full bidirectional JSON serialization/deserialization for `RealityAssessment`
  - Health check endpoint (`GET /health`) returning `{"status": "ok", "environment": "development"}`

## Next Steps (Phase 1)
- Implement external flight data ingestion adapters (AeroDataBox / FlightAware / Flightradar24).
- Implement Redis cache for live flight leg tracking and aircraft tail rotations.
- Implement Turnaround Engine service calculating physical earliest departure based on touchdown + MTT.
