"""Phone numbers API routes."""

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, user_id_to_uuid
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.phone_number import PhoneNumber

router = APIRouter(prefix="/api/v1/phone-numbers", tags=["phone-numbers"])
logger = structlog.get_logger()


# =============================================================================
# Pydantic Models
# =============================================================================


class PhoneNumberResponse(BaseModel):
    """Phone number response."""

    id: str
    phone_number: str
    friendly_name: str | None
    provider: str
    provider_id: str
    workspace_id: str | None
    workspace_name: str | None = None
    assigned_agent_id: str | None
    assigned_agent_name: str | None = None
    can_receive_calls: bool
    can_make_calls: bool
    can_receive_sms: bool
    can_send_sms: bool
    status: str
    notes: str | None
    purchased_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PhoneNumberListResponse(BaseModel):
    """Paginated phone numbers response."""

    phone_numbers: list[PhoneNumberResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreatePhoneNumberRequest(BaseModel):
    """Request to register a phone number."""

    phone_number: str
    friendly_name: str | None = None
    provider: str = "telnyx"
    provider_id: str
    workspace_id: str | None = None
    can_receive_calls: bool = True
    can_make_calls: bool = True
    can_receive_sms: bool = False
    can_send_sms: bool = False
    notes: str | None = None


class UpdatePhoneNumberRequest(BaseModel):
    """Request to update a phone number."""

    friendly_name: str | None = None
    workspace_id: str | None = None
    assigned_agent_id: str | None = None
    status: str | None = None
    notes: str | None = None


# =============================================================================
# Phone Number Endpoints
# =============================================================================


@router.get("", response_model=PhoneNumberListResponse)
async def list_phone_numbers(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    workspace_id: str | None = Query(default=None, description="Filter by workspace ID"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> PhoneNumberListResponse:
    """List phone numbers for the current user.

    Args:
        current_user: Authenticated user
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of records per page
        workspace_id: Optional filter by workspace ID
        status: Optional filter by status

    Returns:
        Paginated list of phone numbers
    """
    log = logger.bind(user_id=current_user.id)
    log.info("listing_phone_numbers", page=page, page_size=page_size)

    # Build query
    user_uuid = user_id_to_uuid(current_user.id)
    query = select(PhoneNumber).where(PhoneNumber.user_id == user_uuid)

    # Apply filters
    if workspace_id:
        query = query.where(PhoneNumber.workspace_id == uuid.UUID(workspace_id))
    if status:
        query = query.where(PhoneNumber.status == status)

    # Get total count
    count_query = select(PhoneNumber.id).where(PhoneNumber.user_id == user_uuid)
    if workspace_id:
        count_query = count_query.where(PhoneNumber.workspace_id == uuid.UUID(workspace_id))
    if status:
        count_query = count_query.where(PhoneNumber.status == status)

    count_result = await db.execute(count_query)
    total = len(count_result.all())

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.order_by(desc(PhoneNumber.created_at)).offset(offset).limit(page_size)

    result = await db.execute(query)
    records = result.scalars().all()

    # Build response with workspace and agent names
    phone_numbers = []
    for record in records:
        workspace_name = None
        agent_name = None

        if record.workspace:
            workspace_name = record.workspace.name
        if record.assigned_agent:
            agent_name = record.assigned_agent.name

        phone_numbers.append(
            PhoneNumberResponse(
                id=str(record.id),
                phone_number=record.phone_number,
                friendly_name=record.friendly_name,
                provider=record.provider,
                provider_id=record.provider_id,
                workspace_id=str(record.workspace_id) if record.workspace_id else None,
                workspace_name=workspace_name,
                assigned_agent_id=str(record.assigned_agent_id)
                if record.assigned_agent_id
                else None,
                assigned_agent_name=agent_name,
                can_receive_calls=record.can_receive_calls,
                can_make_calls=record.can_make_calls,
                can_receive_sms=record.can_receive_sms,
                can_send_sms=record.can_send_sms,
                status=record.status,
                notes=record.notes,
                purchased_at=record.purchased_at,
                created_at=record.created_at,
            )
        )

    total_pages = (total + page_size - 1) // page_size

    return PhoneNumberListResponse(
        phone_numbers=phone_numbers,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{phone_number_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_number_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PhoneNumberResponse:
    """Get a specific phone number.

    Args:
        phone_number_id: Phone number ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Phone number details
    """
    log = logger.bind(user_id=current_user.id, phone_number_id=phone_number_id)
    log.info("getting_phone_number")

    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == uuid.UUID(phone_number_id),
            PhoneNumber.user_id == user_uuid,
        )
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Phone number not found")

    workspace_name = None
    agent_name = None

    if record.workspace:
        workspace_name = record.workspace.name
    if record.assigned_agent:
        agent_name = record.assigned_agent.name

    return PhoneNumberResponse(
        id=str(record.id),
        phone_number=record.phone_number,
        friendly_name=record.friendly_name,
        provider=record.provider,
        provider_id=record.provider_id,
        workspace_id=str(record.workspace_id) if record.workspace_id else None,
        workspace_name=workspace_name,
        assigned_agent_id=str(record.assigned_agent_id) if record.assigned_agent_id else None,
        assigned_agent_name=agent_name,
        can_receive_calls=record.can_receive_calls,
        can_make_calls=record.can_make_calls,
        can_receive_sms=record.can_receive_sms,
        can_send_sms=record.can_send_sms,
        status=record.status,
        notes=record.notes,
        purchased_at=record.purchased_at,
        created_at=record.created_at,
    )


@router.post("", response_model=PhoneNumberResponse, status_code=201)
@limiter.limit("10/minute")  # Rate limit phone number creation
async def create_phone_number(
    create_request: CreatePhoneNumberRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PhoneNumberResponse:
    """Register a new phone number.

    Args:
        create_request: Phone number details
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Created phone number
    """
    log = logger.bind(user_id=current_user.id)
    log.info("creating_phone_number", phone_number=create_request.phone_number)

    user_uuid = user_id_to_uuid(current_user.id)

    phone_number = PhoneNumber(
        user_id=user_uuid,
        phone_number=create_request.phone_number,
        friendly_name=create_request.friendly_name,
        provider=create_request.provider,
        provider_id=create_request.provider_id,
        workspace_id=uuid.UUID(create_request.workspace_id) if create_request.workspace_id else None,
        can_receive_calls=create_request.can_receive_calls,
        can_make_calls=create_request.can_make_calls,
        can_receive_sms=create_request.can_receive_sms,
        can_send_sms=create_request.can_send_sms,
        notes=create_request.notes,
    )

    db.add(phone_number)
    await db.commit()
    await db.refresh(phone_number)

    return PhoneNumberResponse(
        id=str(phone_number.id),
        phone_number=phone_number.phone_number,
        friendly_name=phone_number.friendly_name,
        provider=phone_number.provider,
        provider_id=phone_number.provider_id,
        workspace_id=str(phone_number.workspace_id) if phone_number.workspace_id else None,
        workspace_name=None,
        assigned_agent_id=None,
        assigned_agent_name=None,
        can_receive_calls=phone_number.can_receive_calls,
        can_make_calls=phone_number.can_make_calls,
        can_receive_sms=phone_number.can_receive_sms,
        can_send_sms=phone_number.can_send_sms,
        status=phone_number.status,
        notes=phone_number.notes,
        purchased_at=phone_number.purchased_at,
        created_at=phone_number.created_at,
    )


@router.put("/{phone_number_id}", response_model=PhoneNumberResponse)
@limiter.limit("30/minute")  # Rate limit phone number updates
async def update_phone_number(
    phone_number_id: str,
    update_request: UpdatePhoneNumberRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PhoneNumberResponse:
    """Update a phone number.

    Args:
        phone_number_id: Phone number ID
        update_request: Update details
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated phone number
    """
    log = logger.bind(user_id=current_user.id, phone_number_id=phone_number_id)
    log.info("updating_phone_number")

    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == uuid.UUID(phone_number_id),
            PhoneNumber.user_id == user_uuid,
        )
    )
    phone_number = result.scalar_one_or_none()

    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")

    # Update fields
    if update_request.friendly_name is not None:
        phone_number.friendly_name = update_request.friendly_name
    if update_request.workspace_id is not None:
        phone_number.workspace_id = (
            uuid.UUID(update_request.workspace_id) if update_request.workspace_id else None
        )
    if update_request.assigned_agent_id is not None:
        phone_number.assigned_agent_id = (
            uuid.UUID(update_request.assigned_agent_id) if update_request.assigned_agent_id else None
        )
    if update_request.status is not None:
        phone_number.status = update_request.status
    if update_request.notes is not None:
        phone_number.notes = update_request.notes

    await db.commit()
    await db.refresh(phone_number)

    workspace_name = None
    agent_name = None

    if phone_number.workspace:
        workspace_name = phone_number.workspace.name
    if phone_number.assigned_agent:
        agent_name = phone_number.assigned_agent.name

    return PhoneNumberResponse(
        id=str(phone_number.id),
        phone_number=phone_number.phone_number,
        friendly_name=phone_number.friendly_name,
        provider=phone_number.provider,
        provider_id=phone_number.provider_id,
        workspace_id=str(phone_number.workspace_id) if phone_number.workspace_id else None,
        workspace_name=workspace_name,
        assigned_agent_id=str(phone_number.assigned_agent_id)
        if phone_number.assigned_agent_id
        else None,
        assigned_agent_name=agent_name,
        can_receive_calls=phone_number.can_receive_calls,
        can_make_calls=phone_number.can_make_calls,
        can_receive_sms=phone_number.can_receive_sms,
        can_send_sms=phone_number.can_send_sms,
        status=phone_number.status,
        notes=phone_number.notes,
        purchased_at=phone_number.purchased_at,
        created_at=phone_number.created_at,
    )


@router.delete("/{phone_number_id}", status_code=204)
@limiter.limit("10/minute")  # Rate limit phone number deletion
async def delete_phone_number(
    phone_number_id: str,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a phone number.

    Args:
        phone_number_id: Phone number ID
        current_user: Authenticated user
        db: Database session
    """
    log = logger.bind(user_id=current_user.id, phone_number_id=phone_number_id)
    log.info("deleting_phone_number")

    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(PhoneNumber).where(
            PhoneNumber.id == uuid.UUID(phone_number_id),
            PhoneNumber.user_id == user_uuid,
        )
    )
    phone_number = result.scalar_one_or_none()

    if not phone_number:
        raise HTTPException(status_code=404, detail="Phone number not found")

    await db.delete(phone_number)
    await db.commit()
