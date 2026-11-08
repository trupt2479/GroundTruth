import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.session import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            if isinstance(value, str):
                return uuid.UUID(value)
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(str(value)))
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_name = Column(String(100), default="Trupti", index=True, nullable=False)
    carrier = Column(String(3), nullable=False)
    flight_number = Column(String(10), nullable=False)
    departure_date = Column(String(10), nullable=False)
    origin_iata = Column(String(3), nullable=False)
    destination_iata = Column(String(3), nullable=False)
    origin_name = Column(String(255), nullable=True)
    destination_name = Column(String(255), nullable=True)
    scheduled_departure = Column(DateTime(timezone=True), nullable=True)
    t2_scheduled_fetch = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), default="ARMED", nullable=False)  # "ARMED", "EVALUATED_T2", "DEPARTED"
    latest_assessment = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
