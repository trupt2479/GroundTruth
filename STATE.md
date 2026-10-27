# GroundTruth Architecture & State Log

## Active State
- **Current Branch**: `feat/phase2-push-dispatch`
- **Completed Tasks**:
  - `GT-P0-01` through `GT-P5-04` (Phase 0 Foundation to Phase 5 Alpha MVP Integration)
  - `GT-ADV-01` (FAA NAS Status & Ground Delay Program Ingestion Engine)
  - `GT-ADV-02` (Automatic Alternative Flight Scout)
  - `GT-ADV-03` (Crew Duty Limit "Crew Timeout" Watchdog - FAA Part 117)
  - `GT-ADV-04` (Proactive SMS & Webhook Push Notification Dispatch)
- **Status**: Completed / Verified

## Feature GT-ADV-04 Deliverables

### 1. Subscription Domain Model (`backend/app/schemas/notification.py`)
- Defined `NotificationSubscription`:
  - `flight_carrier`: 2-letter uppercase IATA code.
  - `flight_number`: 1-4 alphanumeric characters.
  - `flight_date`: YYYY-MM-DD date string.
  - `recipient_type`: 'SMS' | 'WEBHOOK'.
  - `destination`: Validated E.164 phone number (`+1...`) or HTTP/HTTPS webhook URL.
  - Granular triggers: `alert_on_delay`, `alert_on_crew_timeout`, `alert_on_swap`.
- Defined `NotificationResponse`: `status`, `message`, `subscription`.
- Cleanly exported in `backend/app/schemas/__init__.py`.

### 2. Push Notification & Dispatch Service (`backend/app/services/notification_service.py`)
- Redis-backed subscription storage using key convention `subscriptions:{carrier}_{flight_num}_{date}` with a 24-hour TTL (86400s).
- Implemented:
  - `subscribe(subscription: NotificationSubscription) -> bool`: Deduplicates and appends subscription records.
  - `get_subscribers(carrier, flight_num, date) -> list[NotificationSubscription]`: Fetches active subscriptions.
  - `dispatch_assessment_alerts(assessment: RealityAssessment) -> int`:
    - Evaluates triggers against turnaround delay, crew timeout risk, or tail swap.
    - Dual-mode SMS: Dispatches via Twilio when configured; falls back to formatted mock logging (`[MOCK SMS to %s]: %s`).
    - Webhook: Asynchronously POSTs JSON payload of `RealityAssessment` with a 3.0s timeout and error suppression.

### 3. REST API Endpoint (`backend/app/api/v1/endpoints/notifications.py`)
- Registered `POST /api/v1/notifications/subscribe` returning HTTP 201 Created and `NotificationResponse`.
- Integrated into `api_router` in `backend/app/api/v1/router.py`.

### 4. Configuration & Security (.env.example ONLY)
- Appended placeholder variables `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` to `.env.example`.
- Confirmed zero modification or access to `.env`.

### 5. Frontend Notification Modal (`frontend/src/components/NotificationModal.tsx`)
- Trigger button "Get Real-Time Alerts" integrated on `GroundRealityCard.tsx`.
- Modal with SMS vs Webhook tab toggle, client-side E.164 and URL validation, trigger checkboxes, and success confirmation banner.

## Test Verification Summary
1. **Notifications Test Suite (`test_notifications.py`)**:
   - `test_subscription_redis_persistence`: Redis store & fetch verification (PASSED).
   - `test_dispatch_mock_sms_on_unavoidable_delay`: Formatted mock SMS dispatch logging (PASSED).
   - `test_dispatch_webhook_payload`: Mock HTTP POST payload delivery (PASSED).
   - `test_api_subscribe_endpoint_success`: 201 Created endpoint assertion (PASSED).
   - `test_api_subscribe_endpoint_validation_errors`: 422 Unprocessable Entity assertions (PASSED).
2. **Full Backend Suite (`pytest -v backend/tests`)**:
   - 47 out of 47 tests passing cleanly in 1.27s.
3. **Frontend Vitest Suite (`npm test`)**:
   - 8 out of 8 tests passing in `src/test/components.test.tsx` (including modal opening, validation, and subscription flow).
4. **Production Build (`npm run build`)**:
   - Built cleanly with zero errors.
5. **Git Security Audit**:
   - Verified `.env` untouched; only `.env.example` updated.
