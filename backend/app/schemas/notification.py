from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class NotificationSubscription(BaseModel):
    """Schema representing a user's subscription for real-time proactive flight alerts."""

    flight_carrier: str = Field(
        ...,
        pattern=r"^[A-Z]{2}$",
        description="2-letter uppercase IATA carrier code (e.g. 'UA', 'DL')",
        examples=["UA"],
    )
    flight_number: str = Field(
        ...,
        pattern=r"^[A-Za-z0-9]{1,4}$",
        description="Alphanumeric flight number (1-4 characters, e.g. '1422')",
        examples=["1422"],
    )
    flight_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Departure date in YYYY-MM-DD format",
        examples=["2026-10-24"],
    )
    recipient_type: Literal["SMS", "WEBHOOK"] = Field(
        ...,
        description="Delivery channel: SMS via phone or WEBHOOK via HTTPS endpoint",
        examples=["SMS"],
    )
    destination: str = Field(
        ...,
        description="Destination address: E.164 phone number (e.g. '+15551234567') or webhook URL (e.g. 'https://api.example.com/webhook')",
        examples=["+15551234567"],
    )
    alert_on_delay: bool = Field(
        default=True,
        description="Trigger alert on confirmed turnaround / physical delay",
    )
    alert_on_crew_timeout: bool = Field(
        default=True,
        description="Trigger alert on FAA Part 117 crew timeout risk",
    )
    alert_on_swap: bool = Field(
        default=True,
        description="Trigger alert on equipment swap possibility or outstation zero-swap",
    )

    @field_validator("flight_carrier")
    @classmethod
    def validate_carrier_uppercase(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("flight_number")
    @classmethod
    def validate_flight_number(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_destination_format(self) -> "NotificationSubscription":
        dest = self.destination.strip()
        if self.recipient_type == "SMS":
            # E.164 format: begins with '+' followed by 7-15 digits
            if not dest.startswith("+") or not dest[1:].isdigit() or len(dest) < 8 or len(dest) > 16:
                raise ValueError(
                    f"Invalid E.164 phone number '{dest}'. Must begin with '+' and country code (e.g. +15551234567)."
                )
        elif self.recipient_type == "WEBHOOK":
            if not (dest.startswith("https://") or dest.startswith("http://")):
                raise ValueError(
                    f"Invalid webhook URL '{dest}'. Must start with https:// (or http:// for testing)."
                )
        return self


class NotificationResponse(BaseModel):
    """API response envelope for notification subscription actions."""

    status: str = Field(default="success", description="Status code or indicator")
    message: str = Field(..., description="Descriptive status message")
    subscription: NotificationSubscription
