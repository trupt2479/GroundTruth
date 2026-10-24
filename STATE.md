# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase3-api-delivery-sse`
- **Completed Tasks**:
  - `GT-P0-01` (Foundation, Monorepo Setup & Shared Domain Schemas)
  - `GT-P1-01` through `GT-P1-04` (Ingestion Adapters, Mock Fixtures, and Redis Cache-Aside)
  - `GT-P2-01` through `GT-P2-05` (Deterministic Delay, MTT Turnaround, and Equipment Swap Engine)
  - `GT-P3-01` (REST Flight Evaluation Endpoint)
  - `GT-P3-02` (Server-Sent Events Real-Time Streaming Endpoint)
  - `GT-P3-03` (Global Exception Handlers, CORS, and Integration Tests)
- **Status**: Completed / Verified

## Monorepo Architecture
GroundTruth is organized as a monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, external ingestion clients (`AeroDataBoxClient`, `OpenSkyClient`), caching service (`CacheService`), ingestion aggregator (`FlightAggregator`), math & heuristics engines (`TurnaroundEngine`, `SwapEvaluator`, `ActionEngine`, `PredictionEngine`), REST & SSE endpoints, and comprehensive test suites.
- `backend/app/fixtures/`: Realistic mock JSON fixtures enabling dual-mode execution without third-party rate limiting.
- `frontend/`: Placeholder structure for Phase 4 web UI.
- `docker-compose.yml`: Multi-container orchestrator running `backend` (FastAPI, port 8000), `redis` (cache, port 6379), and `postgres` (PostgreSQL 16, port 5432) with operational healthchecks.

## Phase 3 Implementation Details

### 1. REST Flight Evaluation Endpoint (`backend/app/api/v1/endpoints/flights.py`)
- `GET /api/v1/flights/evaluate`
- Accepts query parameters: `carrier` (2-char uppercase), `flight_num` (1-4 chars alphanumeric), `date` (YYYY-MM-DD).
- Validates inputs strictly via `FlightQuery`.
- Aggregates context via `FlightAggregator` (with Redis cache-aside) and runs `PredictionEngine.assess_flight()`.
- Standardized error mapping:
  - 422: Malformed query parameters.
  - 404: Flight not found.
  - 503: External flight telemetry APIs unavailable without cache.

### 2. Server-Sent Events (SSE) Delivery Endpoint (`backend/app/api/v1/endpoints/stream.py`)
- `GET /api/v1/flights/{carrier}/{flight_num}/{date}/stream`
- Protocol: `text/event-stream`.
- Emits:
  - Initial `event: INITIAL` with full `RealityAssessment` JSON payload.
  - Periodic keep-alive comment heartbeats (`: keep-alive\n\n`) every 15 seconds.
  - Delta updates (`event: UPDATE` / `event: TICK`) as flight turnaround state progresses.
- Clean cancellation and disconnect handling preventing background task leaks.

### 3. Global Exception Handling & CORS Configuration (`backend/app/main.py`)
- Uniform JSON error envelopes (`{"detail": "...", "error_code": "..."}`).
- CORS middleware configured for frontend ports (`http://localhost:3000`, `http://localhost:5173`).

## Test Verification
- All 28 unit and integration tests across `backend/tests/` pass with 100% pass rate:
  - `test_evaluate_flight_success` (PASSED)
  - `test_evaluate_flight_invalid_carrier_422` (PASSED)
  - `test_evaluate_flight_invalid_date_422` (PASSED)
  - `test_evaluate_flight_upstream_service_unavailable_503` (PASSED)
  - `test_sse_stream_initial_event_and_heartbeat` (PASSED)
  - Phase 2 Prediction Engine Tests (6 passed)
  - Phase 1 Ingestion and Redis Cache Tests (6 passed)
  - Phase 0 Schema and Health Check Tests (11 passed)

## Next Steps (Phase 4)
- Frontend client implementation (Next.js / React) consuming `/api/v1/flights/evaluate` and subscribing to SSE stream `/api/v1/flights/{carrier}/{flight_num}/{date}/stream`.
