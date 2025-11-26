"""Pytest configuration and fixtures for backend tests."""

import asyncio
import logging
import os

# Test database URL (using temp file SQLite for tests)
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from fakeredis import aioredis as fakeredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.redis import get_redis
from app.db.session import get_db
from app.main import app
from app.models.appointment import Appointment
from app.models.call_interaction import CallInteraction
from app.models.contact import Contact

# Import all models to ensure they're registered with Base.metadata
from app.models.user import User

# Create a temp file for the test database
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[Any, None]:
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    # Clean up temp database file
    try:
        db_path = Path(_test_db_path)
        if db_path.exists():
            db_path.unlink()
    except Exception as e:
        logger.debug("Failed to clean up test database: %s", e)


@pytest_asyncio.fixture(scope="function")
async def test_session(test_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def test_redis() -> AsyncGenerator[Any, None]:
    """Create fake Redis client for testing."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    yield redis_client
    await redis_client.flushall()
    await redis_client.aclose()


@pytest_asyncio.fixture(scope="function")
async def test_client(
    test_session: AsyncSession,
    test_redis: Any,
) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with dependency overrides."""

    # Override database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    # Override Redis dependency
    async def override_get_redis() -> Any:
        return test_redis

    # Apply overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Create test client
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_data() -> dict[str, Any]:
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "hashed_password": "hashed_password_123",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def sample_contact_data() -> dict[str, Any]:
    """Sample contact data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone_number": "+1234567890",
        "company_name": "ACME Corp",
        "status": "new",
        "tags": "lead,important",
        "notes": "Interested in our services",
    }


@pytest.fixture
def sample_appointment_data() -> dict[str, Any]:
    """Sample appointment data for testing."""
    from datetime import UTC, datetime, timedelta

    return {
        "scheduled_at": datetime.now(UTC) + timedelta(days=1),
        "duration_minutes": 30,
        "status": "scheduled",
        "service_type": "consultation",
        "notes": "Initial consultation",
        "created_by_agent": "test-agent-1",
    }


@pytest.fixture
def sample_call_interaction_data() -> dict[str, Any]:
    """Sample call interaction data for testing."""
    from datetime import UTC, datetime, timedelta

    call_start = datetime.now(UTC) - timedelta(hours=1)
    call_end = call_start + timedelta(minutes=5)

    return {
        "call_started_at": call_start,
        "call_ended_at": call_end,
        "duration_seconds": 300,
        "agent_name": "VoiceBot Alpha",
        "agent_id": "agent-123",
        "outcome": "answered",
        "transcript": "Customer: Hello. Agent: Hi! How can I help you today?",
        "ai_summary": "Customer inquired about services.",
        "sentiment_score": 0.8,
        "action_items": "Follow up with pricing information",
        "notes": "Customer was very friendly",
    }


@pytest_asyncio.fixture
async def create_test_user(test_session: AsyncSession) -> Any:
    """Factory fixture to create test users."""

    async def _create_user(**kwargs: Any) -> User:
        user_data = {
            "email": "testuser@example.com",
            "hashed_password": "hashed_password",
            "full_name": "Test User",
            "is_active": True,
            "is_superuser": False,
        }
        user_data.update(kwargs)
        user = User(**user_data)
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        return user

    return _create_user


@pytest_asyncio.fixture
async def create_test_contact(test_session: AsyncSession) -> Any:
    """Factory fixture to create test contacts."""

    async def _create_contact(**kwargs: Any) -> Contact:
        contact_data = {
            "user_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone_number": "+1234567890",
            "company_name": "ACME Corp",
            "status": "new",
        }
        contact_data.update(kwargs)
        contact = Contact(**contact_data)
        test_session.add(contact)
        await test_session.commit()
        await test_session.refresh(contact)
        return contact

    return _create_contact


@pytest_asyncio.fixture
async def create_test_appointment(test_session: AsyncSession) -> Any:
    """Factory fixture to create test appointments."""
    from datetime import UTC, datetime, timedelta

    async def _create_appointment(**kwargs: Any) -> Appointment:
        appointment_data = {
            "contact_id": 1,
            "scheduled_at": datetime.now(UTC) + timedelta(days=1),
            "duration_minutes": 30,
            "status": "scheduled",
        }
        appointment_data.update(kwargs)
        appointment = Appointment(**appointment_data)
        test_session.add(appointment)
        await test_session.commit()
        await test_session.refresh(appointment)
        return appointment

    return _create_appointment


@pytest_asyncio.fixture
async def create_test_call_interaction(test_session: AsyncSession) -> Any:
    """Factory fixture to create test call interactions."""
    from datetime import UTC, datetime

    async def _create_call(**kwargs: Any) -> CallInteraction:
        call_data = {
            "contact_id": 1,
            "call_started_at": datetime.now(UTC),
            "outcome": "answered",
        }
        call_data.update(kwargs)
        call = CallInteraction(**call_data)
        test_session.add(call)
        await test_session.commit()
        await test_session.refresh(call)
        return call

    return _create_call
