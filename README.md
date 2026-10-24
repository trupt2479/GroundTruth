# GroundTruth: Real-Time Flight Turnaround Intelligence Engine

GroundTruth is a mobile-first flight turnaround reality evaluation engine that calculates true minimum turnaround time (MTT) limits and detects unannounced airline delays before they appear on airport departure boards.

---

## Architecture Overview

```
                      +-----------------------------------+
                      |      Mobile-First React PWA       |
                      |   (Vite + TypeScript + Tailwind)  |
                      |            Port: 3000             |
                      +-----------------+-----------------+
                                        |  REST / SSE Stream
                                        v
                      +-----------------+-----------------+
                      |         FastAPI Gateway           |
                      |   (Python 3.12 / Pydantic v2)     |
                      |            Port: 8000             |
                      +--------+-----------------+--------+
                               |                 |
                   Cache-Aside |                 | Evaluation
                               v                 v
            +------------------+----+   +--------+------------------+
            |  Redis 7 (Port 6379)  |   | Prediction & MTT Engine   |
            |   Aggregate: 120s TTL |   | Turnaround Matrix: 35/45/75|
            |   Live State: 60s TTL |   | Fortress Hub Evaluator    |
            +-----------------------+   +---------------------------+
                               |                 |
                               +--------+--------+
                                        v
                               +-----------------+
                               | Postgres 16 DB  |
                               |   (Port 5432)   |
                               +-----------------+
```

---

## Key Features

1. **Deterministic Minimum Turnaround Time (MTT) Calculation**:
   - `REGIONAL` (e.g. E175, CRJ9): 35 minutes
   - `NARROWBODY` (e.g. A320, B738, A220): 45 minutes
   - `WIDEBODY` (e.g. B777, B787, A350): 75 minutes
   - Computes unavoidable physical delay: `Earliest Departure = Actual Inbound Touchdown + MTT Buffer`.

2. **Hub vs. Outstation Tail-Swap Heuristic**:
   - Detects whether the departure airport is a Fortress Hub (e.g. `ATL`, `ORD`, `DFW`, `DEN`) with spare tail reserves or an Outstation (`BDL`, `IND`) where swap likelihood is `NEAR_ZERO`.

3. **Prescriptive Traveler Action Guidance**:
   - `RELAX_IN_LOUNGE`: Physical turn buffer is fully intact.
   - `MONITOR_CLOSELY`: Tight turnaround detected; monitor gate closely.
   - `EXPEDITE_REBOOKING`: Unavoidable outstation delay or guaranteed downstream connection break; rebook immediately before seats vanish.

4. **Real-Time Server-Sent Events (SSE)**:
   - High-efficiency `text/event-stream` delivering initial assessment and dynamic delta ticks directly to the mobile UI.

---

## One-Line Docker Compose Setup

Run all 4 services (`frontend`, `backend`, `redis`, `postgres`) with a single command:

```bash
docker compose up --build -d
```

Check service health:

```bash
docker compose ps
```

- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **Backend API & Swagger Docs**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health Check**: `curl http://localhost:8000/health`

---

## API Specifications

### 1. Flight Reality Evaluation
- **Endpoint**: `GET /api/v1/flights/evaluate`
- **Query Parameters**:
  - `carrier`: 2-letter uppercase IATA code (e.g. `UA`, `DL`)
  - `flight_num`: 1 to 4 alphanumeric characters (e.g. `1422`)
  - `date`: Departure date in `YYYY-MM-DD` format
- **Response**:
  ```json
  {
    "flight_query": {
      "carrier": "UA",
      "flight_number": "1422",
      "departure_date": "2026-10-24"
    },
    "official_airline_departure": "2026-10-24T18:30:00Z",
    "calculated_earliest_departure": "2026-10-24T19:15:00Z",
    "delay_lead_time_minutes": 45,
    "is_unavoidable_delay": true,
    "swap_evaluation": {
      "origin_is_hub": false,
      "hub_type": "OUTSTATION",
      "swap_probability": "NEAR_ZERO"
    },
    "rebooking_directive": "EXPEDITE_REBOOKING"
  }
  ```

### 2. Real-Time Flight Event Stream (SSE)
- **Endpoint**: `GET /api/v1/flights/{carrier}/{flight_num}/{date}/stream`
- **MIME Type**: `text/event-stream`
- **Event Types**:
  - `event: INITIAL`: Full initial `RealityAssessment` JSON payload.
  - `: keep-alive`: Periodic heartbeat comment every 15s.
  - `event: TICK` / `event: UPDATE`: Status and telemetry deltas.

---

## Development & Test Guide

### Backend Tests (Python / Pytest)
```bash
# Run all 33 unit, engine, API, and E2E integration tests
pytest -v backend/tests
```

### Frontend Tests & Production Build (Node / Vitest)
```bash
cd frontend
npm install

# Run Vitest component tests
npm test

# Run TypeScript check & Vite production build
npm run build
```
