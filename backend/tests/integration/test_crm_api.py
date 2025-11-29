"""Integration tests for CRM API endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.models.user import User

# API prefix for all endpoints
API_PREFIX = settings.API_V1_PREFIX


class TestContactsAPI:
    """Test contact management endpoints."""

    @pytest.mark.asyncio
    async def test_list_contacts_empty(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test listing contacts returns empty list when no contacts exist."""
        client, _user = authenticated_test_client
        response = await client.get(f"{API_PREFIX}/crm/contacts")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_contact_success(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
        sample_contact_data: dict[str, Any],
    ) -> None:
        """Test creating a contact with valid data."""
        client, _user = authenticated_test_client
        response = await client.post(f"{API_PREFIX}/crm/contacts", json=sample_contact_data)

        assert response.status_code == 201

        data = response.json()
        assert data["first_name"] == sample_contact_data["first_name"]
        assert data["last_name"] == sample_contact_data["last_name"]
        assert data["email"] == sample_contact_data["email"]
        assert data["phone_number"] == sample_contact_data["phone_number"]
        assert data["company_name"] == sample_contact_data["company_name"]
        assert data["status"] == sample_contact_data["status"]
        assert "id" in data
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_contact_minimal_data(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test creating contact with only required fields."""
        client, _user = authenticated_test_client
        minimal_data = {
            "first_name": "John",
            "phone_number": "+15551234567",
        }

        response = await client.post(f"{API_PREFIX}/crm/contacts", json=minimal_data)

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == "John"
        assert data["phone_number"] == "+15551234567"
        assert data["last_name"] is None
        assert data["email"] is None

    @pytest.mark.asyncio
    async def test_create_contact_validation_error(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test creating contact with missing required fields."""
        client, _user = authenticated_test_client
        invalid_data = {
            "first_name": "John",
            # Missing phone_number
        }

        response = await client.post(f"{API_PREFIX}/crm/contacts", json=invalid_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_contacts_with_data(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test listing contacts returns created contacts."""
        client, _user = authenticated_test_client

        # Create contacts via API
        contact1 = await client.post(
            f"{API_PREFIX}/crm/contacts",
            json={"first_name": "Alice", "phone_number": "+15551111111", "status": "new"},
        )
        assert contact1.status_code == 201

        contact2 = await client.post(
            f"{API_PREFIX}/crm/contacts",
            json={
                "first_name": "Bob",
                "phone_number": "+15552222222",
                "status": "qualified",
            },
        )
        assert contact2.status_code == 201

        # List contacts via API
        response = await client.get(f"{API_PREFIX}/crm/contacts")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check that both contacts are returned (order may vary due to timestamp precision)
        first_names = {c["first_name"] for c in data}
        assert first_names == {"Alice", "Bob"}

    @pytest.mark.asyncio
    async def test_list_contacts_pagination(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test contact listing pagination."""
        client, _user = authenticated_test_client

        # Create 5 test contacts via API
        for i in range(5):
            response = await client.post(
                f"{API_PREFIX}/crm/contacts",
                json={"first_name": f"Contact{i}", "phone_number": f"+155512345{i}0"},
            )
            assert response.status_code == 201

        # Test pagination with limit
        response = await client.get(f"{API_PREFIX}/crm/contacts?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Test pagination with skip
        response = await client.get(f"{API_PREFIX}/crm/contacts?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_contact_success(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test getting a single contact by ID."""
        client, _user = authenticated_test_client

        # Create test contact via API
        create_response = await client.post(
            f"{API_PREFIX}/crm/contacts",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone_number": "+15551234567",
                "status": "qualified",
            },
        )
        assert create_response.status_code == 201
        created_contact = create_response.json()

        # Get contact by ID
        response = await client.get(f"{API_PREFIX}/crm/contacts/{created_contact['id']}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_contact["id"]
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_get_contact_not_found(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test getting non-existent contact returns 404."""
        client, _user = authenticated_test_client
        response = await client.get(f"{API_PREFIX}/crm/contacts/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCRMStatsAPI:
    """Test CRM statistics endpoints."""

    @pytest.mark.asyncio
    async def test_get_crm_stats_empty(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test CRM stats with no data returns zero counts."""
        client, _user = authenticated_test_client
        response = await client.get(f"{API_PREFIX}/crm/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 0
        assert data["total_appointments"] == 0
        assert data["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_get_crm_stats_with_contacts(
        self,
        authenticated_test_client: tuple[AsyncClient, User],
    ) -> None:
        """Test CRM stats reflects created contacts."""
        client, _user = authenticated_test_client

        # Create test contacts via API
        for i in range(3):
            response = await client.post(
                f"{API_PREFIX}/crm/contacts",
                json={"first_name": f"Contact{i}", "phone_number": f"+155512345{i}0"},
            )
            assert response.status_code == 201

        # Get stats
        response = await client.get(f"{API_PREFIX}/crm/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 3
        assert data["total_appointments"] == 0
        assert data["total_calls"] == 0
