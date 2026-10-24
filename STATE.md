# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase4-mobile-pwa`
- **Completed Tasks**:
  - `GT-P0-01` (Foundation, Monorepo Setup & Shared Domain Schemas)
  - `GT-P1-01` through `GT-P1-04` (Ingestion Adapters, Mock Fixtures, and Redis Cache-Aside)
  - `GT-P2-01` through `GT-P2-05` (Deterministic Delay, MTT Turnaround, and Equipment Swap Engine)
  - `GT-P3-01` through `GT-P3-03` (REST Flight Evaluation Endpoints & Server-Sent Events Delivery)
  - `GT-P4-01` (Flight Search & Client-Side Validation)
  - `GT-P4-02` (Ground Reality Assessment Dashboard Card)
  - `GT-P4-03` (Inbound Tail Visualizer & MTT Buffer Countdown)
  - `GT-P4-04` (Real-Time SSE Stream Hook with Auto-Reconnection)
- **Status**: Completed / Verified

## Monorepo Architecture
GroundTruth is organized as a monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, external ingestion clients (`AeroDataBoxClient`, `OpenSkyClient`), caching service (`CacheService`), ingestion aggregator (`FlightAggregator`), math & heuristics engines (`TurnaroundEngine`, `SwapEvaluator`, `ActionEngine`, `PredictionEngine`), REST & SSE endpoints, and comprehensive test suites.
- `backend/app/fixtures/`: Realistic mock JSON fixtures enabling dual-mode execution without third-party rate limiting.
- `frontend/`: Lightweight, responsive React mobile PWA (TypeScript + Vite + Tailwind CSS) providing:
  - `FlightSearch`: Form with instant client-side input validation and auto-uppercase.
  - `GroundRealityCard`: Highlighting early warning lead time delta (`+X min ahead`), side-by-side departure times, and prescriptive action banners.
  - `InboundVisualizer`: Physical incoming aircraft tail number, category, live transponder altitude/speed, and upstream delay propagation.
  - `useFlightStream`: Custom hook maintaining an EventSource SSE connection with exponential backoff auto-reconnection.
- `docker-compose.yml`: Multi-container orchestrator running `backend` (FastAPI, port 8000), `redis` (cache, port 6379), and `postgres` (PostgreSQL 16, port 5432) with operational healthchecks.

## Test Verification Summary
1. **Frontend Tests (Vitest)**:
   - `4 passed` in `src/test/components.test.tsx` (validation, onSearch invocation, Ground Reality Card badge and banner rendering).
2. **Frontend Build (Vite + TypeScript)**:
   - `tsc -b && vite build` succeeded cleanly with zero warnings/errors.
3. **Backend Full Test Suite (Pytest)**:
   - `28 passed` across API delivery, ingestion caching, turnaround prediction engine, and domain schemas.
