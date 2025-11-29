"""CRM endpoints for contacts, appointments, and call interactions."""

import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.auth import CurrentUser
from app.core.cache import cache_get, cache_invalidate, cache_set
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.call_interaction import CallInteraction
from app.models.contact import Contact
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])

# Constants
MAX_CONTACTS_LIMIT = 1000  # Maximum number of contacts that can be fetched in one request
MAX_SKIP_OFFSET = 1_000_000  # Maximum pagination skip offset
MAX_NAME_LENGTH = 100  # Maximum length for first/last name
MAX_PHONE_LENGTH = 20  # Maximum phone number length
MIN_PHONE_LENGTH = 7  # Minimum phone number length
MAX_COMPANY_NAME_LENGTH = 255  # Maximum company name length
MAX_TAGS_LENGTH = 500  # Maximum tags length
MAX_NOTES_LENGTH = 10000  # Maximum notes length
MIN_DURATION_MINUTES = 5  # Minimum appointment duration
MAX_DURATION_MINUTES = 480  # Maximum appointment duration (8 hours)


# Pydantic schemas
class ContactResponse(BaseModel):
    """Contact response schema."""

    id: int
    user_id: int
    workspace_id: str | None
    first_name: str
    last_name: str | None
    email: str | None
    phone_number: str
    company_name: str | None
    status: str
    tags: str | None
    notes: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class ContactCreate(BaseModel):
    """Contact creation schema."""

    first_name: str
    last_name: str | None = None
    email: EmailStr | None = None
    phone_number: str
    company_name: str | None = None
    status: str = "new"
    tags: str | None = None
    notes: str | None = None
    workspace_id: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        """Validate workspace_id is a valid UUID if provided."""
        if v is not None:
            try:
                uuid.UUID(v)
            except ValueError as e:
                raise ValueError("workspace_id must be a valid UUID") from e
        return v

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str) -> str:
        """Validate first_name length and content."""
        v = v.strip()
        if not v:
            raise ValueError("first_name cannot be empty")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"first_name cannot exceed {MAX_NAME_LENGTH} characters")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str | None) -> str | None:
        """Validate last_name length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_NAME_LENGTH:
                raise ValueError(f"last_name cannot exceed {MAX_NAME_LENGTH} characters")
            if not v:  # Empty string after strip
                return None
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone_number format and length."""
        v = v.strip()
        # Remove common phone number formatting characters
        cleaned = re.sub(r"[^\d+]", "", v)
        if not cleaned:
            raise ValueError("phone_number cannot be empty")
        if len(cleaned) > MAX_PHONE_LENGTH:
            raise ValueError(f"phone_number cannot exceed {MAX_PHONE_LENGTH} characters")
        if len(cleaned) < MIN_PHONE_LENGTH:
            raise ValueError(f"phone_number must be at least {MIN_PHONE_LENGTH} digits")
        return cleaned

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str | None) -> str | None:
        """Validate company_name length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_COMPANY_NAME_LENGTH:
                raise ValueError(f"company_name cannot exceed {MAX_COMPANY_NAME_LENGTH} characters")
            if not v:
                return None
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        valid_statuses = {"new", "contacted", "qualified", "converted", "lost"}
        if v not in valid_statuses:
            raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: str | None) -> str | None:
        """Validate tags length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_TAGS_LENGTH:
                raise ValueError(f"tags cannot exceed {MAX_TAGS_LENGTH} characters")
            if not v:
                return None
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Validate notes length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_NOTES_LENGTH:
                raise ValueError(f"notes cannot exceed {MAX_NOTES_LENGTH} characters")
            if not v:
                return None
        return v


async def _validate_workspace_ownership(
    workspace_id_str: str,
    user_id: int,
    db: AsyncSession,
) -> uuid.UUID:
    """Validate workspace_id and verify ownership.

    Args:
        workspace_id_str: The workspace ID as a string
        user_id: The user ID to verify ownership against
        db: The database session

    Returns:
        The validated workspace UUID

    Raises:
        HTTPException: If workspace_id is invalid or not owned by user
    """
    try:
        workspace_uuid = uuid.UUID(workspace_id_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid workspace_id format") from e

    ws_result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid, Workspace.user_id == user_id)
    )
    if not ws_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workspace not found")

    return workspace_uuid


@router.get("/contacts", response_model=list[ContactResponse])
@limiter.limit("100/minute")
async def list_contacts(
    request: Request,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    workspace_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """List all contacts for the current user, optionally filtered by workspace."""
    user_id = current_user.id

    # Validate pagination parameters to prevent DoS
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be non-negative")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be at least 1")
    if limit > MAX_CONTACTS_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_CONTACTS_LIMIT}")
    if skip > MAX_SKIP_OFFSET:  # Prevent massive table scans
        raise HTTPException(status_code=400, detail="Skip offset too large")

    # Validate workspace_id if provided
    workspace_uuid = None
    if workspace_id:
        workspace_uuid = await _validate_workspace_ownership(workspace_id, user_id, db)

    cache_key = f"crm:contacts:list:{user_id}:{workspace_id or 'all'}:{skip}:{limit}"

    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        logger.debug(
            "Cache hit for contacts list: user_id=%d, workspace_id=%s, skip=%d, limit=%d",
            user_id,
            workspace_id,
            skip,
            limit,
        )
        return list(cached)

    # Fetch from database - filtered by user_id to prevent data leaks
    logger.debug(
        "Cache miss - fetching contacts from database: user_id=%d, workspace_id=%s, skip=%d, limit=%d",
        user_id,
        workspace_id,
        skip,
        limit,
    )

    # Build query
    query = select(Contact).where(Contact.user_id == user_id)
    if workspace_uuid:
        query = query.where(Contact.workspace_id == workspace_uuid)

    query = (
        query.options(undefer(Contact.notes))
        .offset(skip)
        .limit(limit)
        .order_by(Contact.created_at.desc())
    )

    result = await db.execute(query)
    contacts = list(result.scalars().all())

    # Build response with workspace_id as string
    contacts_data: list[dict[str, object]] = []
    for c in contacts:
        contacts_data.append(
            {
                "id": c.id,
                "user_id": c.user_id,
                "workspace_id": str(c.workspace_id) if c.workspace_id else None,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "email": c.email,
                "phone_number": c.phone_number,
                "company_name": c.company_name,
                "status": c.status,
                "tags": c.tags,
                "notes": c.notes,
            }
        )

    # Cache for 5 minutes (300 seconds)
    await cache_set(cache_key, contacts_data, ttl=300)
    logger.debug("Cached contacts list for 5 minutes")
    return contacts_data


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
@limiter.limit("100/minute")
async def get_contact(
    request: Request,
    contact_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Get a single contact by ID (must belong to current user)."""
    user_id = current_user.id
    cache_key = f"crm:contact:{user_id}:{contact_id}"

    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Cache hit for contact: %d", contact_id)
        return dict(cached)

    # Fetch from database - filter by user_id to prevent unauthorized access
    logger.debug("Cache miss - fetching contact from database: %d", contact_id)
    try:
        result = await db.execute(
            select(Contact)
            .options(undefer(Contact.notes))
            .where(Contact.id == contact_id, Contact.user_id == user_id),
        )
        contact = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving contact: %d", contact_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected error retrieving contact: %d", contact_id)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e

    if not contact:
        logger.error("Contact not found or unauthorized: %d", contact_id)
        raise HTTPException(status_code=404, detail="Contact not found")

    # Build response with workspace_id as string
    contact_data: dict[str, object] = {
        "id": contact.id,
        "user_id": contact.user_id,
        "workspace_id": str(contact.workspace_id) if contact.workspace_id else None,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "phone_number": contact.phone_number,
        "company_name": contact.company_name,
        "status": contact.status,
        "tags": contact.tags,
        "notes": contact.notes,
    }

    # Cache for 10 minutes (600 seconds)
    await cache_set(cache_key, contact_data, ttl=600)
    logger.info("Retrieved contact: %d", contact_id)
    return contact_data


@router.post("/contacts", response_model=ContactResponse, status_code=201)
@limiter.limit("100/minute")
async def create_contact(
    request: Request,
    contact_data: ContactCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Create a new contact for the current user."""
    user_id = current_user.id

    # Validate workspace_id if provided
    workspace_uuid = None
    if contact_data.workspace_id:
        workspace_uuid = await _validate_workspace_ownership(contact_data.workspace_id, user_id, db)

    try:
        # Build contact data, converting workspace_id string to UUID
        contact_dict = contact_data.model_dump(exclude={"workspace_id"})
        contact = Contact(
            user_id=user_id,
            workspace_id=workspace_uuid,
            **contact_dict,
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        logger.info(
            "Created contact: id=%d, user_id=%d, phone=%s, workspace_id=%s",
            contact.id,
            contact.user_id,
            contact.phone_number,
            contact.workspace_id,
        )

        response_data: dict[str, object] = {
            "id": contact.id,
            "user_id": contact.user_id,
            "workspace_id": str(contact.workspace_id) if contact.workspace_id else None,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "phone_number": contact.phone_number,
            "company_name": contact.company_name,
            "status": contact.status,
            "tags": contact.tags,
            "notes": contact.notes,
        }

        # Invalidate CRM caches after creating a contact
        try:
            # Invalidate contacts list cache so new contacts appear immediately
            list_invalidated = await cache_invalidate(f"crm:contacts:list:{user_id}:*")
            stats_invalidated = await cache_invalidate("crm:stats:*")
            logger.debug(
                "Invalidated %d list cache keys and %d stats cache keys after contact creation",
                list_invalidated,
                stats_invalidated,
            )
        except Exception:
            logger.exception("Failed to invalidate cache after contact creation")

        return response_data
    except IntegrityError as e:
        await db.rollback()
        logger.warning(
            "Integrity constraint violation creating contact: user_id=%d, phone=%s",
            user_id,
            contact_data.phone_number,
        )
        # Check if it's a duplicate phone or email
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
        if "ix_contacts_user_id_phone_unique" in error_msg:
            raise HTTPException(
                status_code=409,
                detail="A contact with this phone number already exists",
            ) from e
        if "ix_contacts_user_id_email_unique" in error_msg:
            raise HTTPException(
                status_code=409,
                detail="A contact with this email already exists",
            ) from e
        raise HTTPException(
            status_code=400,
            detail="Failed to create contact due to constraint violation",
        ) from e
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error creating contact: phone=%s", contact_data.phone_number)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        await db.rollback()
        logger.exception(
            "Unexpected error creating contact: user_id=%d, phone=%s",
            user_id,
            contact_data.phone_number,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e


class ContactUpdate(BaseModel):
    """Contact update schema - all fields optional."""

    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    company_name: str | None = None
    status: str | None = None
    tags: str | None = None
    notes: str | None = None
    workspace_id: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        """Validate workspace_id is a valid UUID if provided."""
        if v is not None:
            try:
                uuid.UUID(v)
            except ValueError as e:
                raise ValueError("workspace_id must be a valid UUID") from e
        return v

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, v: str | None) -> str | None:
        """Validate first_name length and content."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("first_name cannot be empty")
            if len(v) > MAX_NAME_LENGTH:
                raise ValueError(f"first_name cannot exceed {MAX_NAME_LENGTH} characters")
        return v

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, v: str | None) -> str | None:
        """Validate last_name length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_NAME_LENGTH:
                raise ValueError(f"last_name cannot exceed {MAX_NAME_LENGTH} characters")
            if not v:
                return None
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        """Validate phone_number format and length."""
        if v is not None:
            v = v.strip()
            cleaned = re.sub(r"[^\d+]", "", v)
            if not cleaned:
                raise ValueError("phone_number cannot be empty")
            if len(cleaned) > MAX_PHONE_LENGTH:
                raise ValueError(f"phone_number cannot exceed {MAX_PHONE_LENGTH} characters")
            if len(cleaned) < MIN_PHONE_LENGTH:
                raise ValueError(f"phone_number must be at least {MIN_PHONE_LENGTH} digits")
            return cleaned
        return v

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str | None) -> str | None:
        """Validate company_name length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_COMPANY_NAME_LENGTH:
                raise ValueError(f"company_name cannot exceed {MAX_COMPANY_NAME_LENGTH} characters")
            if not v:
                return None
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status is one of the allowed values."""
        if v is not None:
            valid_statuses = {"new", "contacted", "qualified", "converted", "lost"}
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: str | None) -> str | None:
        """Validate tags length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_TAGS_LENGTH:
                raise ValueError(f"tags cannot exceed {MAX_TAGS_LENGTH} characters")
            if not v:
                return None
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str | None) -> str | None:
        """Validate notes length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_NOTES_LENGTH:
                raise ValueError(f"notes cannot exceed {MAX_NOTES_LENGTH} characters")
            if not v:
                return None
        return v


@router.put("/contacts/{contact_id}", response_model=ContactResponse)
@limiter.limit("100/minute")
async def update_contact(
    request: Request,
    contact_id: int,
    contact_data: ContactUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Update an existing contact (must belong to current user)."""
    user_id = current_user.id

    # Validate workspace_id if provided
    workspace_uuid = None
    if contact_data.workspace_id:
        workspace_uuid = await _validate_workspace_ownership(contact_data.workspace_id, user_id, db)

    # Fetch existing contact - filter by user_id for security
    try:
        result = await db.execute(
            select(Contact)
            .options(undefer(Contact.notes))
            .where(Contact.id == contact_id, Contact.user_id == user_id),
        )
        contact = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving contact for update: %d", contact_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not contact:
        logger.error("Contact not found or unauthorized for update: %d", contact_id)
        raise HTTPException(status_code=404, detail="Contact not found")

    # Update only provided fields, handling workspace_id specially
    update_data = contact_data.model_dump(exclude_unset=True, exclude={"workspace_id"})
    for field, value in update_data.items():
        setattr(contact, field, value)

    # Handle workspace_id separately (convert string to UUID)
    if contact_data.workspace_id is not None:
        contact.workspace_id = workspace_uuid

    try:
        await db.commit()
        await db.refresh(contact)

        logger.info(
            "Updated contact: id=%d, user_id=%d",
            contact.id,
            contact.user_id,
        )

        # Invalidate caches
        try:
            await cache_invalidate(f"crm:contact:{user_id}:{contact_id}")
            await cache_invalidate(f"crm:contacts:list:{user_id}:*")
            await cache_invalidate("crm:stats:*")
        except Exception:
            logger.exception("Failed to invalidate cache after contact update")

        return {
            "id": contact.id,
            "user_id": contact.user_id,
            "workspace_id": str(contact.workspace_id) if contact.workspace_id else None,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "email": contact.email,
            "phone_number": contact.phone_number,
            "company_name": contact.company_name,
            "status": contact.status,
            "tags": contact.tags,
            "notes": contact.notes,
        }
    except IntegrityError as e:
        await db.rollback()
        logger.warning(
            "Integrity constraint violation updating contact: id=%d",
            contact_id,
        )
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
        if "ix_contacts_user_id_phone_unique" in error_msg:
            raise HTTPException(
                status_code=409,
                detail="A contact with this phone number already exists",
            ) from e
        if "ix_contacts_user_id_email_unique" in error_msg:
            raise HTTPException(
                status_code=409,
                detail="A contact with this email already exists",
            ) from e
        raise HTTPException(
            status_code=400,
            detail="Failed to update contact due to constraint violation",
        ) from e
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error updating contact: %d", contact_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        await db.rollback()
        logger.exception("Unexpected error updating contact: %d", contact_id)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e


@router.delete("/contacts/{contact_id}", status_code=204)
@limiter.limit("100/minute")
async def delete_contact(
    request: Request,
    contact_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a contact (must belong to current user)."""
    user_id = current_user.id

    # Fetch existing contact - filter by user_id for security
    try:
        result = await db.execute(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id),
        )
        contact = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving contact for deletion: %d", contact_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not contact:
        logger.error("Contact not found or unauthorized for deletion: %d", contact_id)
        raise HTTPException(status_code=404, detail="Contact not found")

    try:
        await db.delete(contact)
        await db.commit()

        logger.info(
            "Deleted contact: id=%d, user_id=%d",
            contact.id,
            user_id,
        )

        # Invalidate caches
        try:
            await cache_invalidate(f"crm:contact:{user_id}:{contact_id}")
            await cache_invalidate(f"crm:contacts:list:{user_id}:*")
            await cache_invalidate("crm:stats:*")
        except Exception:
            logger.exception("Failed to invalidate cache after contact deletion")

    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error deleting contact: %d", contact_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
    except Exception as e:
        await db.rollback()
        logger.exception("Unexpected error deleting contact: %d", contact_id)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        ) from e


@router.get("/stats")
@limiter.limit("100/minute")
async def get_crm_stats(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get CRM statistics with 60-second cache."""
    user_id = current_user.id

    # Try to get from cache first (include user_id in cache key)
    cache_key = f"crm:stats:{user_id}"
    cached_stats = await cache_get(cache_key)

    if cached_stats is not None:
        logger.debug("Returning cached CRM stats for user %d", user_id)
        return dict(cached_stats)

    # Cache miss - fetch from database with separate count queries
    logger.debug("Cache miss - fetching CRM stats from database for user %d", user_id)

    # Use separate count queries filtered by user_id to avoid data leaks
    # Contacts are directly linked to user_id
    total_contacts = await db.scalar(
        select(func.count()).select_from(Contact).where(Contact.user_id == user_id)
    )
    # Appointments are linked through contacts
    total_appointments = await db.scalar(
        select(func.count())
        .select_from(Appointment)
        .join(Contact)
        .where(Contact.user_id == user_id)
    )
    # CallInteractions are linked through contacts
    total_calls = await db.scalar(
        select(func.count())
        .select_from(CallInteraction)
        .join(Contact)
        .where(Contact.user_id == user_id)
    )

    stats = {
        "total_contacts": total_contacts or 0,
        "total_appointments": total_appointments or 0,
        "total_calls": total_calls or 0,
    }

    # Cache the results for 60 seconds
    await cache_set(cache_key, stats, ttl=60)
    logger.debug("Cached CRM stats for user %d", user_id)

    return stats


# --- Appointment Schemas ---


class AppointmentResponse(BaseModel):
    """Appointment response schema."""

    id: int
    contact_id: int
    workspace_id: str | None = None
    agent_id: str | None = None
    scheduled_at: str
    duration_minutes: int
    status: str
    service_type: str | None
    notes: str | None
    created_by_agent: str | None
    contact_name: str | None = None
    contact_phone: str | None = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class AppointmentCreate(BaseModel):
    """Appointment creation schema."""

    contact_id: int
    workspace_id: str | None = None
    scheduled_at: str
    duration_minutes: int = 30
    service_type: str | None = None
    notes: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str | None) -> str | None:
        """Validate workspace_id is a valid UUID if provided."""
        if v is None:
            return v
        try:
            uuid.UUID(v)
        except ValueError as e:
            raise ValueError("workspace_id must be a valid UUID") from e
        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: str) -> str:
        """Validate scheduled_at is a valid ISO datetime."""
        from datetime import datetime

        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError("scheduled_at must be a valid ISO 8601 datetime") from e
        return v

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        """Validate duration is reasonable."""
        if v < MIN_DURATION_MINUTES:
            raise ValueError(f"duration_minutes must be at least {MIN_DURATION_MINUTES}")
        if v > MAX_DURATION_MINUTES:
            raise ValueError(f"duration_minutes cannot exceed {MAX_DURATION_MINUTES}")
        return v


class AppointmentUpdate(BaseModel):
    """Appointment update schema - all fields optional."""

    scheduled_at: str | None = None
    duration_minutes: int | None = None
    status: str | None = None
    service_type: str | None = None
    notes: str | None = None

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v: str | None) -> str | None:
        """Validate scheduled_at is a valid ISO datetime."""
        if v is not None:
            from datetime import datetime

            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError("scheduled_at must be a valid ISO 8601 datetime") from e
        return v

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: int | None) -> int | None:
        """Validate duration is reasonable."""
        if v is not None:
            if v < MIN_DURATION_MINUTES:
                raise ValueError(f"duration_minutes must be at least {MIN_DURATION_MINUTES}")
            if v > MAX_DURATION_MINUTES:
                raise ValueError(f"duration_minutes cannot exceed {MAX_DURATION_MINUTES}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate status is one of the allowed values."""
        if v is not None:
            valid_statuses = {"scheduled", "completed", "cancelled", "no_show"}
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v


# --- Appointment Endpoints ---


@router.get("/appointments", response_model=list[AppointmentResponse])
@limiter.limit("100/minute")
async def list_appointments(
    request: Request,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    workspace_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """List all appointments for the current user's contacts, optionally filtered by workspace."""
    from datetime import datetime

    from sqlalchemy.orm import selectinload

    user_id = current_user.id

    # Validate pagination
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be non-negative")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be at least 1")
    if limit > MAX_CONTACTS_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_CONTACTS_LIMIT}")

    # Validate workspace_id if provided
    workspace_uuid = None
    if workspace_id:
        workspace_uuid = await _validate_workspace_ownership(workspace_id, user_id, db)

    # Build query - join with contacts to filter by user_id
    # Use undefer to eagerly load the notes column which is deferred by default
    from sqlalchemy.orm import undefer

    query = (
        select(Appointment)
        .join(Contact)
        .where(Contact.user_id == user_id)
        .options(selectinload(Appointment.contact), undefer(Appointment.notes))
        .offset(skip)
        .limit(limit)
        .order_by(Appointment.scheduled_at.desc())
    )

    if status:
        query = query.where(Appointment.status == status)

    # Filter by workspace if provided
    if workspace_uuid:
        query = query.where(Appointment.workspace_id == workspace_uuid)

    try:
        result = await db.execute(query)
        appointments = list(result.scalars().all())
    except DBAPIError as e:
        logger.exception("Database error listing appointments")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    # Build response with contact info
    response: list[dict[str, object]] = []
    for appt in appointments:
        scheduled_at_str = (
            appt.scheduled_at.isoformat()
            if isinstance(appt.scheduled_at, datetime)
            else str(appt.scheduled_at)
        )
        response.append(
            {
                "id": appt.id,
                "contact_id": appt.contact_id,
                "workspace_id": str(appt.workspace_id) if appt.workspace_id else None,
                "agent_id": str(appt.agent_id) if appt.agent_id else None,
                "scheduled_at": scheduled_at_str,
                "duration_minutes": appt.duration_minutes,
                "status": appt.status,
                "service_type": appt.service_type,
                "notes": appt.notes,
                "created_by_agent": appt.created_by_agent,
                "contact_name": f"{appt.contact.first_name} {appt.contact.last_name or ''}".strip()
                if appt.contact
                else None,
                "contact_phone": appt.contact.phone_number if appt.contact else None,
            }
        )

    return response


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
@limiter.limit("100/minute")
async def get_appointment(
    request: Request,
    appointment_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Get a single appointment by ID."""
    from datetime import datetime

    from sqlalchemy.orm import selectinload

    user_id = current_user.id

    try:
        result = await db.execute(
            select(Appointment)
            .join(Contact)
            .where(Appointment.id == appointment_id, Contact.user_id == user_id)
            .options(selectinload(Appointment.contact)),
        )
        appointment = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving appointment: %d", appointment_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    scheduled_at_str = (
        appointment.scheduled_at.isoformat()
        if isinstance(appointment.scheduled_at, datetime)
        else str(appointment.scheduled_at)
    )
    return {
        "id": appointment.id,
        "contact_id": appointment.contact_id,
        "workspace_id": str(appointment.workspace_id) if appointment.workspace_id else None,
        "agent_id": str(appointment.agent_id) if appointment.agent_id else None,
        "scheduled_at": scheduled_at_str,
        "duration_minutes": appointment.duration_minutes,
        "status": appointment.status,
        "service_type": appointment.service_type,
        "notes": appointment.notes,
        "created_by_agent": appointment.created_by_agent,
        "contact_name": f"{appointment.contact.first_name} {appointment.contact.last_name or ''}".strip()
        if appointment.contact
        else None,
        "contact_phone": appointment.contact.phone_number if appointment.contact else None,
    }


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
@limiter.limit("100/minute")
async def create_appointment(
    request: Request,
    appointment_data: AppointmentCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Create a new appointment."""
    from datetime import datetime

    from sqlalchemy.orm import selectinload

    user_id = current_user.id

    # Verify contact belongs to user
    contact_result = await db.execute(
        select(Contact).where(
            Contact.id == appointment_data.contact_id, Contact.user_id == user_id
        ),
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # Validate workspace_id if provided
    workspace_uuid = None
    if appointment_data.workspace_id:
        workspace_uuid = await _validate_workspace_ownership(
            appointment_data.workspace_id, user_id, db
        )

    try:
        scheduled_dt = datetime.fromisoformat(appointment_data.scheduled_at.replace("Z", "+00:00"))
        appointment = Appointment(
            contact_id=appointment_data.contact_id,
            workspace_id=workspace_uuid,
            scheduled_at=scheduled_dt,
            duration_minutes=appointment_data.duration_minutes,
            service_type=appointment_data.service_type,
            notes=appointment_data.notes,
        )
        db.add(appointment)
        await db.commit()
        await db.refresh(appointment, ["contact"])

        # Reload with contact
        appt_result = await db.execute(
            select(Appointment)
            .where(Appointment.id == appointment.id)
            .options(selectinload(Appointment.contact)),
        )
        appointment = appt_result.scalar_one()

        logger.info("Created appointment: id=%d, contact_id=%d", appointment.id, contact.id)

        # Invalidate stats cache
        await cache_invalidate("crm:stats:*")

        scheduled_at_str = (
            appointment.scheduled_at.isoformat()
            if isinstance(appointment.scheduled_at, datetime)
            else str(appointment.scheduled_at)
        )
        return {
            "id": appointment.id,
            "contact_id": appointment.contact_id,
            "workspace_id": str(appointment.workspace_id) if appointment.workspace_id else None,
            "agent_id": str(appointment.agent_id) if appointment.agent_id else None,
            "scheduled_at": scheduled_at_str,
            "duration_minutes": appointment.duration_minutes,
            "status": appointment.status,
            "service_type": appointment.service_type,
            "notes": appointment.notes,
            "created_by_agent": appointment.created_by_agent,
            "contact_name": f"{appointment.contact.first_name} {appointment.contact.last_name or ''}".strip()
            if appointment.contact
            else None,
            "contact_phone": appointment.contact.phone_number if appointment.contact else None,
        }
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error creating appointment")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
@limiter.limit("100/minute")
async def update_appointment(
    request: Request,
    appointment_id: int,
    appointment_data: AppointmentUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Update an existing appointment."""
    from datetime import datetime

    from sqlalchemy.orm import selectinload

    user_id = current_user.id

    # Fetch appointment with contact
    try:
        result = await db.execute(
            select(Appointment)
            .join(Contact)
            .where(Appointment.id == appointment_id, Contact.user_id == user_id)
            .options(selectinload(Appointment.contact)),
        )
        appointment = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving appointment for update: %d", appointment_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Update fields
    update_data = appointment_data.model_dump(exclude_unset=True)
    for field, field_value in update_data.items():
        if field == "scheduled_at" and field_value:
            setattr(
                appointment,
                field,
                datetime.fromisoformat(field_value.replace("Z", "+00:00")),
            )
        else:
            setattr(appointment, field, field_value)

    try:
        await db.commit()
        await db.refresh(appointment)

        logger.info("Updated appointment: id=%d", appointment.id)

        # Invalidate stats cache
        await cache_invalidate("crm:stats:*")

        scheduled_at_str = (
            appointment.scheduled_at.isoformat()
            if isinstance(appointment.scheduled_at, datetime)
            else str(appointment.scheduled_at)
        )
        return {
            "id": appointment.id,
            "contact_id": appointment.contact_id,
            "workspace_id": str(appointment.workspace_id) if appointment.workspace_id else None,
            "agent_id": str(appointment.agent_id) if appointment.agent_id else None,
            "scheduled_at": scheduled_at_str,
            "duration_minutes": appointment.duration_minutes,
            "status": appointment.status,
            "service_type": appointment.service_type,
            "notes": appointment.notes,
            "created_by_agent": appointment.created_by_agent,
            "contact_name": f"{appointment.contact.first_name} {appointment.contact.last_name or ''}".strip()
            if appointment.contact
            else None,
            "contact_phone": appointment.contact.phone_number if appointment.contact else None,
        }
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error updating appointment: %d", appointment_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.delete("/appointments/{appointment_id}", status_code=204)
@limiter.limit("100/minute")
async def delete_appointment(
    request: Request,
    appointment_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an appointment."""
    user_id = current_user.id

    try:
        result = await db.execute(
            select(Appointment)
            .join(Contact)
            .where(Appointment.id == appointment_id, Contact.user_id == user_id),
        )
        appointment = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving appointment for deletion: %d", appointment_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    try:
        await db.delete(appointment)
        await db.commit()

        logger.info("Deleted appointment: id=%d", appointment_id)

        # Invalidate stats cache
        await cache_invalidate("crm:stats:*")

    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error deleting appointment: %d", appointment_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
