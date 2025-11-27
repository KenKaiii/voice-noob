"""Telephony API routes for Twilio and Telnyx integration.

This module provides:
- Webhook endpoints for inbound calls (Twilio/Telnyx)
- Phone number management (list, search, buy, release)
- Outbound call initiation
- Call status callbacks
- WebSocket endpoint for telephony media streaming
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_user_api_keys
from app.core.auth import CurrentUser, user_id_to_uuid
from app.db.session import get_db
from app.models.agent import Agent
from app.models.call_record import CallDirection, CallRecord, CallStatus
from app.services.telephony.telnyx_service import TelnyxService
from app.services.telephony.twilio_service import TwilioService

if TYPE_CHECKING:
    from app.services.telephony.base import PhoneNumber

router = APIRouter(prefix="/api/v1/telephony", tags=["telephony"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

logger = structlog.get_logger()


# =============================================================================
# Pydantic Models
# =============================================================================


class PhoneNumberResponse(BaseModel):
    """Phone number response."""

    id: str
    phone_number: str
    friendly_name: str | None = None
    provider: str
    capabilities: dict[str, bool] | None = None
    assigned_agent_id: str | None = None


class SearchPhoneNumbersRequest(BaseModel):
    """Request to search for phone numbers."""

    provider: str  # "twilio" or "telnyx"
    country: str = "US"
    area_code: str | None = None
    contains: str | None = None
    limit: int = 10


class PurchasePhoneNumberRequest(BaseModel):
    """Request to purchase a phone number."""

    provider: str  # "twilio" or "telnyx"
    phone_number: str


class InitiateCallRequest(BaseModel):
    """Request to initiate an outbound call."""

    to_number: str
    from_number: str
    agent_id: str


class CallResponse(BaseModel):
    """Call response."""

    call_id: str
    call_control_id: str | None = None
    from_number: str
    to_number: str
    direction: str
    status: str
    agent_id: str | None = None


# =============================================================================
# Helper Functions
# =============================================================================


async def get_twilio_service(user_id: int, db: AsyncSession) -> TwilioService | None:
    """Get Twilio service for a user."""
    user_uuid = user_id_to_uuid(user_id)
    user_settings = await get_user_api_keys(user_uuid, db)

    if (
        not user_settings
        or not user_settings.twilio_account_sid
        or not user_settings.twilio_auth_token
    ):
        return None

    return TwilioService(
        account_sid=user_settings.twilio_account_sid,
        auth_token=user_settings.twilio_auth_token,
    )


async def get_telnyx_service(user_id: int, db: AsyncSession) -> TelnyxService | None:
    """Get Telnyx service for a user."""
    user_uuid = user_id_to_uuid(user_id)
    user_settings = await get_user_api_keys(user_uuid, db)

    if not user_settings or not user_settings.telnyx_api_key:
        return None

    return TelnyxService(
        api_key=user_settings.telnyx_api_key,
        public_key=user_settings.telnyx_public_key,
    )


async def get_agent_by_phone_number(phone_number: str, db: AsyncSession) -> Agent | None:
    """Find agent by assigned phone number."""
    # Remove + prefix for comparison if present
    normalized = phone_number.lstrip("+")

    result = await db.execute(
        select(Agent).where(
            (Agent.phone_number_id == phone_number)
            | (Agent.phone_number_id == normalized)
            | (Agent.phone_number_id == f"+{normalized}")
        )
    )
    return result.scalar_one_or_none()


# =============================================================================
# Phone Number Management Endpoints
# =============================================================================


@router.get("/phone-numbers", response_model=list[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    provider: str = Query("twilio", description="Provider: twilio or telnyx"),
) -> list[PhoneNumberResponse]:
    """List all phone numbers for the user's account.

    Args:
        provider: Telephony provider (twilio or telnyx)
        current_user: Authenticated user
        db: Database session

    Returns:
        List of phone numbers
    """
    log = logger.bind(user_id=current_user.id, provider=provider)
    log.info("listing_phone_numbers")

    numbers: list[PhoneNumber] = []

    if provider == "twilio":
        twilio_service = await get_twilio_service(current_user.id, db)
        if not twilio_service:
            raise HTTPException(
                status_code=400,
                detail="Twilio credentials not configured. Please add them in Settings.",
            )
        numbers = await twilio_service.list_phone_numbers()

    elif provider == "telnyx":
        telnyx_service = await get_telnyx_service(current_user.id, db)
        if not telnyx_service:
            raise HTTPException(
                status_code=400,
                detail="Telnyx credentials not configured. Please add them in Settings.",
            )
        numbers = await telnyx_service.list_phone_numbers()

    else:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'twilio' or 'telnyx'.")

    # Map to response model
    return [
        PhoneNumberResponse(
            id=n.id,
            phone_number=n.phone_number,
            friendly_name=n.friendly_name,
            provider=n.provider,
            capabilities=n.capabilities,
            assigned_agent_id=n.assigned_agent_id,
        )
        for n in numbers
    ]


@router.post("/phone-numbers/search", response_model=list[PhoneNumberResponse])
async def search_phone_numbers(
    request: SearchPhoneNumbersRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[PhoneNumberResponse]:
    """Search for available phone numbers to purchase.

    Args:
        request: Search parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        List of available phone numbers
    """
    log = logger.bind(user_id=current_user.id, provider=request.provider)
    log.info("searching_phone_numbers", country=request.country, area_code=request.area_code)

    numbers: list[PhoneNumber] = []

    if request.provider == "twilio":
        twilio_service = await get_twilio_service(current_user.id, db)
        if not twilio_service:
            raise HTTPException(
                status_code=400,
                detail="Twilio credentials not configured. Please add them in Settings.",
            )
        numbers = await twilio_service.search_phone_numbers(
            country=request.country,
            area_code=request.area_code,
            contains=request.contains,
            limit=request.limit,
        )

    elif request.provider == "telnyx":
        telnyx_service = await get_telnyx_service(current_user.id, db)
        if not telnyx_service:
            raise HTTPException(
                status_code=400,
                detail="Telnyx credentials not configured. Please add them in Settings.",
            )
        numbers = await telnyx_service.search_phone_numbers(
            country=request.country,
            area_code=request.area_code,
            contains=request.contains,
            limit=request.limit,
        )

    else:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'twilio' or 'telnyx'.")

    return [
        PhoneNumberResponse(
            id=n.id,
            phone_number=n.phone_number,
            friendly_name=n.friendly_name,
            provider=n.provider,
            capabilities=n.capabilities,
        )
        for n in numbers
    ]


@router.post("/phone-numbers/purchase", response_model=PhoneNumberResponse)
async def purchase_phone_number(
    request: PurchasePhoneNumberRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PhoneNumberResponse:
    """Purchase a phone number.

    Args:
        request: Purchase request with provider and phone number
        current_user: Authenticated user
        db: Database session

    Returns:
        Purchased phone number details
    """
    log = logger.bind(user_id=current_user.id, provider=request.provider)
    log.info("purchasing_phone_number", phone_number=request.phone_number)

    number: PhoneNumber

    if request.provider == "twilio":
        twilio_service = await get_twilio_service(current_user.id, db)
        if not twilio_service:
            raise HTTPException(
                status_code=400,
                detail="Twilio credentials not configured. Please add them in Settings.",
            )
        number = await twilio_service.purchase_phone_number(request.phone_number)

    elif request.provider == "telnyx":
        telnyx_service = await get_telnyx_service(current_user.id, db)
        if not telnyx_service:
            raise HTTPException(
                status_code=400,
                detail="Telnyx credentials not configured. Please add them in Settings.",
            )
        number = await telnyx_service.purchase_phone_number(request.phone_number)

    else:
        raise HTTPException(status_code=400, detail="Invalid provider. Use 'twilio' or 'telnyx'.")

    return PhoneNumberResponse(
        id=number.id,
        phone_number=number.phone_number,
        friendly_name=number.friendly_name,
        provider=number.provider,
        capabilities=number.capabilities,
    )


@router.delete("/phone-numbers/{phone_number_id}")
async def release_phone_number(
    phone_number_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    provider: str = Query(..., description="Provider: twilio or telnyx"),
) -> dict[str, str]:
    """Release a phone number.

    Args:
        phone_number_id: Phone number ID to release
        provider: Telephony provider
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message
    """
    log = logger.bind(user_id=current_user.id, provider=provider)
    log.info("releasing_phone_number", phone_number_id=phone_number_id)

    success = False

    if provider == "twilio":
        twilio_service = await get_twilio_service(current_user.id, db)
        if not twilio_service:
            raise HTTPException(
                status_code=400,
                detail="Twilio credentials not configured.",
            )
        success = await twilio_service.release_phone_number(phone_number_id)

    elif provider == "telnyx":
        telnyx_service = await get_telnyx_service(current_user.id, db)
        if not telnyx_service:
            raise HTTPException(
                status_code=400,
                detail="Telnyx credentials not configured.",
            )
        success = await telnyx_service.release_phone_number(phone_number_id)

    else:
        raise HTTPException(status_code=400, detail="Invalid provider.")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to release phone number.")

    return {"message": "Phone number released successfully"}


# =============================================================================
# Outbound Call Endpoints
# =============================================================================


@router.post("/calls", response_model=CallResponse)
async def initiate_call(
    request: InitiateCallRequest,
    http_request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CallResponse:
    """Initiate an outbound call.

    Args:
        request: Call initiation request
        http_request: HTTP request for building webhook URLs
        current_user: Authenticated user
        db: Database session

    Returns:
        Call details
    """
    log = logger.bind(user_id=current_user.id, agent_id=request.agent_id)
    log.info("initiating_call", to=request.to_number, from_=request.from_number)

    # Load agent to get provider preference
    result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(request.agent_id)))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine provider from agent's phone number configuration
    # Default to Telnyx if not specified
    provider = "telnyx"

    # Try Telnyx first
    telnyx_service = await get_telnyx_service(current_user.id, db)
    twilio_service = await get_twilio_service(current_user.id, db)

    if not telnyx_service and not twilio_service:
        raise HTTPException(
            status_code=400,
            detail="No telephony provider configured. Please add Twilio or Telnyx credentials in Settings.",
        )

    # Build webhook URL
    base_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhooks/{'telnyx' if telnyx_service else 'twilio'}/answer?agent_id={request.agent_id}"

    if telnyx_service:
        provider = "telnyx"
        call_info = await telnyx_service.initiate_call(
            to_number=request.to_number,
            from_number=request.from_number,
            webhook_url=webhook_url,
            agent_id=request.agent_id,
        )
    elif twilio_service:
        provider = "twilio"
        call_info = await twilio_service.initiate_call(
            to_number=request.to_number,
            from_number=request.from_number,
            webhook_url=webhook_url,
            agent_id=request.agent_id,
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize telephony service")

    log.info("call_initiated", call_id=call_info.call_id, provider=provider)

    # Create call record for outbound call
    call_record = CallRecord(
        user_id=user_id_to_uuid(current_user.id),
        provider=provider,
        provider_call_id=call_info.call_id,
        agent_id=uuid.UUID(request.agent_id),
        direction=CallDirection.OUTBOUND.value,
        status=CallStatus.INITIATED.value,
        from_number=request.from_number,
        to_number=request.to_number,
    )
    db.add(call_record)
    await db.commit()
    log.info("call_record_created", record_id=str(call_record.id))

    return CallResponse(
        call_id=call_info.call_id,
        call_control_id=call_info.call_control_id,
        from_number=call_info.from_number,
        to_number=call_info.to_number,
        direction=call_info.direction.value,
        status=call_info.status.value,
        agent_id=call_info.agent_id,
    )


@router.post("/calls/{call_id}/hangup")
async def hangup_call(
    call_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    provider: str = Query(..., description="Provider: twilio or telnyx"),
) -> dict[str, str]:
    """Hang up an active call.

    Args:
        call_id: Call ID to hang up
        provider: Telephony provider
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message
    """
    log = logger.bind(user_id=current_user.id, call_id=call_id, provider=provider)
    log.info("hanging_up_call")

    success = False

    if provider == "twilio":
        twilio_service = await get_twilio_service(current_user.id, db)
        if twilio_service:
            success = await twilio_service.hangup_call(call_id)

    elif provider == "telnyx":
        telnyx_service = await get_telnyx_service(current_user.id, db)
        if telnyx_service:
            success = await telnyx_service.hangup_call(call_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to hang up call")

    return {"message": "Call ended successfully"}


# =============================================================================
# Twilio Webhook Endpoints
# =============================================================================


@webhook_router.post("/twilio/voice", response_class=HTMLResponse)
async def twilio_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    call_sid: str = Form(default="", alias="CallSid"),
    from_number: str = Form(default="", alias="From"),
    to_number: str = Form(default="", alias="To"),
    call_status: str = Form(default="", alias="CallStatus"),
) -> Response:
    """Handle incoming Twilio voice calls.

    This webhook is called when a call comes in to a Twilio phone number.
    It returns TwiML to connect the call to our WebSocket for AI handling.
    """
    log = logger.bind(
        webhook="twilio_voice",
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        status=call_status,
    )
    log.info("twilio_incoming_call")

    # Find agent by phone number
    agent = await get_agent_by_phone_number(to_number, db)
    agent_id = str(agent.id) if agent else None

    if not agent:
        log.warning("no_agent_for_number", to_number=to_number)
        # Return TwiML that says no agent is available
        return Response(
            content="""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, no agent is configured for this number. Goodbye.</Say>
    <Hangup/>
</Response>""",
            media_type="application/xml",
        )

    # Create call record for inbound call
    call_record = CallRecord(
        user_id=agent.user_id,
        provider="twilio",
        provider_call_id=call_sid,
        agent_id=agent.id,
        direction=CallDirection.INBOUND.value,
        status=CallStatus.RINGING.value,
        from_number=from_number,
        to_number=to_number,
    )
    db.add(call_record)
    await db.commit()
    log.info("call_record_created", record_id=str(call_record.id))

    # Build WebSocket URL for media streaming
    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("http://", "wss://").replace("https://", "wss://")
    stream_url = f"{ws_url}/ws/telephony/twilio/{agent_id}"

    # Generate TwiML to connect to our WebSocket
    twilio_service = TwilioService("", "")  # Just need TwiML generation
    twiml = twilio_service.generate_answer_response(stream_url, agent_id)

    log.info("twilio_twiml_generated", agent_id=agent_id)

    return Response(content=twiml, media_type="application/xml")


@webhook_router.post("/twilio/status")
async def twilio_status_callback(
    db: AsyncSession = Depends(get_db),
    call_sid: str = Form(default="", alias="CallSid"),
    call_status: str = Form(default="", alias="CallStatus"),
    call_duration: str = Form(default="0", alias="CallDuration"),
    from_number: str = Form(default="", alias="From"),
    to_number: str = Form(default="", alias="To"),
) -> dict[str, str]:
    """Handle Twilio call status callbacks.

    Called when call status changes (initiated, ringing, answered, completed).
    """
    log = logger.bind(
        webhook="twilio_status",
        call_sid=call_sid,
        status=call_status,
        duration=call_duration,
    )
    log.info("twilio_status_update")

    # Find and update call record
    result = await db.execute(select(CallRecord).where(CallRecord.provider_call_id == call_sid))
    call_record = result.scalar_one_or_none()

    if call_record:
        # Map Twilio status to our status
        status_map = {
            "initiated": CallStatus.INITIATED.value,
            "ringing": CallStatus.RINGING.value,
            "in-progress": CallStatus.IN_PROGRESS.value,
            "completed": CallStatus.COMPLETED.value,
            "busy": CallStatus.BUSY.value,
            "failed": CallStatus.FAILED.value,
            "no-answer": CallStatus.NO_ANSWER.value,
            "canceled": CallStatus.CANCELED.value,
        }

        call_record.status = status_map.get(call_status, call_status)

        # Update timestamps based on status
        if call_status == "in-progress" and not call_record.answered_at:
            call_record.answered_at = datetime.now(UTC)
        elif call_status in ("completed", "busy", "failed", "no-answer", "canceled"):
            call_record.ended_at = datetime.now(UTC)
            if call_duration:
                call_record.duration_seconds = int(call_duration)

        await db.commit()
        log.info("call_record_updated", record_id=str(call_record.id), status=call_status)
    else:
        log.warning("call_record_not_found", call_sid=call_sid)

    return {"status": "received"}


@webhook_router.post("/twilio/answer", response_class=HTMLResponse)
async def twilio_answer_webhook(
    request: Request,
    agent_id: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Handle Twilio outbound call connection.

    Called when an outbound call is answered by the recipient.
    Returns TwiML to connect to our WebSocket.
    """
    log = logger.bind(webhook="twilio_answer", agent_id=agent_id)
    log.info("twilio_outbound_answered")

    # Build WebSocket URL
    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("http://", "wss://").replace("https://", "wss://")
    stream_url = f"{ws_url}/ws/telephony/twilio/{agent_id}"

    twilio_service = TwilioService("", "")
    twiml = twilio_service.generate_answer_response(stream_url, agent_id)

    return Response(content=twiml, media_type="application/xml")


# =============================================================================
# Telnyx Webhook Endpoints
# =============================================================================


@webhook_router.post("/telnyx/voice", response_class=HTMLResponse)
async def telnyx_voice_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Handle incoming Telnyx voice calls.

    This webhook is called when a call comes in to a Telnyx phone number.
    It returns TeXML to connect the call to our WebSocket for AI handling.
    """
    body = await request.json()
    data = body.get("data", {})
    payload = data.get("payload", {})

    call_control_id = payload.get("call_control_id", "")
    from_number = payload.get("from", "")
    to_number = payload.get("to", "")
    event_type = data.get("event_type", "")

    log = logger.bind(
        webhook="telnyx_voice",
        call_control_id=call_control_id,
        from_number=from_number,
        to_number=to_number,
        event_type=event_type,
    )
    log.info("telnyx_incoming_call")

    # Find agent by phone number
    agent = await get_agent_by_phone_number(to_number, db)
    agent_id = str(agent.id) if agent else None

    if not agent:
        log.warning("no_agent_for_number", to_number=to_number)
        return Response(
            content="""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Sorry, no agent is configured for this number. Goodbye.</Say>
    <Hangup/>
</Response>""",
            media_type="application/xml",
        )

    # Create call record for inbound call
    call_record = CallRecord(
        user_id=agent.user_id,
        provider="telnyx",
        provider_call_id=call_control_id,
        agent_id=agent.id,
        direction=CallDirection.INBOUND.value,
        status=CallStatus.RINGING.value,
        from_number=from_number,
        to_number=to_number,
    )
    db.add(call_record)
    await db.commit()
    log.info("call_record_created", record_id=str(call_record.id))

    # Build WebSocket URL
    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("http://", "wss://").replace("https://", "wss://")
    stream_url = f"{ws_url}/ws/telephony/telnyx/{agent_id}"

    telnyx_service = TelnyxService("")
    texml = telnyx_service.generate_answer_response(stream_url, agent_id)

    log.info("telnyx_texml_generated", agent_id=agent_id)

    return Response(content=texml, media_type="application/xml")


@webhook_router.post("/telnyx/answer", response_class=HTMLResponse)
async def telnyx_answer_webhook(
    request: Request,
    agent_id: str = Query(default=""),
) -> Response:
    """Handle Telnyx outbound call connection.

    Called when an outbound call is answered by the recipient.
    Returns TeXML to connect to our WebSocket.
    """
    log = logger.bind(webhook="telnyx_answer", agent_id=agent_id)
    log.info("telnyx_outbound_answered")

    # Build WebSocket URL
    base_url = str(request.base_url).rstrip("/")
    ws_url = base_url.replace("http://", "wss://").replace("https://", "wss://")
    stream_url = f"{ws_url}/ws/telephony/telnyx/{agent_id}"

    telnyx_service = TelnyxService("")
    texml = telnyx_service.generate_answer_response(stream_url, agent_id)

    return Response(content=texml, media_type="application/xml")


@webhook_router.post("/telnyx/status")
async def telnyx_status_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Handle Telnyx call status callbacks.

    Called when call events occur (call.initiated, call.answered, call.hangup, etc).
    """
    body = await request.json()
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")

    log = logger.bind(
        webhook="telnyx_status",
        event_type=event_type,
        call_control_id=call_control_id,
    )
    log.info("telnyx_status_update")

    # Find and update call record
    result = await db.execute(
        select(CallRecord).where(CallRecord.provider_call_id == call_control_id)
    )
    call_record = result.scalar_one_or_none()

    if call_record:
        # Map Telnyx event types to our status
        event_status_map = {
            "call.initiated": CallStatus.INITIATED.value,
            "call.ringing": CallStatus.RINGING.value,
            "call.answered": CallStatus.IN_PROGRESS.value,
            "call.hangup": CallStatus.COMPLETED.value,
            "call.machine.detection.ended": None,  # Don't change status
        }

        new_status = event_status_map.get(event_type)
        if new_status:
            call_record.status = new_status

        # Update timestamps based on event
        if event_type == "call.answered" and not call_record.answered_at:
            call_record.answered_at = datetime.now(UTC)
        elif event_type == "call.hangup":
            call_record.ended_at = datetime.now(UTC)
            # Calculate duration if we have answered_at
            if call_record.answered_at:
                duration = (call_record.ended_at - call_record.answered_at).total_seconds()
                call_record.duration_seconds = int(duration)

            # Check hangup cause for failed calls
            hangup_cause = payload.get("hangup_cause", "")
            if hangup_cause == "USER_BUSY":
                call_record.status = CallStatus.BUSY.value
            elif hangup_cause == "NO_ANSWER":
                call_record.status = CallStatus.NO_ANSWER.value
            elif hangup_cause in ("CALL_REJECTED", "ORIGINATOR_CANCEL"):
                call_record.status = CallStatus.CANCELED.value
            elif hangup_cause and hangup_cause not in ("NORMAL_CLEARING", "NORMAL_RELEASE"):
                call_record.status = CallStatus.FAILED.value

        await db.commit()
        log.info("call_record_updated", record_id=str(call_record.id), event=event_type)
    else:
        log.warning("call_record_not_found", call_control_id=call_control_id)

    return {"status": "received"}
