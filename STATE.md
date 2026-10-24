# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `feat/phase2-crew-timeout-watchdog`
- **Completed Tasks**:
  - `GT-P0-01` through `GT-P5-04` (Phase 0 Foundation to Phase 5 Alpha MVP Integration)
  - `GT-ADV-01` (FAA NAS Status & Ground Delay Program Ingestion Engine)
  - `GT-ADV-02` (Automatic Alternative Flight Scout)
  - `GT-ADV-03` (Crew Duty Limit "Crew Timeout" Watchdog - FAA Part 117)
- **Status**: Completed / Verified

## Feature GT-ADV-03 Deliverables

### 1. Crew Duty Limit Watchdog Service (`backend/app/services/crew_duty_watchdog.py`)
- Implemented `CrewDutyWatchdog` service evaluating flight crew legal duty hours under FAA Part 117 guidelines:
  - Standard domestic maximum Flight Duty Period (FDP) buffer: 14 hours (840 minutes).
  - Crew report time calculated 60 minutes prior to first rotation departure.
  - Duty time accumulated across preceding rotation legs (`Leg n-2`, `Leg n-1`) and projected arrival of current leg.
  - Risk categorization:
    - `HIGH`: Remaining duty buffer < 60 minutes (imminent cancellation / crew illegal risk).
    - `MODERATE`: Remaining duty buffer between 60 and 120 minutes.
    - `LOW`: Remaining duty buffer > 120 minutes.

### 2. Domain Schema Extension (`backend/app/schemas/flight.py`)
- Added `CrewDutyAssessment` schema:
  - `elapsed_duty_minutes`: int
  - `remaining_buffer_minutes`: int
  - `timeout_risk`: Literal['LOW', 'MODERATE', 'HIGH']
  - `risk_summary`: str
- Extended `RealityAssessment` to include `crew_duty: Optional[CrewDutyAssessment] = None`.
- Exported `CrewDutyAssessment` from `backend/app/schemas/__init__.py`.

### 3. Prediction Engine Integration (`backend/app/services/prediction_engine.py`)
- Evaluates `CrewDutyWatchdog.assess_crew_duty()` on every flight evaluation.
- When `timeout_risk == 'HIGH'`:
  - Enforces `is_unavoidable_delay = True`.
  - Automatically escalates prescriptive directive to `rebooking_directive = 'EXPEDITE_REBOOKING'`.
  - Appends crew duty assessment to `RealityAssessment.crew_duty`.

### 4. Frontend Ground Reality Card Integration (`frontend/src/components/GroundRealityCard.tsx`)
- Extended `RealityAssessment` and added `CrewDutyAssessment` interface in `frontend/src/types/flight.ts`.
- Added **"FAA Part 117 Watchdog: Crew Timeout Warning"** alert banner with `data-testid="crew-duty-banner"`:
  - Displays prominent red/amber alert warning of high cancellation risk due to impending crew timeout.
  - Renders a real-time duty buffer pill showing remaining minutes until legal timeout.

## Test Verification Summary
1. **Crew Duty Watchdog Test Suite (`test_crew_watchdog.py`)**:
   - `test_crew_duty_calculation_across_rotations`: Validates duty accumulation across 2 prior rotation legs (PASSED).
   - `test_crew_timeout_high_risk_escalation`: Validates `timeout_risk == 'HIGH'` when remaining buffer < 60m and verifies `rebooking_directive == 'EXPEDITE_REBOOKING'` (PASSED).
   - `test_crew_duty_moderate_risk`: Validates `MODERATE` risk when buffer is 60-120m (PASSED).
2. **Full Backend Suite (`pytest -v backend/tests`)**:
   - 42 out of 42 tests passing cleanly in 1.11s.
3. **Frontend Vitest Suite (`npm test`)**:
   - 7 out of 7 tests passing in `src/test/components.test.tsx` (including crew timeout banner rendering and buffer verification).
4. **Production Build (`npm run build`)**:
   - Built cleanly with zero errors.
