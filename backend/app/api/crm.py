"""CRM endpoints for contacts, appointments, and call interactions."""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_invalidate, cache_set
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.call_interaction import CallInteraction
from app.models.contact import Contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


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
    email: str | None = None
    phone_number: str
    company_name: str | None = None
    status: str = "new"
    tags: str | None = None
    notes: str | None = None


@router.get("/contacts", response_model=list[ContactResponse])
@limiter.limit("100/minute")
async def list_contacts(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[Contact]:
    """List all contacts (simplified - normally would filter by user_id)."""
    result = await db.execute(
        select(Contact).offset(skip).limit(limit).order_by(Contact.created_at.desc()),
    )
    return list(result.scalars().all())


@router.get("/contacts/{contact_id}", response_model=ContactResponse)
@limiter.limit("100/minute")
async def get_contact(
    request: Request,
    contact_id: int,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Get a single contact by ID."""
    from fastapi import HTTPException

    try:
        result = await db.execute(select(Contact).where(Contact.id == contact_id))
        contact = result.scalar_one_or_none()
    except Exception:
        logger.exception("Failed to retrieve contact: %d", contact_id)
        raise

    if not contact:
        logger.error("Contact not found: %d", contact_id)
        raise HTTPException(status_code=404, detail="Contact not found")

    logger.info("Retrieved contact: %d", contact_id)
    return contact


@router.post("/contacts", response_model=ContactResponse, status_code=201)
@limiter.limit("100/minute")
async def create_contact(
    request: Request,
    contact_data: ContactCreate,
    db: AsyncSession = Depends(get_db),
) -> Contact:
    """Create a new contact (simplified - normally would get user_id from auth)."""
    try:
        contact = Contact(
            user_id=1,  # TODO: Get from authenticated user
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
    except Exception:
        logger.exception(
            "Failed to create contact: user_id=%d, phone=%s",
            1,
            contact_data.phone_number,
        )
        raise


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

    # Cache miss - fetch from database
    logger.debug("Cache miss - fetching CRM stats from database")

    contacts_count = await db.scalar(select(func.count()).select_from(Contact))
    appointments_count = await db.scalar(select(func.count()).select_from(Appointment))
    calls_count = await db.scalar(
        select(func.count()).select_from(CallInteraction),
    )

    stats = {
        "total_contacts": contacts_count or 0,
        "total_appointments": appointments_count or 0,
        "total_calls": calls_count or 0,
    }

    # Cache the results for 60 seconds
    await cache_set(cache_key, stats, ttl=60)
    logger.debug("Cached CRM stats")

    return stats
