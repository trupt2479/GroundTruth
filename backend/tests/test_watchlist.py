import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.watchlist import WatchlistItem

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database and session for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Override get_db with test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_watchlist_item_and_t2_calculation(client, db_session):
    """GT-WATCH-01: Test watchlist item creation with automatic t2_scheduled_fetch calculation."""
    payload = {
        "user_name": "Trupti",
        "carrier": "DL",
        "flight_number": "450",
        "departure_date": "2026-10-24",
    }
    response = client.post("/api/v1/watchlist/", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["user_name"] == "Trupti"
    assert data["carrier"] == "DL"
    assert data["flight_number"] == "450"
    assert data["origin_iata"] == "ATL"
    assert data["destination_iata"] == "MCO"
    assert data["status"] == "ARMED"
    assert data["scheduled_departure"] is not None
    assert data["t2_scheduled_fetch"] is not None

    sched_dep = datetime.fromisoformat(data["scheduled_departure"])
    t2_fetch = datetime.fromisoformat(data["t2_scheduled_fetch"])

    # Difference between scheduled_departure and t2_scheduled_fetch must be exactly 2 hours
    delta = sched_dep - t2_fetch
    assert delta == timedelta(hours=2)


def test_duplicate_flight_conflict_and_get_by_user(client):
    """GT-WATCH-01: Test duplicate flight handling (409) and user retrieval."""
    payload = {
        "user_name": "Trupti",
        "carrier": "DL",
        "flight_number": "450",
        "departure_date": "2026-10-24",
    }
    # Initial creation
    res1 = client.post("/api/v1/watchlist/", json=payload)
    assert res1.status_code == 201

    # Duplicate creation
    res2 = client.post("/api/v1/watchlist/", json=payload)
    assert res2.status_code == 409
    assert "already on your watchlist" in res2.json()["detail"]

    # Retrieval for user "Trupti"
    res3 = client.get("/api/v1/watchlist/?user_name=Trupti")
    assert res3.status_code == 200
    items = res3.json()
    assert len(items) == 1
    assert items[0]["flight_number"] == "450"

    # Retrieval for user "OtherUser"
    res4 = client.get("/api/v1/watchlist/?user_name=OtherUser")
    assert res4.status_code == 200
    assert len(res4.json()) == 0


def test_milestone_due_check_armed_to_evaluated_t2(client, db_session):
    """GT-WATCH-01: Test milestone due check transitions ARMED -> EVALUATED_T2."""
    now = datetime.now(timezone.utc)
    due_item = WatchlistItem(
        id=uuid.uuid4(),
        user_name="Trupti",
        carrier="UA",
        flight_number="1422",
        departure_date="2026-10-24",
        origin_iata="ORD",
        destination_iata="EWR",
        scheduled_departure=now + timedelta(hours=1),
        t2_scheduled_fetch=now - timedelta(minutes=10),  # Past due
        status="ARMED",
    )
    db_session.add(due_item)
    db_session.commit()

    # Trigger milestone check
    resp = client.post("/api/v1/watchlist/check-milestones")
    assert resp.status_code == 200
    data = resp.json()

    assert data["checked_count"] >= 1
    assert data["evaluated_count"] >= 1

    # Verify item status in database
    db_session.refresh(due_item)
    assert due_item.status == "EVALUATED_T2"
    assert due_item.latest_assessment is not None


def test_delete_watchlist_item(client):
    """GT-WATCH-01: Test removing a flight from the watchlist."""
    payload = {
        "user_name": "Trupti",
        "carrier": "AA",
        "flight_number": "1200",
        "departure_date": "2026-10-24",
    }
    create_res = client.post("/api/v1/watchlist/", json=payload)
    assert create_res.status_code == 201
    item_id = str(create_res.json()["id"])

    # Delete item
    del_res = client.delete(f"/api/v1/watchlist/{item_id}")
    assert del_res.status_code == 200

    # Delete again -> 404
    del_again = client.delete(f"/api/v1/watchlist/{item_id}")
    assert del_again.status_code == 404

    # Get watchlist -> empty
    get_res = client.get("/api/v1/watchlist/?user_name=Trupti")
    assert len(get_res.json()) == 0
