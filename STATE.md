# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `poc/phase5-mvp-integration`
- **Completed Tasks**:
  - `GT-P0-01` (Foundation, Monorepo Setup & Shared Domain Schemas)
  - `GT-P1-01` through `GT-P1-04` (Ingestion Adapters, Mock Fixtures, and Redis Cache-Aside)
  - `GT-P2-01` through `GT-P2-05` (Deterministic Delay, MTT Turnaround, and Equipment Swap Engine)
  - `GT-P3-01` through `GT-P3-03` (REST Flight Evaluation Endpoints & Server-Sent Events Delivery)
  - `GT-P4-01` through `GT-P4-04` (Mobile-First React PWA, Ground Reality Card, Tail Visualizer, and SSE Hook)
  - `GT-P5-01` & `GT-P5-02` (Unified Multi-Container Docker Compose Environment with Nginx Reverse Proxy)
  - `GT-P5-03` (End-to-End Alpha Integration Test Suite & Latency Benchmarks)
  - `GT-P5-04` (Repository Documentation & Alpha Sign-Off)
- **Status**: Completed / Verified (Alpha MVP Ready)

## Monorepo Architecture
GroundTruth is organized as a production-ready monorepo containing:
- `backend/`: FastAPI Python application with Pydantic v2 domain schemas, configuration management via `pydantic-settings`, external ingestion clients (`AeroDataBoxClient`, `OpenSkyClient`), caching service (`CacheService`), ingestion aggregator (`FlightAggregator`), math & heuristics engines (`TurnaroundEngine`, `SwapEvaluator`, `ActionEngine`, `PredictionEngine`), REST & SSE endpoints, and comprehensive unit/integration test suites (33 passed).
- `backend/app/fixtures/`: Realistic mock JSON fixtures enabling rate-limit-free dual-mode replay.
- `frontend/`: Lightweight, responsive React mobile PWA (TypeScript + Vite + Tailwind CSS) served via multi-stage Docker build with Nginx reverse proxy.
- `docker-compose.yml`: Multi-container orchestrator running all 4 services:
  1. `groundtruth-frontend` (Port 3000, Nginx reverse proxy routing `/api/` to backend)
  2. `groundtruth-backend` (Port 8000, FastAPI app with healthcheck)
  3. `groundtruth-redis` (Port 6379, in-memory cache)
  4. `groundtruth-postgres` (Port 5432, PostgreSQL 16 database)

## Verified Alpha Test Evidence
1. **Docker Compose Environment**:
   - All 4 services running in a healthy state via `docker compose up --build -d`.
2. **Backend Test Suite (Pytest)**:
   - 33 out of 33 tests passing cleanly across:
     - End-to-end integration flows & < 50ms latency benchmarks (`test_e2e_integration.py`)
     - REST API & Server-Sent Events delivery (`test_api_delivery.py`)
     - Ingestion clients, dual-mode replay, and cache-aside (`test_ingestion_cache.py`)
     - Turnaround physics & swap heuristics scenarios (`test_prediction_engine.py`)
     - Shared domain schemas & health check (`test_schemas.py`)
3. **Frontend Test Suite & Build (Vitest + Vite)**:
   - 4 out of 4 component unit tests passing.
   - Production Vite bundle generated cleanly with zero type errors.

## Phase 2 Roadmap
- Integration with live FAA Ground Delay Program (GDP) and Ground Stop feeds.
- Flight crew duty hour and legality limit estimators (FAR Part 117 limits).
- Push notification & SMS dispatch service (Twilio/Firebase Cloud Messaging).
