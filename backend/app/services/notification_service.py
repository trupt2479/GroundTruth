import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.schemas.flight import RealityAssessment
from app.schemas.notification import NotificationSubscription
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

SUBSCRIPTION_TTL_SECONDS = 86400  # 24 hours


class NotificationService:
    """Proactive SMS and Webhook push notification dispatch service."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache = cache_service or CacheService()

    def _get_subscription_key(self, carrier: str, flight_num: str, date: str) -> str:
        c = carrier.strip().upper()
        f = flight_num.strip().upper()
        d = date.strip()
        return f"subscriptions:{c}_{f}_{d}"

    async def subscribe(self, subscription: NotificationSubscription) -> bool:
        """Persist a new subscriber for a flight in Redis with a 24-hour TTL."""
        key = self._get_subscription_key(
            subscription.flight_carrier,
            subscription.flight_number,
            subscription.flight_date,
        )

        existing = await self.cache.get_json(key)
        if not isinstance(existing, list):
            subscribers_list: List[Dict[str, Any]] = []
        else:
            subscribers_list = existing

        # Avoid duplicate subscriptions for identical destination and channel
        sub_dict = subscription.model_dump()
        duplicate = False
        for s in subscribers_list:
            if (
                s.get("recipient_type") == subscription.recipient_type
                and s.get("destination") == subscription.destination
            ):
                duplicate = True
                break

        if not duplicate:
            subscribers_list.append(sub_dict)

        success = await self.cache.set_json(
            key, subscribers_list, ttl_seconds=SUBSCRIPTION_TTL_SECONDS
        )
        logger.info(
            "Subscribed %s to %s%s on %s (result: %s)",
            subscription.destination,
            subscription.flight_carrier,
            subscription.flight_number,
            subscription.flight_date,
            success,
        )
        return success

    async def get_subscribers(
        self, carrier: str, flight_num: str, date: str
    ) -> List[NotificationSubscription]:
        """Retrieve all active subscriptions for a given flight."""
        key = self._get_subscription_key(carrier, flight_num, date)
        raw_list = await self.cache.get_json(key)
        if not isinstance(raw_list, list):
            return []

        subscribers: List[NotificationSubscription] = []
        for item in raw_list:
            try:
                subscribers.append(NotificationSubscription.model_validate(item))
            except Exception as exc:
                logger.warning("Invalid subscriber record skipped: %s (error: %s)", item, exc)
        return subscribers

    def format_alert_message(self, assessment: RealityAssessment) -> str:
        """Format the standardized user-facing alert message."""
        carrier = assessment.flight_query.carrier
        flight_num = assessment.flight_query.flight_number
        flight_date = str(assessment.flight_query.departure_date)
        delay_lead_time = assessment.delay_lead_time_minutes
        directive = assessment.rebooking_directive

        return (
            f"⚠️ GroundTruth Alert: {carrier}{flight_num} on {flight_date} has a confirmed "
            f"{delay_lead_time}m physical delay. Rebooking directive: {directive}. "
            f"Action: Check alternative flights."
        )

    async def dispatch_assessment_alerts(self, assessment: RealityAssessment) -> int:
        """Dispatch real-time SMS and Webhook notifications to registered subscribers."""
        carrier = assessment.flight_query.carrier
        flight_num = assessment.flight_query.flight_number
        flight_date = str(assessment.flight_query.departure_date)

        subscribers = await self.get_subscribers(carrier, flight_num, flight_date)
        if not subscribers:
            logger.info("No subscribers registered for %s%s on %s", carrier, flight_num, flight_date)
            return 0

        dispatched_count = 0
        formatted_message = self.format_alert_message(assessment)

        for sub in subscribers:
            # Check alert preferences
            should_alert = False
            if sub.alert_on_delay and (assessment.is_unavoidable_delay or assessment.delay_lead_time_minutes > 0):
                should_alert = True
            elif sub.alert_on_crew_timeout and assessment.crew_duty and assessment.crew_duty.timeout_risk in ["HIGH", "MODERATE"]:
                should_alert = True
            elif sub.alert_on_swap and assessment.swap_evaluation and assessment.swap_evaluation.swap_probability in ["HIGH", "MODERATE", "NEAR_ZERO"]:
                should_alert = True

            if not should_alert:
                continue

            if sub.recipient_type == "SMS":
                # Check live Twilio provider credentials
                has_twilio = (
                    not settings.MOCK_INGESTION
                    and bool(settings.TWILIO_ACCOUNT_SID)
                    and bool(settings.TWILIO_AUTH_TOKEN)
                    and bool(settings.TWILIO_PHONE_NUMBER)
                )

                if has_twilio:
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as http_client:
                            twilio_url = (
                                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
                            )
                            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                            data = {
                                "From": settings.TWILIO_PHONE_NUMBER,
                                "To": sub.destination,
                                "Body": formatted_message,
                            }
                            resp = await http_client.post(twilio_url, auth=auth, data=data)
                            if resp.status_code in [200, 201]:
                                logger.info("Live Twilio SMS dispatched to %s", sub.destination)
                                dispatched_count += 1
                            else:
                                logger.warning("Twilio SMS failed with status %s: %s", resp.status_code, resp.text)
                    except Exception as exc:
                        logger.error("Failed to dispatch Twilio SMS to %s: %s", sub.destination, exc)
                else:
                    # Mock SMS dispatch via standard logging
                    logger.info("[MOCK SMS to %s]: %s", sub.destination, formatted_message)
                    dispatched_count += 1

            elif sub.recipient_type == "WEBHOOK":
                # Asynchronously POST JSON payload of RealityAssessment to subscriber's endpoint
                try:
                    payload = assessment.model_dump(mode="json")
                    async with httpx.AsyncClient(timeout=3.0) as http_client:
                        await http_client.post(
                            sub.destination,
                            json=payload,
                            headers={"Content-Type": "application/json", "User-Agent": "GroundTruth-Alert-Dispatcher/1.0"},
                        )
                        logger.info("Webhook alert dispatched to %s", sub.destination)
                        dispatched_count += 1
                except Exception as exc:
                    logger.warning("Webhook dispatch suppressed error for %s: %s", sub.destination, exc)

        return dispatched_count
