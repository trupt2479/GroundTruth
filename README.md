<div align="center">

# ✈️ GroundTruth
### Turnaround Physics vs. Airline Claims — Live Predictive Flight & Equipment Intelligence

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Tailwind-38bdf8?style=flat-square&logo=react)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Cache-Redis%207-dc382d?style=flat-square&logo=redis)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ed?style=flat-square&logo=docker)](https://www.docker.com/)

**Predict flight delays hours before gate agents announce them by tracking physical airframe rotations, minimum turnaround physics, FAA airspace advisories, and Part 117 crew duty limits.**

</div>

---

## 🎯 Why GroundTruth?

Airlines routinely display **"On Time"** on departure boards and mobile apps until minutes before boarding—even when the physical aircraft assigned to operate the flight is still thousands of miles away or stuck in a ground stop.

**GroundTruth** eliminates the information asymmetry by evaluating operational reality instead of published schedules:

1. **Physical Airframe & Turnaround Physics:** Tracks your booked flight's live callsign while isolating the incoming aircraft tail's prior leg, applying deterministic Minimum Turnaround Time (MTT) baselines (`35m` Regional, `45m` Narrowbody, `75m` Widebody).
2. **Hub vs. Outstation Spare Heuristics:** Distinguishes between fortress hubs (where dispatch can swap in a spare aircraft) and outstations (where `0` spares exist and an inbound delay guarantees an outbound push delay).
3. **FAA Airspace & Part 117 Watchdog:** Ingests live FAA National Airspace System (NAS) Ground Stops / Ground Delay Programs and monitors flight crew 14-hour legal duty ceilings.
4. **Airport-Local & Device Timezone Intelligence:** Renders milestones in origin/destination airport-local timezones (`PST`, `CST`, `EST`) with automatic `+1 day` overnight red-eye badges and a persistent `[ Airport Local | My Time ]` toggle.
5. **Quota-Conscious T-2h Persistent Watchlist:** Saves flights to a PostgreSQL-backed watchlist and automatically evaluates them once at the **T-2 hour decision window**—conserving free-tier API quotas while giving travelers early rebooking lead time.

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                        Browser / Traveler Dashboard                        │
│              React 18 + TypeScript + Tailwind + EventSource SSE            │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │ HTTP / SSE (Port 3000)
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       Nginx Reverse Proxy (Unbuffered)                     │
│             Serves Static SPA  │  Proxies /api/v1/* & SSE Streams          │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │ Port 8000
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend & Async Engine                       │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │
│  │  Flight Aggregator  │  │  Prediction Engine   │  │ Watchlist Worker  │  │
│  │ (Callsign + Tail)   │  │ (MTT, Swaps, Pt.117) │  │ (T-2h Auto-Check) │  │
│  └──────────┬──────────┘  └──────────┬───────────┘  └─────────┬─────────┘  │
└─────────────┼────────────────────────┼────────────────────────┼────────────┘
              │                        │                        │
     ┌────────┴────────┐      ┌────────┴────────┐      ┌────────┴────────┐
     ▼                 ▼      ▼                 ▼      ▼                 ▼
┌─────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────┐
│ Redis 7 │     │   AeroDataBox    │     │ OpenSky Network  │     │PostgreSQL│
│ (Cache) │     │ (Schedules/Tails)│     │ (Live ADS-B GPS) │     │(Volume)  │
└─────────┘     └──────────────────┘     └──────────────────┘     └──────────┘
                                                  │
                                                  ▼
                                         ┌──────────────────┐
                                         │  FAA NAS Status  │
                                         │ (Ground Stops)   │
                                         └──────────────────┘
```

---

## ✨ Key Features

| Module | Capability |
| :--- | :--- |
| **Booked-Flight Hero View** | Prioritizes your active flight callsign (e.g., `DAL783`, `SWA4772`) for live cruise altitude, airspeed, and transponder status while isolating incoming tail turns into a secondary diagnostic panel. |
| **Multi-Leg Route Filter** | Optional `Origin` and `Destination` IATA filters disambiguate carriers that reuse a single flight number across multiple daily hops. |
| **Dual-Mode Timezone Toggle** | Switch between **Airport Local** (origin departure TZ & destination arrival TZ with `+1 day` red-eye badges) and **My Time** (browser local TZ), persisted in `localStorage`. |
| **Persistent Watchlist & T-2h Worker** | Save flights to PostgreSQL (`postgres_data` named volume). A background `asyncio` scheduler monitors armed flights and runs a single evaluation at `Departure - 2 Hours`. |
| **Proactive Rebooking Scout** | Surfaces alternative flights on the same city pair alongside seat availability and standby recommendations whenever `EXPEDITE_REBOOKING` is triggered. |
| **Offline Scenario Simulator** | Built-in 1-click scenarios (`UA 1422`, `DL 450`, `AA 1200`, `DL 783`) and offline mode (`MOCK_INGESTION=true`) for zero-quota testing and demos. |

---

## 🚀 Quick Start (Docker Compose)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & Docker Compose v2+
- *(Optional)* A free [RapidAPI AeroDataBox](https://rapidapi.com/aedbx-aedbx/api/aerodatabox) key for live flight data (the app works out-of-the-box in offline mock mode without API keys).

### 1. Clone the Repository
```bash
git clone https://github.com/trupt2479/GroundTruth.git
cd GroundTruth
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Open `.env` and set your ingestion mode:
- **Offline Demo Mode (Default — Zero API Quota Used):**
  ```env
  MOCK_INGESTION=true
  ```
- **Live Flight Tracking Mode:**
  ```env
  MOCK_INGESTION=false
  AERODATABOX_API_KEY=your_rapidapi_key_here
  AERODATABOX_API_HOST=aerodatabox.p.rapidapi.com
  ```

### 3. Build and Launch All Services
```bash
docker compose up --build -d
```

Verify all 4 containers are healthy:
```bash
docker compose ps
```

### 4. Access the Application
- **Web Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Interactive API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 🔌 Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/flights/evaluate` | Evaluate turnaround physics, swap probability, crew duty, and telemetry (`?carrier=DL&flight_num=783&date=2026-11-18&origin=LAX&destination=ATL`). |
| `GET` | `/api/v1/flights/{carrier}/{flight_num}/{date}/stream` | Server-Sent Events (SSE) live stream for real-time assessment updates. |
| `POST` | `/api/v1/watchlist` | Enroll a flight into the persistent PostgreSQL watchlist and arm its T-2h milestone timer. |
| `GET` | `/api/v1/watchlist?user_name=Trupti` | Retrieve all monitored flights, countdown timers, and latest cached assessments. |
| `POST` | `/api/v1/watchlist/check-milestones` | Manually trigger an immediate evaluation check on any armed flights inside their T-2h window. |
| `DELETE` | `/api/v1/watchlist/{item_id}` | Remove a flight from active watchlist monitoring. |
| `POST` | `/api/v1/notifications/subscribe` | Subscribe an SMS or Webhook endpoint for unavoidable delay and crew timeout alerts. |

---

## 🧪 Running Automated Tests

### Backend Test Suite (Pytest)
```bash
docker compose exec backend pytest -v tests
```

### Frontend Test Suite (Vitest) & Production Build
```bash
cd frontend
npm install
npm test -- --run
npm run build
```

---

## 📁 Repository Structure

```text
GroundTruth/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # REST & SSE routers (flights, watchlist, stream, notifications)
│   │   ├── core/               # Config settings & database session management
│   │   ├── models/             # SQLAlchemy models (WatchlistItem)
│   │   ├── schemas/            # Pydantic v2 contracts (RealityAssessment, FlightQuery)
│   │   └── services/           # Ingestion clients, turnaround physics, timezone mapper, scheduler
│   └── tests/                  # Comprehensive backend unit & integration test suite
├── frontend/
│   ├── src/
│   │   ├── components/         # GroundRealityCard, InboundVisualizer, WatchlistDrawer, FlightSearch
│   │   ├── hooks/              # Zero-retry SSE streaming hook (useFlightStream)
│   │   └── types/              # TypeScript domain interfaces
│   └── nginx.conf              # Unbuffered SSE reverse-proxy configuration
├── docker-compose.yml          # Multi-container orchestration with named postgres_data volume
└── .env.example                # Documented environment variable template
```

---

## 🛡️ Data Persistence & Quota Safety
- **PostgreSQL Volume:** Saved watchlist items reside in the `postgres_data` Docker volume and persist across `docker compose down` and container rebuilds.
- **Manual-First Querying:** Searches only execute when explicitly triggered by the user or once at the T-2h milestone window—preventing background polling from exhausting free-tier API quotas.
