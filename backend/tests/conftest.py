"""Pytest configuration and fixtures for backend tests."""

import asyncio
import logging
import os

# Test database URL (using temp file SQLite for tests)
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import fakeredis
import pytest
import pytest_asyncio
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

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[Any, None]:
    """Create test database engine with fresh database for each test."""
    # Create a unique temp file for each test to ensure complete isolation
    test_db_fd, test_db_path = tempfile.mkstemp(suffix=".db")
    os.close(test_db_fd)
    test_db_url = f"sqlite+aiosqlite:///{test_db_path}"

    engine = create_async_engine(
        test_db_url,
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
        db_path = Path(test_db_path)
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


@pytest.fixture
def test_redis() -> Any:
    """Create fake Redis client for testing.

    Note: Returns a factory function that creates a new fakeredis instance
    each time get_redis is called, to avoid event loop issues.
    """
    # Return a sync version that will be called to create fresh instances
    return fakeredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture(scope="function")
async def test_client(
    test_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with dependency overrides but NO authentication.

    Use this for testing unauthenticated endpoints or testing auth failure cases.
    For authenticated endpoints, use `authenticated_test_client` instead.
    """

    # Override database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_session

    # Override Redis dependency - create fresh async fakeredis for each call
    async def override_get_redis() -> Any:
        return fakeredis.FakeAsyncRedis(decode_responses=True)

    # Apply overrides
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Create test client
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def authenticated_test_client(
    test_engine: Any,
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """Create test HTTP client with authentication.

    Returns a tuple of (client, user) where user is the authenticated test user.
    Use this for testing authenticated endpoints.

    Note: This fixture creates its own session to avoid transaction isolation issues.
    """
    import app.db.redis as redis_module
    from app.core.auth import get_current_user

    # Reset global redis state to avoid event loop issues
    redis_module.redis_client = None
    redis_module.redis_pool = None

    # Create a shared fakeredis instance for this test
    shared_fake_redis = fakeredis.FakeAsyncRedis(decode_responses=True)

    # Create a fresh session for this test
    test_async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with test_async_session() as session:
        # Create test user first
        test_user = User(
            email="authuser@example.com",
            hashed_password="test_hashed_pw_1234",  # noqa: S106
            full_name="Auth Test User",
            is_active=True,
            is_superuser=False,
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)

        # Override database dependency - provide a fresh session for each request
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            request_session = test_async_session()
            async with request_session:
                yield request_session

        # Override Redis dependency - use the shared fake redis for this test
        async def override_get_redis() -> Any:
            return shared_fake_redis

        # Monkey patch the global get_redis to return our fake redis
        original_get_redis = redis_module.get_redis

        async def patched_get_redis() -> Any:
            return shared_fake_redis

        redis_module.get_redis = patched_get_redis

        # Override authentication to return our test user
        async def override_get_current_user() -> User:
            return test_user

        # Apply overrides
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_user] = override_get_current_user

        # Create test client
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, test_user

        # Clean up overrides
        app.dependency_overrides.clear()

        # Restore original get_redis
        redis_module.get_redis = original_get_redis

        # Close shared fakeredis
        await shared_fake_redis.aclose()


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
