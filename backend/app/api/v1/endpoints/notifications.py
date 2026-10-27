import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.notification import NotificationResponse, NotificationSubscription
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_notification_service() -> NotificationService:
    return NotificationService()


@router.post(
    "/subscribe",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to Flight Alerts",
    description="Registers an SMS phone number or Webhook endpoint for proactive real-time flight notifications.",
)
async def subscribe_to_alerts(
    subscription: NotificationSubscription,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationResponse:
    """Validate incoming subscription and persist in Redis."""
    try:
        success = await service.subscribe(subscription)
    except Exception as exc:
        logger.error("Error subscribing destination %s: %s", subscription.destination, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error processing notification subscription.",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist notification subscription in storage.",
        )

    return NotificationResponse(
        status="success",
        message=(
            f"Successfully subscribed {subscription.destination} to alerts for "
            f"{subscription.flight_carrier}{subscription.flight_number} on {subscription.flight_date}."
        ),
        subscription=subscription,
    )
