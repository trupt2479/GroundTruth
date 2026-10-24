# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase2-heuristic-mtt-engine`
- **Completed Tasks**:
  - `GT-P0-01` (Foundation, Monorepo Setup & Shared Domain Schemas)
  - `GT-P1-01` through `GT-P1-04` (Ingestion Adapters, Mock Fixtures, and Redis Cache-Aside)
  - `GT-P2-01` (Minimum Turnaround Time Engine)
  - `GT-P2-02` (Hub vs. Outstation Equipment Swap Evaluator)
  - `GT-P2-03` (Layover Compression & Action Engine)
  - `GT-P2-04` (Prediction Engine Orchestrator)
  - `GT-P2-05` (Deterministic Delay Engine Tests)
- **Status**: Completed / Verified

## Monorepo Architecture
GroundTruth is organized as a monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, external ingestion clients (`AeroDataBoxClient`, `OpenSkyClient`), caching service (`CacheService`), ingestion aggregator (`FlightAggregator`), math & heuristics engines (`TurnaroundEngine`, `SwapEvaluator`, `ActionEngine`, `PredictionEngine`), and comprehensive test suites.
- `backend/app/fixtures/`: Realistic mock JSON fixtures enabling dual-mode execution without third-party rate limiting.
- `frontend/`: Placeholder structure for Phase 4 web UI.
- `docker-compose.yml`: Multi-container orchestrator running `backend` (FastAPI, port 8000), `redis` (cache, port 6379), and `postgres` (PostgreSQL 16, port 5432) with operational healthchecks.

## Phase 2 Implementation Details

### 1. Minimum Turnaround Time (MTT) Engine (`backend/app/services/turnaround_engine.py`)
- Fleet turn buffer matrix lookup:
  - `REGIONAL` (e.g. E175, CRJ9): 35 minutes
  - `NARROWBODY` (e.g. A320, B738, A220): 45 minutes
  - `WIDEBODY` (e.g. B777, B787, A350): 75 minutes
- Calculates physical earliest departure: `Earliest Possible Departure = Inbound Actual Touchdown + MTT Buffer`.
- Flags unavoidable physical delay when `Earliest Possible Departure > Scheduled Departure`, computing `Delay Lead Time Delta`.

### 2. Hub vs Outstation Swap Evaluator (`backend/app/services/swap_evaluator.py`)
- Hub database tracking Fortress Hubs (`ATL`, `ORD`, `DFW`, `DEN`, `CLT`, `IAH`, `DTW`, `MSP`, `EWR`, `SFO`) vs Outstations.
- Evaluates swap probability based on spare fleet capacity:
  - Outstation with delay > 30 mins: `NEAR_ZERO`
  - Fortress Hub with delay > 45 mins: `HIGH`
  - Fortress Hub with delay > 15 mins: `MODERATE`
  - On-time / minor buffer: `LOW`

### 3. Layover Compression & Prescriptive Action Engine (`backend/app/services/action_engine.py`)
- Compares delay lead time against downstream connection layover and Minimum Connection Time (MCT = 40 min).
- Emits prescriptive directives:
  - `RELAX_IN_LOUNGE`: On-time or minor delay with intact buffer.
  - `MONITOR_CLOSELY`: Tightening turnaround/connection with feasible hub swap.
  - `EXPEDITE_REBOOKING`: Inbound delayed at outstation with guaranteed misconnection; proceed to agent immediately.

### 4. Engine Orchestrator (`backend/app/services/prediction_engine.py`)
- Unifies `TurnaroundEngine`, `SwapEvaluator`, and `ActionEngine`.
- Accepts `FlightLeg` and `InboundTurnaround` to emit a complete `RealityAssessment` domain contract.

## Test Verification
- All 23 unit and scenario tests pass cleanly across `backend/tests/`:
  - `Scenario A (Outstation Trap)`: B738 inbound to BDL delayed 90 mins -> Unavoidable delay = True, Swap = NEAR_ZERO, Directive = EXPEDITE_REBOOKING (PASSED)
  - `Scenario B (Hub Spare Feasible)`: A320 inbound to ATL delayed 60 mins -> Unavoidable delay = True, Origin = FORTRESS_HUB, Swap = HIGH, Directive = MONITOR_CLOSELY (PASSED)
  - `Scenario C (On-Time Narrowbody)`: Inbound touches down on schedule -> Unavoidable delay = False, Directive = RELAX_IN_LOUNGE (PASSED)
  - Fleet buffer matrix lookup (PASSED)
  - Hub and outstation swap probabilities (PASSED)
  - Downstream layover compression logic (PASSED)
  - Ingestion and caching tests (6 passed)
  - Pydantic schema validation tests (11 passed)

## Next Steps (Phase 3)
- API endpoint integration: Expose `POST /api/v1/assess` and `GET /api/v1/flights/{carrier}/{flight_number}`.
- Real-time notification worker and subscription alerts.
