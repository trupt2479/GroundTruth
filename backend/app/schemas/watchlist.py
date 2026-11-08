from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    user_name: str = Field(default="Trupti", description="User watchlist owner identifier")
    carrier: str = Field(..., description="2-letter uppercase carrier code, e.g., 'DL'")
    flight_number: str = Field(..., description="Flight number, e.g., '565'")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")


class WatchlistResponse(BaseModel):
    id: uuid.UUID | str
    user_name: str
    carrier: str
    flight_number: str
    departure_date: str
    origin_iata: str
    destination_iata: str
    origin_name: Optional[str] = None
    destination_name: Optional[str] = None
    scheduled_departure: Optional[datetime] = None
    t2_scheduled_fetch: Optional[datetime] = None
    status: str
    latest_assessment: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MilestoneCheckResponse(BaseModel):
    evaluated_count: int
    items_evaluated: list[str] = Field(default_factory=list)
    alerts_dispatched: int = 0
    checked_count: Optional[int] = None
    items: list[WatchlistResponse] = Field(default_factory=list)
