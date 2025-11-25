"""CRM endpoints for contacts, appointments, and call interactions."""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.core.cache import cache_get, cache_invalidate, cache_set
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.call_interaction import CallInteraction
from app.models.contact import Contact

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


# Pydantic schemas
class ContactResponse(BaseModel):
    """Contact response schema."""

    id: int
    user_id: int
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


def _get_current_user_id() -> int:
    """Get current user ID (placeholder until auth is implemented).

    TODO: Replace with actual authentication - use CurrentUser dependency from app.core.auth
    """
    return 1


@router.get("/contacts", response_model=list[ContactResponse])
@limiter.limit("100/minute")
async def list_contacts(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[Contact]:
    """List all contacts for the current user."""
    # Get current user ID (placeholder)
    user_id = _get_current_user_id()

    # Validate pagination parameters to prevent DoS
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be non-negative")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be at least 1")
    if limit > MAX_CONTACTS_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_CONTACTS_LIMIT}")
    if skip > MAX_SKIP_OFFSET:  # Prevent massive table scans
        raise HTTPException(status_code=400, detail="Skip offset too large")

    cache_key = f"crm:contacts:list:{user_id}:{skip}:{limit}"

    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Cache hit for contacts list: user_id=%d, skip=%d, limit=%d", user_id, skip, limit)
        # Convert cached dicts back to Contact objects
        return [Contact(**contact_data) for contact_data in cached]

    # Fetch from database - filtered by user_id to prevent data leaks
    logger.debug("Cache miss - fetching contacts from database: user_id=%d, skip=%d, limit=%d", user_id, skip, limit)
    result = await db.execute(
        select(Contact)
        .where(Contact.user_id == user_id)
        .options(undefer(Contact.notes))
        .offset(skip)
        .limit(limit)
        .order_by(Contact.created_at.desc()),
    )
    contacts = list(result.scalars().all())

    # Cache for 5 minutes (300 seconds)
    # Use Pydantic model_dump for efficient serialization
    contacts_data = [ContactResponse.model_validate(c).model_dump() for c in contacts]
    await cache_set(cache_key, contacts_data, ttl=300)
    logger.debug("Cached contacts list for 5 minutes")
    return contacts


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
@limiter.limit("100/minute")
async def get_contact(
    request: Request,
    contact_id: int,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Get a single contact by ID (must belong to current user)."""
    user_id = _get_current_user_id()
    cache_key = f"crm:contact:{user_id}:{contact_id}"

    # Try cache first
    cached = await cache_get(cache_key)
    if cached:
        logger.debug("Cache hit for contact: %d", contact_id)
        return Contact(**cached)

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

    # Cache for 10 minutes (600 seconds)
    # Use Pydantic model_dump for efficient serialization
    contact_data = ContactResponse.model_validate(contact).model_dump()
    await cache_set(cache_key, contact_data, ttl=600)
    logger.info("Retrieved contact: %d", contact_id)
    return contact


@router.post("/contacts", response_model=ContactResponse, status_code=201)
@limiter.limit("100/minute")
async def create_contact(
    request: Request,
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Create a new contact for the current user."""
    user_id = _get_current_user_id()
    try:
        contact = Contact(
            user_id=user_id,
            **contact_data.model_dump(),
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        logger.info(
            "Created contact: id=%d, user_id=%d, phone=%s",
            contact.id,
            contact.user_id,
            contact.phone_number,
        )

        # Invalidate CRM stats cache after creating a contact
        try:
            invalidated = await cache_invalidate("crm:stats:*")
            logger.debug("Invalidated %d cache keys after contact creation", invalidated)
        except Exception:
            logger.exception("Failed to invalidate cache after contact creation")

        return contact
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


@router.get("/stats")
@limiter.limit("100/minute")
async def get_crm_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Get CRM statistics with 60-second cache."""
    # Try to get from cache first
    cache_key = "crm:stats:all"
    cached_stats = await cache_get(cache_key)

    if cached_stats is not None:
        logger.debug("Returning cached CRM stats")
        return dict(cached_stats)

    # Cache miss - fetch from database with separate count queries
    logger.debug("Cache miss - fetching CRM stats from database")

    # Use separate count queries to avoid cartesian product issues
    # This prevents count multiplication when contacts have multiple appointments/calls
    total_contacts = await db.scalar(select(func.count()).select_from(Contact))
    total_appointments = await db.scalar(select(func.count()).select_from(Appointment))
    total_calls = await db.scalar(select(func.count()).select_from(CallInteraction))

    stats = {
        "total_contacts": total_contacts or 0,
        "total_appointments": total_appointments or 0,
        "total_calls": total_calls or 0,
    }

    # Cache the results for 60 seconds
    await cache_set(cache_key, stats, ttl=60)
    logger.debug("Cached CRM stats")

    return stats
