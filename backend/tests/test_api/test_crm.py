"""Tests for CRM API endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestContactEndpoints:
    """Test contact CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_contact_success(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        sample_contact_data: dict[str, Any],
    ) -> None:
        """Test successful contact creation."""
        client, user = authenticated_test_client

        # Create contact
        response = await client.post("/api/v1/crm/contacts", json=sample_contact_data)

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == sample_contact_data["first_name"]
        assert data["last_name"] == sample_contact_data["last_name"]
        assert data["email"] == sample_contact_data["email"]
        assert data["phone_number"] == sample_contact_data["phone_number"]
        assert data["company_name"] == sample_contact_data["company_name"]
        assert data["status"] == sample_contact_data["status"]
        assert data["user_id"] == user.id
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_contact_minimal_data(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test contact creation with minimal required fields."""
        client, _user = authenticated_test_client

        minimal_data = {
            "first_name": "Jane",
            "phone_number": "+9876543210",
        }

        response = await client.post("/api/v1/crm/contacts", json=minimal_data)

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["phone_number"] == "+9876543210"
        assert data["last_name"] is None
        assert data["email"] is None
        assert data["status"] == "new"

    @pytest.mark.asyncio
    async def test_create_contact_validation_error(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test contact creation with missing required fields."""
        client, _user = authenticated_test_client

        # Missing first_name and phone_number
        invalid_data = {"email": "test@example.com"}

        response = await client.post("/api/v1/crm/contacts", json=invalid_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_contact_success(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        create_test_contact: Any,
    ) -> None:
        """Test successful contact retrieval."""
        client, user = authenticated_test_client
        contact = await create_test_contact(user_id=user.id)

        response = await client.get(f"/api/v1/crm/contacts/{contact.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == contact.id
        assert data["first_name"] == contact.first_name
        assert data["phone_number"] == contact.phone_number

    @pytest.mark.asyncio
    async def test_get_contact_not_found(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test retrieving non-existent contact."""
        client, _user = authenticated_test_client
        response = await client.get("/api/v1/crm/contacts/99999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Contact not found"

    @pytest.mark.asyncio
    async def test_list_contacts_empty(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test listing contacts when none exist."""
        client, _user = authenticated_test_client
        response = await client.get("/api/v1/crm/contacts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_contacts_success(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        create_test_contact: Any,
    ) -> None:
        """Test listing multiple contacts."""
        client, user = authenticated_test_client

        # Create multiple contacts
        await create_test_contact(
            user_id=user.id,
            first_name="Alice",
            phone_number="+1111111111",
        )
        await create_test_contact(
            user_id=user.id,
            first_name="Bob",
            phone_number="+2222222222",
        )

        response = await client.get("/api/v1/crm/contacts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Should be ordered by created_at desc (newest first)
        assert data[0]["first_name"] == "Bob"
        assert data[1]["first_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_list_contacts_pagination(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        create_test_contact: Any,
    ) -> None:
        """Test contact listing with pagination."""
        client, user = authenticated_test_client

        # Create 5 contacts
        for i in range(5):
            await create_test_contact(
                user_id=user.id,
                first_name=f"Contact{i}",
                phone_number=f"+100000000{i}",
            )

        # Test skip and limit
        response = await client.get("/api/v1/crm/contacts?skip=2&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_contact_rate_limiting(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test rate limiting on contact endpoints."""
        client, _user = authenticated_test_client

        # Make many requests to trigger rate limit
        # Rate limit is 100/minute, so we'll make 110 requests
        responses = []
        for _ in range(110):
            response = await client.get("/api/v1/crm/contacts")
            responses.append(response)

        # Some responses should be rate limited (429)
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes


class TestCRMStatsEndpoint:
    """Test CRM statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test stats endpoint with no data."""
        client, _user = authenticated_test_client
        response = await client.get("/api/v1/crm/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 0
        assert data["total_appointments"] == 0
        assert data["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        create_test_contact: Any,
        create_test_appointment: Any,
        create_test_call_interaction: Any,
    ) -> None:
        """Test stats endpoint with data."""
        client, user = authenticated_test_client
        contact1 = await create_test_contact(user_id=user.id, phone_number="+1111111111")
        contact2 = await create_test_contact(user_id=user.id, phone_number="+2222222222")

        # Create appointments for contacts
        await create_test_appointment(contact_id=contact1.id)
        await create_test_appointment(contact_id=contact2.id)
        await create_test_appointment(contact_id=contact2.id)

        # Create call interactions
        await create_test_call_interaction(contact_id=contact1.id)

        response = await client.get("/api/v1/crm/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 2
        assert data["total_appointments"] == 3
        assert data["total_calls"] == 1

    @pytest.mark.asyncio
    async def test_stats_caching(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        test_redis: Any,
        create_test_contact: Any,
    ) -> None:
        """Test that stats endpoint uses caching."""
        client, user = authenticated_test_client
        await create_test_contact(user_id=user.id)

        # First request - should cache
        response1 = await client.get("/api/v1/crm/stats")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["total_contacts"] == 1

        # Check that cache key was set (cache key includes user_id)
        cache_key = f"crm:stats:{user.id}"
        cached_value = await test_redis.get(cache_key)
        assert cached_value is not None

        # Second request - should use cache
        response2 = await client.get("/api/v1/crm/stats")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2 == data1

    @pytest.mark.asyncio
    async def test_stats_cache_invalidation_on_contact_creation(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        test_redis: Any,
        sample_contact_data: dict[str, Any],
    ) -> None:
        """Test that creating a contact invalidates stats cache."""
        client, user = authenticated_test_client

        # Get initial stats to populate cache
        response1 = await client.get("/api/v1/crm/stats")
        assert response1.status_code == 200
        assert response1.json()["total_contacts"] == 0

        # Verify cache exists (cache key includes user_id)
        cache_key = f"crm:stats:{user.id}"
        cached_value = await test_redis.get(cache_key)
        assert cached_value is not None

        # Create a contact (should invalidate cache)
        create_response = await client.post(
            "/api/v1/crm/contacts",
            json=sample_contact_data,
        )
        assert create_response.status_code == 201

        # Get stats again - should show updated count
        response2 = await client.get("/api/v1/crm/stats")
        assert response2.status_code == 200
        assert response2.json()["total_contacts"] == 1


class TestContactDatabaseIntegration:
    """Test contact database operations."""

    @pytest.mark.asyncio
    async def test_contact_persists_to_database(
        self,
        test_session: Any,
        create_test_user: Any,
        create_test_contact: Any,
    ) -> None:
        """Test that contacts are properly persisted."""
        from sqlalchemy import select

        from app.models.contact import Contact

        user = await create_test_user()
        contact = await create_test_contact(
            user_id=user.id,
            first_name="Test",
            last_name="User",
            phone_number="+1234567890",
        )

        # Query directly from database
        result = await test_session.execute(select(Contact).where(Contact.id == contact.id))
        db_contact = result.scalar_one()

        assert db_contact.id == contact.id
        assert db_contact.first_name == "Test"
        assert db_contact.last_name == "User"
        assert db_contact.phone_number == "+1234567890"
        assert db_contact.user_id == user.id

    @pytest.mark.asyncio
    async def test_contact_cascade_delete_appointments(
        self,
        test_session: Any,
        create_test_user: Any,
        create_test_contact: Any,
        create_test_appointment: Any,
    ) -> None:
        """Test that deleting a contact cascades to appointments."""
        from sqlalchemy import select

        from app.models.appointment import Appointment

        user = await create_test_user()
        contact = await create_test_contact(user_id=user.id)
        appointment = await create_test_appointment(contact_id=contact.id)

        # Delete contact
        await test_session.delete(contact)
        await test_session.commit()

        # Verify appointment was also deleted
        result = await test_session.execute(
            select(Appointment).where(Appointment.id == appointment.id)
        )
        deleted_appointment = result.scalar_one_or_none()
        assert deleted_appointment is None

    @pytest.mark.asyncio
    async def test_contact_cascade_delete_call_interactions(
        self,
        test_session: Any,
        create_test_user: Any,
        create_test_contact: Any,
        create_test_call_interaction: Any,
    ) -> None:
        """Test that deleting a contact cascades to call interactions."""
        from sqlalchemy import select

        from app.models.call_interaction import CallInteraction

        user = await create_test_user()
        contact = await create_test_contact(user_id=user.id)
        call = await create_test_call_interaction(contact_id=contact.id)

        # Delete contact
        await test_session.delete(contact)
        await test_session.commit()

        # Verify call was also deleted
        result = await test_session.execute(
            select(CallInteraction).where(CallInteraction.id == call.id)
        )
        deleted_call = result.scalar_one_or_none()
        assert deleted_call is None
