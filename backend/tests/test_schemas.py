from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.flight import (
    AircraftInfo,
    FlightLeg,
    FlightQuery,
    InboundTurnaround,
    RealityAssessment,
    SwapHeuristic,
)


def test_flight_query_valid():
    query = FlightQuery(
        carrier="DL",
        flight_number="1234",
        departure_date=date(2026, 10, 24),
    )
    assert query.carrier == "DL"
    assert query.flight_number == "1234"
    assert query.departure_date == date(2026, 10, 24)


def test_flight_query_carrier_lowercase_invalid():
    with pytest.raises(ValidationError) as exc_info:
        FlightQuery(
            carrier="dl",
            flight_number="1234",
            departure_date=date(2026, 10, 24),
        )
    errors = exc_info.value.errors()
    assert any("carrier" in err["loc"] for err in errors)


def test_flight_query_carrier_length_invalid():
    with pytest.raises(ValidationError):
        FlightQuery(
            carrier="DAL",
            flight_number="1234",
            departure_date=date(2026, 10, 24),
        )

    with pytest.raises(ValidationError):
        FlightQuery(
            carrier="D",
            flight_number="1234",
            departure_date=date(2026, 10, 24),
        )


def test_flight_query_flight_number_length_invalid():
    with pytest.raises(ValidationError):
        FlightQuery(
            carrier="DL",
            flight_number="12345",  # Exceeds 4 chars
            departure_date=date(2026, 10, 24),
        )

    with pytest.raises(ValidationError):
        FlightQuery(
            carrier="DL",
            flight_number="",  # Min length 1
            departure_date=date(2026, 10, 24),
        )


def test_flight_query_invalid_date_format():
    # Pass string that cannot parse as YYYY-MM-DD
    with pytest.raises(ValidationError) as exc_info:
        FlightQuery.model_validate(
            {"carrier": "UA", "flight_number": "88", "departure_date": "10-24-2026"}
        )
    assert any("departure_date" in err["loc"] for err in exc_info.value.errors())


def test_aircraft_info_valid_and_invalid_category():
    aircraft = AircraftInfo(
        icao_type="A321",
        tail_number="N987DN",
        category="NARROWBODY",
    )
    assert aircraft.category == "NARROWBODY"

    with pytest.raises(ValidationError):
        AircraftInfo(
            icao_type="A321",
            tail_number="N987DN",
            category="SUPERJUMBO",  # Invalid category
        )


def test_inbound_turnaround_mtt_values():
    aircraft = AircraftInfo(
        icao_type="B738",
        tail_number="N37437",
        category="NARROWBODY",
    )
    leg = FlightLeg(
        flight_number="UA101",
        origin_iata="SFO",
        destination_iata="ORD",
        scheduled_departure=datetime(2026, 10, 24, 8, 0, tzinfo=timezone.utc),
        scheduled_arrival=datetime(2026, 10, 24, 14, 0, tzinfo=timezone.utc),
        actual_departure=datetime(2026, 10, 24, 8, 15, tzinfo=timezone.utc),
        actual_arrival=datetime(2026, 10, 24, 14, 10, tzinfo=timezone.utc),
        status="LANDED",
    )

    # Valid MTT values: 35, 45, 75
    for valid_mtt in [35, 45, 75]:
        turnaround = InboundTurnaround(
            previous_legs=[leg],
            assigned_aircraft=aircraft,
            mtt_minutes=valid_mtt,
            estimated_touchdown=datetime(2026, 10, 24, 14, 10, tzinfo=timezone.utc),
            earliest_possible_departure=datetime(
                2026, 10, 24, 14, 55, tzinfo=timezone.utc
            ),
        )
        assert turnaround.mtt_minutes == valid_mtt

    # Invalid MTT values
    for invalid_mtt in [20, 50, 60, 90]:
        with pytest.raises(ValidationError):
            InboundTurnaround(
                previous_legs=[leg],
                assigned_aircraft=aircraft,
                mtt_minutes=invalid_mtt,  # type: ignore
                estimated_touchdown=datetime(
                    2026, 10, 24, 14, 10, tzinfo=timezone.utc
                ),
                earliest_possible_departure=datetime(
                    2026, 10, 24, 14, 55, tzinfo=timezone.utc
                ),
            )


def test_inbound_turnaround_previous_legs_max_length():
    aircraft = AircraftInfo(
        icao_type="E175",
        tail_number="N101SY",
        category="REGIONAL",
    )
    leg = FlightLeg(
        flight_number="OO5544",
        origin_iata="DEN",
        destination_iata="SLC",
        scheduled_departure=datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc),
        scheduled_arrival=datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc),
        status="LANDED",
    )

    # 3 legs should exceed max_length=2
    with pytest.raises(ValidationError):
        InboundTurnaround(
            previous_legs=[leg, leg, leg],
            assigned_aircraft=aircraft,
            mtt_minutes=35,
            estimated_touchdown=datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc),
            earliest_possible_departure=datetime(
                2026, 10, 24, 8, 5, tzinfo=timezone.utc
            ),
        )


def test_swap_heuristic_literals():
    heuristic = SwapHeuristic(
        origin_is_hub=True,
        hub_type="FORTRESS_HUB",
        swap_probability="HIGH",
    )
    assert heuristic.origin_is_hub is True

    with pytest.raises(ValidationError):
        SwapHeuristic(
            origin_is_hub=True,
            hub_type="FOCUS_CITY",  # Invalid literal
            swap_probability="HIGH",
        )

    with pytest.raises(ValidationError):
        SwapHeuristic(
            origin_is_hub=True,
            hub_type="FORTRESS_HUB",
            swap_probability="VERY_HIGH",  # Invalid literal
        )


def test_reality_assessment_roundtrip_serialization():
    query = FlightQuery(
        carrier="UA",
        flight_number="2479",
        departure_date=date(2026, 10, 24),
    )
    swap = SwapHeuristic(
        origin_is_hub=False,
        hub_type="OUTSTATION",
        swap_probability="NEAR_ZERO",
    )
    official_dep = datetime(2026, 10, 24, 15, 30, tzinfo=timezone.utc)
    calculated_dep = datetime(2026, 10, 24, 16, 45, tzinfo=timezone.utc)

    assessment = RealityAssessment(
        flight_query=query,
        official_airline_departure=official_dep,
        calculated_earliest_departure=calculated_dep,
        delay_lead_time_minutes=75,
        is_unavoidable_delay=True,
        swap_evaluation=swap,
        rebooking_directive="EXPEDITE_REBOOKING",
    )

    # Serialize to JSON
    json_data = assessment.model_dump_json()
    assert isinstance(json_data, str)
    assert "2479" in json_data
    assert "EXPEDITE_REBOOKING" in json_data

    # Deserialize back from JSON
    deserialized = RealityAssessment.model_validate_json(json_data)
    assert deserialized == assessment
    assert deserialized.flight_query.carrier == "UA"
    assert deserialized.delay_lead_time_minutes == 75
    assert deserialized.is_unavoidable_delay is True
    assert deserialized.swap_evaluation.swap_probability == "NEAR_ZERO"
    assert deserialized.rebooking_directive == "EXPEDITE_REBOOKING"


def test_health_check_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "development"}

