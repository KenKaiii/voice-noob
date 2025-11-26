"""WebRTC and WebSocket API for GPT Realtime voice calls."""

import asyncio
import contextlib
import json
import uuid
from http import HTTPStatus
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_current_user_id, get_user_api_keys
from app.core.config import settings
from app.db.session import get_db
from app.models.agent import Agent
from app.services.gpt_realtime import GPTRealtimeSession
from app.services.tools.registry import ToolRegistry

router = APIRouter(prefix="/ws", tags=["realtime"])
webrtc_router = APIRouter(prefix="/api/v1/realtime", tags=["realtime-webrtc"])
logger = structlog.get_logger()


@router.websocket("/realtime/{agent_id}")
async def realtime_websocket(
    websocket: WebSocket,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """WebSocket endpoint for GPT Realtime voice calls.

    This endpoint:
    1. Accepts WebSocket connection from client (phone/browser)
    2. Loads agent configuration and enabled integrations
    3. Initializes GPT Realtime session with internal tools
    4. Bridges audio between client and GPT Realtime
    5. Routes tool calls to internal tool handlers

    Args:
        websocket: WebSocket connection
        agent_id: Agent UUID
        db: Database session
    """
    session_id = str(uuid.uuid4())
    client_logger = logger.bind(
        endpoint="realtime_websocket",
        agent_id=agent_id,
        session_id=session_id,
    )

    await websocket.accept()
    client_logger.info("websocket_connected")

    try:
        # Load agent configuration
        result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        agent = result.scalar_one_or_none()

        if not agent:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": f"Agent {agent_id} not found",
                }
            )
            await websocket.close()
            return

        if not agent.is_active:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "Agent is not active",
                }
            )
            await websocket.close()
            return

        # Check if Premium tier (GPT Realtime only for Premium)
        if agent.pricing_tier != "premium":
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "GPT Realtime only available for Premium tier agents",
                }
            )
            await websocket.close()
            return

        client_logger.info(
            "agent_loaded",
            agent_name=agent.name,
            tier=agent.pricing_tier,
            tools_count=len(agent.enabled_tools),
        )

        # Build agent config for GPT Realtime
        agent_config = {
            "system_prompt": agent.system_prompt,
            "enabled_tools": agent.enabled_tools,
            "language": agent.language,
        }

        # Initialize GPT Realtime session with internal tools
        async with GPTRealtimeSession(
            db=db,
            user_id=agent.user_id,
            agent_config=agent_config,
            session_id=session_id,
        ) as realtime_session:
            # Send ready signal to client
            await websocket.send_json(
                {
                    "type": "session.ready",
                    "session_id": session_id,
                    "agent": {
                        "id": str(agent.id),
                        "name": agent.name,
                        "tier": agent.pricing_tier,
                    },
                }
            )

            # Start bidirectional streaming
            await _bridge_audio_streams(
                client_ws=websocket,
                realtime_session=realtime_session,
                logger=client_logger,
            )

    except WebSocketDisconnect:
        client_logger.info("websocket_disconnected")
    except Exception as e:
        client_logger.exception("websocket_error", error=str(e))
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(e),
                }
            )
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
        client_logger.info("websocket_closed")


async def _bridge_audio_streams(
    client_ws: WebSocket,
    realtime_session: GPTRealtimeSession,
    logger: Any,
) -> None:
    """Bridge audio streams between client and GPT Realtime.

    Args:
        client_ws: Client WebSocket connection
        realtime_session: GPT Realtime session
        logger: Structured logger
    """

    async def client_to_realtime() -> None:
        """Forward messages from client to GPT Realtime."""
        try:
            while True:
                # Receive from client
                logger.debug("waiting_for_client_message")
                message = await client_ws.receive()
                logger.debug("client_message_received", message_type=message.get("type"))

                if message["type"] == "websocket.disconnect":
                    logger.info("client_initiated_disconnect")
                    break

                # Forward to Realtime API
                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        # Audio data
                        audio_size = len(message["bytes"])
                        logger.debug("client_audio_received", size_bytes=audio_size)
                        await realtime_session.send_audio(message["bytes"])
                    elif "text" in message:
                        # JSON event
                        data = json.loads(message["text"])
                        logger.info("client_event", event_type=data.get("type"), data=data)

        except WebSocketDisconnect:
            logger.info("client_disconnected_exception")
        except Exception as e:
            logger.exception("client_to_realtime_error", error=str(e), error_type=type(e).__name__)

    async def realtime_to_client() -> None:
        """Forward messages from GPT Realtime to client."""
        try:
            if not realtime_session.connection:
                logger.error("no_realtime_connection")
                return

            logger.info("starting_realtime_to_client_loop")
            async for event in realtime_session.connection:
                try:
                    event_type = event.type

                    logger.info("realtime_event", event_type=event_type)

                    # Handle tool calls internally
                    if event_type == "response.function_call_arguments.done":
                        logger.info(
                            "handling_function_call", call_id=event.call_id, name=event.name
                        )
                        await realtime_session.handle_function_call_event(event)

                    # Forward events to client as JSON
                    await client_ws.send_json(
                        {
                            "type": event_type,
                            "event": event.model_dump() if hasattr(event, "model_dump") else {},
                        }
                    )
                    logger.debug("event_forwarded_to_client", event_type=event_type)

                except Exception as e:
                    logger.exception(
                        "event_forward_error", error=str(e), error_type=type(e).__name__
                    )

        except Exception as e:
            logger.exception("realtime_to_client_error", error=str(e), error_type=type(e).__name__)

    # Run both directions concurrently
    await asyncio.gather(
        client_to_realtime(),
        realtime_to_client(),
        return_exceptions=True,
    )


# =============================================================================
# WebRTC Endpoints for GPT Realtime
# =============================================================================


@webrtc_router.post("/session/{agent_id}")
async def create_webrtc_session(
    agent_id: str,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Create a WebRTC session for GPT Realtime API.

    This endpoint implements the unified interface approach:
    1. Receives SDP offer from client
    2. Loads agent configuration and builds session config with tools
    3. Forwards to OpenAI Realtime API
    4. Returns SDP answer to client

    Args:
        agent_id: Agent UUID
        request: HTTP request containing SDP offer
        user_id: Current user ID
        db: Database session

    Returns:
        SDP answer from OpenAI
    """
    session_logger = logger.bind(
        endpoint="webrtc_session",
        agent_id=agent_id,
        user_id=str(user_id),
    )

    session_logger.info("webrtc_session_requested")

    # Get SDP offer from request body
    sdp_offer = await request.body()
    if not sdp_offer:
        raise HTTPException(status_code=400, detail="SDP offer required in request body")

    # Load agent configuration
    result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    if not agent.is_active:
        raise HTTPException(status_code=400, detail="Agent is not active")

    if agent.pricing_tier != "premium":
        raise HTTPException(
            status_code=400, detail="WebRTC Realtime only available for Premium tier agents"
        )

    session_logger.info(
        "agent_loaded",
        agent_name=agent.name,
        tier=agent.pricing_tier,
        tools_count=len(agent.enabled_tools),
    )

    # Get OpenAI API key
    user_settings = await get_user_api_keys(user_id, db)
    api_key = None
    if user_settings and user_settings.openai_api_key:
        api_key = user_settings.openai_api_key
        session_logger.info("using_user_openai_key")
    elif settings.OPENAI_API_KEY:
        api_key = settings.OPENAI_API_KEY
        session_logger.info("using_global_openai_key")
    else:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Please add it in Settings.",
        )

    # Build tool definitions
    tool_registry = ToolRegistry(db, user_id)
    tools = tool_registry.get_all_tool_definitions(agent.enabled_tools)

    # Build session configuration for OpenAI Realtime
    session_config: dict[str, Any] = {
        "type": "realtime",
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "instructions": agent.system_prompt or "You are a helpful voice assistant.",
        "voice": "shimmer",
        "input_audio_transcription": {"model": "whisper-1"},
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500,
        },
    }

    # Add tools if any are enabled
    if tools:
        session_config["tools"] = tools
        session_config["tool_choice"] = "auto"

    session_logger.info(
        "creating_openai_session",
        model=session_config["model"],
        tool_count=len(tools),
    )

    # Create multipart form data for OpenAI API
    try:
        async with httpx.AsyncClient() as client:
            # Prepare multipart form - properly typed for httpx
            files: list[tuple[str, tuple[str, bytes | str, str]]] = [
                ("sdp", ("offer.sdp", sdp_offer, "application/sdp")),
                ("session", ("session.json", json.dumps(session_config), "application/json")),
            ]

            response = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                timeout=30.0,
            )

            if response.status_code != HTTPStatus.OK:
                session_logger.error(
                    "openai_api_error",
                    status_code=response.status_code,
                    response_text=response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenAI API error: {response.text}",
                )

            sdp_answer = response.text
            session_logger.info("webrtc_session_created")

            return Response(content=sdp_answer, media_type="application/sdp")

    except httpx.RequestError as e:
        session_logger.exception("openai_request_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect to OpenAI: {e!s}") from e


@webrtc_router.get("/token/{agent_id}")
async def get_ephemeral_token(
    agent_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get an ephemeral token for OpenAI Realtime API WebRTC connection.

    This endpoint is used by the OpenAI Agents SDK to establish WebRTC connections.
    It returns a short-lived ephemeral API key that can be used client-side.

    Args:
        agent_id: Agent UUID
        user_id: Current user ID
        db: Database session

    Returns:
        Ephemeral token response with client_secret value and session config
    """
    token_logger = logger.bind(
        endpoint="ephemeral_token",
        agent_id=agent_id,
        user_id=str(user_id),
    )

    token_logger.info("ephemeral_token_requested")

    # Load agent configuration
    result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    if not agent.is_active:
        raise HTTPException(status_code=400, detail="Agent is not active")

    if agent.pricing_tier != "premium":
        raise HTTPException(
            status_code=400, detail="WebRTC Realtime only available for Premium tier agents"
        )

    # Get OpenAI API key
    user_settings = await get_user_api_keys(user_id, db)
    api_key = None
    if user_settings and user_settings.openai_api_key:
        api_key = user_settings.openai_api_key
        token_logger.info("using_user_openai_key")
    elif settings.OPENAI_API_KEY:
        api_key = settings.OPENAI_API_KEY
        token_logger.info("using_global_openai_key")
    else:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Please add it in Settings.",
        )

    # Build minimal session configuration for ephemeral token request
    # The SDK will configure instructions, voice, tools etc. after connection via data channel
    # Using the latest 2025 model as per official OpenAI examples
    session_config: dict[str, Any] = {
        "model": "gpt-4o-realtime-preview-2025-06-03",
        "modalities": ["audio", "text"],
        "voice": "alloy",
    }

    token_logger.info(
        "requesting_ephemeral_token",
        model=session_config["model"],
    )

    # Request ephemeral token from OpenAI Realtime sessions endpoint
    # The session_config is sent directly as the request body (not wrapped)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=session_config,
                timeout=30.0,
            )

            if not response.is_success:
                token_logger.error(
                    "openai_token_error",
                    status_code=response.status_code,
                    response_text=response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenAI API error: {response.text}",
                )

            token_data = response.json()
            token_logger.info("ephemeral_token_created")

            # Build tool definitions for the agent
            tool_registry = ToolRegistry(db, user_id)
            tools = tool_registry.get_all_tool_definitions(agent.enabled_tools)

            token_logger.info(
                "tools_prepared",
                tool_count=len(tools),
                enabled_tools=agent.enabled_tools,
            )

            # Return token data with agent info and tools
            return {
                "client_secret": token_data.get("client_secret", {}),
                "agent": {
                    "id": str(agent.id),
                    "name": agent.name,
                    "tier": agent.pricing_tier,
                    "system_prompt": agent.system_prompt,
                    "enabled_tools": agent.enabled_tools,
                },
                "session_config": session_config,
                "tools": tools,
            }

    except httpx.RequestError as e:
        token_logger.exception("openai_token_request_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect to OpenAI: {e!s}") from e
