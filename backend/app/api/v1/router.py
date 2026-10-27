from fastapi import APIRouter
from app.api.v1.endpoints import flights, health, notifications, stream

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(flights.router, prefix="/flights", tags=["Flights"])
api_router.include_router(stream.router, prefix="/flights", tags=["Flight Stream"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
