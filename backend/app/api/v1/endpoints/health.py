from typing import Dict
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint returning system status and current environment."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
    }
