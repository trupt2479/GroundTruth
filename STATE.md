# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `feat/phase2-faa-airspace-gdp`
- **Completed Tasks**:
  - `GT-P0-01` through `GT-P5-04` (Phase 0 Foundation to Phase 5 Alpha MVP Integration)
  - `GT-ADV-01` (FAA NAS Status & Ground Delay Program Ingestion Engine)
- **Status**: Completed / Verified

## Feature GT-ADV-01 Deliverables

### 1. FAA NAS Data Client (`backend/app/services/faa_nas_client.py`)
- Async client querying the FAA NAS status API (`https://nasstatus.faa.gov/api/airport-status-information`) with timeout and rate-limit guardrails.
- Supports dual-mode execution (`settings.MOCK_INGESTION == True`) reading from local XML fixture `backend/app/fixtures/sample_faa_nas_status.xml`.
- Implements `get_airport_airspace_status(airport_iata: str)` parsing:
  - `status_type`: `GROUND_STOP` | `GROUND_DELAY_PROGRAM` | `DEICING` | `NORMAL`
  - `reason`: e.g. `THUNDERSTORMS`, `LOW CEILINGS`, `SNOW/ICE`
  - `avg_delay_minutes`: Average delay in minutes
  - `end_time_utc`: Advisory end timestamp
  - `advisory_active`: Boolean status

### 2. Domain Schema Extension (`backend/app/schemas/flight.py`)
- Added `AirspaceAdvisory` schema matching FAA operational taxonomy.
- Extended `RealityAssessment` to include optional `airspace_advisory: Optional[AirspaceAdvisory] = None`.

### 3. Prediction Engine Integration (`backend/app/services/prediction_engine.py`)
- Evaluates active airspace programs for origin airport:
  - `GROUND_STOP`: Forces `is_unavoidable_delay = True`, injects ground stop duration, and escalates directive to `EXPEDITE_REBOOKING`.
  - `GROUND_DELAY_PROGRAM`: Injects average program delay into calculated earliest possible departure if greater than physical turnaround limit.

### 4. Frontend Alert Banner (`frontend/src/components/GroundRealityCard.tsx`)
- High-visibility airspace alert banner displayed whenever an active `airspace_advisory` is detected on a queried flight.
- Distinct color grading: Rose/Red for `GROUND_STOP`, Amber/Yellow for `GROUND_DELAY_PROGRAM`.

## Test Verification Summary
1. **FAA NAS Test Suite (`test_faa_nas.py`)**:
   - `test_faa_nas_mock_fixture_parsing`: Validates parsing of Ground Stop (ORD), GDP (EWR), and Normal (SFO) entries (PASSED).
   - `test_prediction_engine_ground_stop_escalation`: Confirms Ground Stop forces `is_unavoidable_delay = True` and `EXPEDITE_REBOOKING` (PASSED).
   - `test_prediction_engine_ground_delay_program_injection`: Confirms GDP delay injection into earliest departure (PASSED).
2. **Full Backend Suite (`pytest -v backend/tests`)**:
   - 36 passed in 33.48s.
3. **Frontend Vitest Suite (`npm test`)**:
   - 5 passed in `src/test/components.test.tsx` including active Ground Stop banner rendering.
