import asyncio
from datetime import date
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.schemas.flight import FlightLeg, FlightQuery, InboundTurnaround
from app.services.aerodatabox_client import (
    AeroDataBoxClient,
    AeroDataBoxRateLimitError,
    AeroDataBoxServiceUnavailableError,
)
from app.services.cache_service import CacheService
from app.services.flight_aggregator import FlightAggregator
from app.services.opensky_client import OpenSkyClient


class MockAsyncRedisClient:
    """In-memory Redis client simulator for testing TTL and key storage."""

    def __init__(self):
        self._store = {}
        self._ttls = {}

    async def get(self, key: str):
        if key in self._store:
            expire_at = self._ttls.get(key)
            if expire_at is not None and asyncio.get_event_loop().time() > expire_at:
                del self._store[key]
                del self._ttls[key]
                return None
            return self._store[key]
        return None

    async def set(self, key: str, value: str, ex: int | None = None):
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = asyncio.get_event_loop().time() + ex
        else:
            self._ttls.pop(key, None)
        return True

    async def delete(self, key: str):
        existed = key in self._store
        self._store.pop(key, None)
        self._ttls.pop(key, None)
        return 1 if existed else 0

    async def ping(self):
        return True


@pytest.fixture
def in_memory_cache(monkeypatch):
    cache = CacheService()
    fake_redis = MockAsyncRedisClient()
    monkeypatch.setattr(cache, "_get_client", lambda: fake_redis)
    return cache


@pytest.mark.asyncio
async def test_redis_cache_set_and_get(in_memory_cache):
    test_key = "flight:UA_1422_2026-10-24"
    test_data = {"status": "SCHEDULED", "carrier": "UA", "flight_num": "1422"}

    # Initially empty
    assert await in_memory_cache.get_json(test_key) is None

    # Set with TTL = 120
    ok = await in_memory_cache.set_json(test_key, test_data, ttl_seconds=120)
    assert ok is True

    # Retrieve
    retrieved = await in_memory_cache.get_json(test_key)
    assert retrieved == test_data

    # Ping health check
    assert await in_memory_cache.ping() is True

    # Delete
    deleted = await in_memory_cache.delete(test_key)
    assert deleted is True
    assert await in_memory_cache.get_json(test_key) is None


@pytest.mark.asyncio
async def test_redis_cache_expiration(in_memory_cache):
    test_key = "tail:N123UA:state"
    test_data = {"altitude": 32000, "ground_speed": 450}

    # Set key with short TTL (0.1 second)
    await in_memory_cache.set_json(test_key, test_data, ttl_seconds=0.1)

    # Immediately present
    assert await in_memory_cache.get_json(test_key) == test_data

    # Wait past TTL
    await asyncio.sleep(0.15)

    # Should expire and return None
    assert await in_memory_cache.get_json(test_key) is None


@pytest.mark.asyncio
async def test_aerodatabox_mock_replay():
    client = AeroDataBoxClient(mock_mode=True)

    # Test get_flight_status with mock
    flight_data = await client.get_flight_status(
        carrier="UA", flight_num="1422", date="2026-10-24"
    )
    assert flight_data["number"] == "UA1422"
    assert flight_data["aircraft"]["reg"] == "N123UA"
    assert flight_data["aircraft"]["typeCode"] == "B738"
    assert flight_data["departure"]["airport"]["iata"] == "ORD"
    assert flight_data["arrival"]["airport"]["iata"] == "EWR"

    # Test get_inbound_rotations with mock
    rotations = await client.get_inbound_rotations(
        tail_number="N123UA", date="2026-10-24"
    )
    assert len(rotations) == 2
    assert all(isinstance(leg, FlightLeg) for leg in rotations)
    assert rotations[0].flight_number == "UA210"
    assert rotations[0].origin_iata == "SFO"
    assert rotations[0].destination_iata == "DEN"
    assert rotations[1].flight_number == "UA584"
    assert rotations[1].destination_iata == "ORD"


@pytest.mark.asyncio
async def test_opensky_mock_replay():
    client = OpenSkyClient(mock_mode=True)

    state = await client.get_aircraft_state("N123UA")
    assert state is not None
    assert state["callsign"].strip() == "UAL1422"
    assert state["baro_altitude_ft"] == 28000.0
    assert state["ground_speed_kts"] == 445.5
    assert state["on_ground"] is False
    assert state["latitude"] == 41.8781
    assert state["longitude"] == -87.6298


@pytest.mark.asyncio
async def test_aggregator_cache_aside_flow(in_memory_cache):
    adb_mock = AeroDataBoxClient(mock_mode=True)
    opensky_mock = OpenSkyClient(mock_mode=True)

    aggregator = FlightAggregator(
        aerodatabox_client=adb_mock,
        opensky_client=opensky_mock,
        cache_service=in_memory_cache,
    )

    query = FlightQuery(
        carrier="UA",
        flight_number="1422",
        departure_date=date(2026, 10, 24),
    )

    # Spy on aerodatabox.get_flight_status
    adb_spy = AsyncMock(wraps=adb_mock.get_flight_status)
    aggregator.aerodatabox.get_flight_status = adb_spy

    # First Call: Cache MISS -> calls external service -> writes to cache
    current_leg, turnaround, telemetry = await aggregator.get_flight_context(query)
    assert adb_spy.call_count == 1
    assert isinstance(current_leg, FlightLeg)
    assert isinstance(turnaround, InboundTurnaround)
    assert current_leg.flight_number == "UA1422"
    assert turnaround.assigned_aircraft.tail_number == "N123UA"
    assert turnaround.mtt_minutes == 45  # B738 is Narrowbody -> MTT 45m
    assert telemetry is not None
    assert telemetry["callsign"].strip() == "UAL1422"

    # Verify key was written into cache with TTL 120
    cache_key = "flight:UA_1422_2026-10-24"
    cached_val = await in_memory_cache.get_json(cache_key)
    assert cached_val is not None
    assert cached_val["current_leg"]["flight_number"] == "UA1422"

    # Second Call: Cache HIT -> returns immediately without querying external service
    current_leg_cached, turnaround_cached, telemetry_cached = (
        await aggregator.get_flight_context(query)
    )
    assert adb_spy.call_count == 1  # Not called again!
    assert current_leg_cached.flight_number == current_leg.flight_number
    assert turnaround_cached.mtt_minutes == turnaround.mtt_minutes
    assert telemetry_cached["callsign"] == telemetry["callsign"]


@pytest.mark.asyncio
async def test_aerodatabox_error_handling():
    client = AeroDataBoxClient(mock_mode=False)

    # 1. Test 429 Rate Limit Error
    mock_429_resp = httpx.Response(
        status_code=429,
        request=httpx.Request("GET", "https://aerodatabox.p.rapidapi.com/flights/number/UA100/2026-10-24"),
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_429_resp)):
        with pytest.raises(AeroDataBoxRateLimitError):
            await client.get_flight_status("UA", "100", "2026-10-24")

    # 2. Test 503 Service Unavailable Error
    mock_503_resp = httpx.Response(
        status_code=503,
        request=httpx.Request("GET", "https://aerodatabox.p.rapidapi.com/flights/number/UA100/2026-10-24"),
    )
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_503_resp)):
        with pytest.raises(AeroDataBoxServiceUnavailableError):
            await client.get_flight_status("UA", "100", "2026-10-24")
