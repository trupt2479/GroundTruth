# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase1-ingestion-cache`
- **Completed Tasks**:
  - `GT-P0-01` (Foundation, Monorepo Setup & Shared Domain Schemas)
  - `GT-P1-01` (AeroDataBox Ingestion Client)
  - `GT-P1-02` (OpenSky Network Telemetry Client)
  - `GT-P1-03` (Async Redis Cache Service with TTL Policies)
  - `GT-P1-04` (Ingestion Aggregator & Rotation Tracker with Cache-Aside)
- **Status**: Completed / Verified

## Monorepo Architecture
GroundTruth is organized as a monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, external ingestion clients (`AeroDataBoxClient`, `OpenSkyClient`), caching service (`CacheService`), ingestion aggregator (`FlightAggregator`), and test suites.
- `backend/app/fixtures/`: Realistic mock JSON fixtures (`sample_aerodatabox_flight.json`, `sample_aerodatabox_rotations.json`, `sample_opensky_state.json`) enabling rate-limit-free dual-mode replay.
- `frontend/`: Placeholder structure for Phase 4 web UI.
- `docker-compose.yml`: Multi-container orchestrator running `backend` (FastAPI, port 8000), `redis` (cache, port 6379), and `postgres` (PostgreSQL 16, port 5432) with operational healthchecks.

## Phase 1 Implementation Details

### 1. AeroDataBox Ingestion Client (`backend/app/services/aerodatabox_client.py`)
- Communicates with RapidAPI AeroDataBox API using `httpx.AsyncClient` with configurable timeout and dual-mode execution (`MOCK_INGESTION=True` fixture fallback).
- Implements `get_flight_status(carrier, flight_num, date)` and `get_inbound_rotations(tail_number, date)` returning `list[FlightLeg]`.
- Handles HTTP 429 (`AeroDataBoxRateLimitError`) and HTTP 503 (`AeroDataBoxServiceUnavailableError`).

### 2. OpenSky Network Client (`backend/app/services/opensky_client.py`)
- Async `httpx.AsyncClient` querying OpenSky REST API with dual-mode mock fallback (`sample_opensky_state.json`).
- `get_aircraft_state(icao24_or_callsign)` returns live state vectors including callsign, barometric altitude (ft), ground speed (kts), on-ground status, and coordinates.

### 3. Redis Cache Service (`backend/app/services/cache_service.py`)
- Async connection pool using `redis.asyncio` with JSON serialization.
- Explicit TTL policies enforced:
  - Flight aggregate / evaluation: `flight:{carrier}_{flight_num}_{date}` -> **TTL = 120 seconds**
  - Live airframe/transponder state: `tail:{tail_number}:state` -> **TTL = 60 seconds**
- Standard operations: `get_json`, `set_json`, `delete`, and `ping` health checks.

### 4. Ingestion Aggregator & Rotation Tracker (`backend/app/services/flight_aggregator.py`)
- Orchestrates `get_flight_context(query: FlightQuery) -> tuple[FlightLeg, InboundTurnaround, dict | None]`.
- Implements the **Cache-Aside Pattern**:
  - Checks Redis cache key `flight:{carrier}_{flight_number}_{departure_date}`.
  - On Cache Hit: returns deserialized domain models directly.
  - On Cache Miss: queries AeroDataBox for flight details, extracts tail and prior legs, queries OpenSky for live transponder state, categorizes aircraft (MTT: 35m regional, 45m narrowbody, 75m widebody), calculates estimated touchdown and earliest departure, writes aggregate to Redis (TTL 120s), and returns context.

## Test Verification
- All 17 unit and integration tests across `backend/tests/` pass with 100% pass rate:
  - `test_redis_cache_set_and_get` (PASSED)
  - `test_redis_cache_expiration` (PASSED)
  - `test_aerodatabox_mock_replay` (PASSED)
  - `test_opensky_mock_replay` (PASSED)
  - `test_aggregator_cache_aside_flow` (PASSED)
  - `test_aerodatabox_error_handling` (PASSED)
  - 11 Phase 0 domain schema and health check unit tests (PASSED)

## Next Steps (Phase 2)
- Implement Turnaround Feasibility Engine & Delay Lead-Time Calculator.
- Implement Hub Heuristic & Tail Swap Probability Evaluator.
- Generate full `RealityAssessment` domain payloads.
