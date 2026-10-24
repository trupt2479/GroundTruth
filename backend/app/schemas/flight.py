from datetime import date, datetime
from typing import Annotated, List, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CarrierCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=False,
        pattern=r"^[A-Z]{2}$",
    ),
]

FlightNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[A-Za-z0-9]{1,4}$",
    ),
]

IataCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[A-Z]{3}$",
    ),
]


class FlightQuery(BaseModel):
    """Query parameters for looking up a specific flight instance."""

    model_config = ConfigDict(extra="forbid")

    carrier: CarrierCode = Field(
        ...,
        description="2-letter uppercase IATA carrier code (e.g., 'DL', 'UA', 'AA')",
    )
    flight_number: FlightNumber = Field(
        ...,
        description="Alphanumeric flight number with 1 to 4 characters (e.g., '123', '45B')",
    )
    departure_date: date = Field(
        ...,
        description="Departure date in YYYY-MM-DD format",
    )


class AircraftInfo(BaseModel):
    """Details regarding the specific physical aircraft assigned to a flight."""

    model_config = ConfigDict(extra="forbid")

    icao_type: str = Field(
        ...,
        description="ICAO aircraft type designator (e.g., 'A320', 'B738', 'E175')",
    )
    tail_number: str = Field(
        ...,
        description="Aircraft registration / tail number (e.g., 'N123AA')",
    )
    category: Literal["REGIONAL", "NARROWBODY", "WIDEBODY"] = Field(
        ...,
        description="Aircraft category determining minimum turnaround duration baseline",
    )


class FlightLeg(BaseModel):
    """A distinct flight leg within an aircraft's operational rotation."""

    model_config = ConfigDict(extra="forbid")

    flight_number: str = Field(..., description="Flight number of this leg")
    origin_iata: IataCode = Field(..., description="3-letter IATA origin airport code")
    destination_iata: IataCode = Field(
        ..., description="3-letter IATA destination airport code"
    )
    scheduled_departure: datetime = Field(..., description="Scheduled departure timestamp")
    scheduled_arrival: datetime = Field(..., description="Scheduled arrival timestamp")
    actual_departure: datetime | None = Field(
        default=None, description="Actual or estimated wheels-up/out timestamp"
    )
    actual_arrival: datetime | None = Field(
        default=None, description="Actual or estimated touchdown/in timestamp"
    )
    status: str = Field(
        ...,
        description="Current leg status (e.g., 'SCHEDULED', 'ACTIVE', 'LANDED', 'DELAYED')",
    )


class InboundTurnaround(BaseModel):
    """Inbound aircraft status, previous legs, and minimum turnaround time."""

    model_config = ConfigDict(extra="forbid")

    previous_legs: List[FlightLeg] = Field(
        ...,
        max_length=2,
        description="Previous flight legs of the assigned aircraft (up to 2 legs prior)",
    )
    assigned_aircraft: AircraftInfo = Field(
        ...,
        description="Assigned physical aircraft",
    )
    mtt_minutes: Literal[35, 45, 75] = Field(
        ...,
        description="Minimum Turnaround Time in minutes (35 for regional, 45 for narrowbody, 75 for widebody)",
    )
    estimated_touchdown: datetime = Field(
        ...,
        description="Estimated or actual touchdown time of the inbound flight leg",
    )
    earliest_possible_departure: datetime = Field(
        ...,
        description="Earliest possible departure time calculated from estimated_touchdown + mtt_minutes",
    )


class SwapHeuristic(BaseModel):
    """Assessment of whether an airline can mitigate delay via aircraft swap."""

    model_config = ConfigDict(extra="forbid")

    origin_is_hub: bool = Field(
        ...,
        description="Whether the departure origin is an airline operational hub",
    )
    hub_type: Literal["FORTRESS_HUB", "OUTSTATION"] = Field(
        ...,
        description="Operational hub classification",
    )
    swap_probability: Literal["HIGH", "MODERATE", "LOW", "NEAR_ZERO"] = Field(
        ...,
        description="Estimated probability of aircraft tail swap",
    )


class AirspaceAdvisory(BaseModel):
    """FAA National Airspace System (NAS) status advisory for an airport."""

    model_config = ConfigDict(extra="forbid")

    airport_iata: str = Field(
        ...,
        description="Airport 3-letter IATA code",
    )
    program_type: Literal[
        "GROUND_STOP", "GROUND_DELAY_PROGRAM", "DEICING", "NORMAL"
    ] = Field(
        ...,
        description="Type of airspace program / advisory",
    )
    reason: str | None = Field(
        default=None,
        description="Advisory operational cause (e.g. THUNDERSTORMS, LOW CEILINGS)",
    )
    avg_delay_minutes: int = Field(
        default=0,
        description="Average delay in minutes caused by the airspace program",
    )
    advisory_active: bool = Field(
        default=False,
        description="Whether the advisory program is currently active",
    )


class AlternativeFlight(BaseModel):
    """Viable alternative flight option for travelers facing severe delays."""

    model_config = ConfigDict(extra="forbid")

    flight_number: str = Field(
        ...,
        description="Flight number of alternative flight (e.g. UA1588)",
    )
    carrier: str = Field(
        ...,
        description="Carrier code (e.g. UA)",
    )
    departure_time: datetime = Field(
        ...,
        description="Scheduled departure timestamp of alternative flight",
    )
    arrival_time: datetime = Field(
        ...,
        description="Scheduled arrival timestamp of alternative flight",
    )
    origin_iata: str = Field(
        ...,
        description="Origin airport IATA code",
    )
    destination_iata: str = Field(
        ...,
        description="Destination airport IATA code",
    )
    seats_available: bool = Field(
        default=True,
        description="Whether confirmed seats are available",
    )
    standby_recommended: bool = Field(
        default=False,
        description="Whether standby status is recommended if seats are sold out",
    )


class CrewDutyAssessment(BaseModel):
    """FAA Part 117 flight crew legal duty hours and timeout risk evaluation."""

    model_config = ConfigDict(extra="forbid")

    elapsed_duty_minutes: int = Field(
        ...,
        description="Estimated elapsed duty minutes since initial crew report time",
    )
    remaining_buffer_minutes: int = Field(
        ...,
        description="Remaining buffer minutes before reaching the 840-minute (14-hour) FAA Part 117 duty limit",
    )
    timeout_risk: Literal["LOW", "MODERATE", "HIGH"] = Field(
        ...,
        description="Risk level of flight crew timing out and triggering cancellation",
    )
    risk_summary: str = Field(
        ...,
        description="Actionable summary of crew duty hours and timeout status",
    )


class RealityAssessment(BaseModel):
    """Final calculated reality assessment contrasting official airline claims against physics."""

    model_config = ConfigDict(extra="forbid")

    flight_query: FlightQuery = Field(
        ...,
        description="Flight queried by the traveler",
    )
    official_airline_departure: datetime = Field(
        ...,
        description="Official published departure time from airline channels",
    )
    calculated_earliest_departure: datetime = Field(
        ...,
        description="Calculated earliest departure based on inbound aircraft turnaround reality",
    )
    delay_lead_time_minutes: int = Field(
        ...,
        description="Lead time in minutes between calculated reality and airline-published departure",
    )
    is_unavoidable_delay: bool = Field(
        ...,
        description="True if turnaround physics make delay unavoidable despite official schedule",
    )
    swap_evaluation: SwapHeuristic = Field(
        ...,
        description="Heuristic evaluation of spare aircraft availability and swap likelihood",
    )
    rebooking_directive: Literal[
        "RELAX_IN_LOUNGE", "MONITOR_CLOSELY", "EXPEDITE_REBOOKING"
    ] = Field(
        ...,
        description="Actionable travel guidance directive for traveler",
    )
    airspace_advisory: AirspaceAdvisory | None = Field(
        default=None,
        description="Correlated FAA airspace advisory for flight origin or inbound stations",
    )
    alternative_flights: List[AlternativeFlight] = Field(
        default_factory=list,
        description="Ranked viable alternative flights if rebooking is expedited",
    )
    crew_duty: CrewDutyAssessment | None = Field(
        default=None,
        description="FAA Part 117 flight crew duty hours and timeout risk evaluation",
    )
