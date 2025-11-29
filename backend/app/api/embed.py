"""Public embed API routes for embeddable voice widgets.

These endpoints are unauthenticated but protected by:
- Domain allowlisting (Origin header validation)
- Rate limiting
- Ephemeral session tokens
"""

import asyncio
import contextlib
import fnmatch
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.integrations import get_workspace_integrations
from app.db.session import get_db
from app.models.agent import Agent
from app.services.gpt_realtime import GPTRealtimeSession

router = APIRouter(prefix="/api/public/embed", tags=["public-embed"])
ws_router = APIRouter(prefix="/ws/public/embed", tags=["public-embed-ws"])
logger = structlog.get_logger()

# Rate limiter for public endpoints
limiter = Limiter(key_func=get_remote_address)

# In-memory session store (in production, use Redis with TTL)
_embed_sessions: dict[str, dict[str, Any]] = {}
SESSION_EXPIRY_MINUTES = 5


class EmbedConfigResponse(BaseModel):
    """Public agent configuration for widget initialization."""

    public_id: str
    name: str
    greeting_message: str
    button_text: str
    theme: str
    position: str
    primary_color: str
    language: str
    voice: str


class EmbedSessionResponse(BaseModel):
    """Response for session creation."""

    session_id: str
    expires_at: str
    websocket_url: str


def validate_origin(origin: str | None, allowed_domains: list[str]) -> bool:
    """Validate that the Origin header matches allowed domains.

    Supports wildcards: "*.example.com" matches "app.example.com"
    Empty allowed_domains means all origins are allowed.

    Args:
        origin: The Origin header value
        allowed_domains: List of allowed domain patterns

    Returns:
        True if origin is allowed, False otherwise
    """
    if not allowed_domains:
        # Empty list means all origins allowed (for development/testing)
        return True

    if not origin:
        return False

    # Extract hostname from origin (e.g., "https://example.com" -> "example.com")
    try:
        from urllib.parse import urlparse

        parsed = urlparse(origin)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    # Check against each allowed domain pattern
    for pattern in allowed_domains:
        # Handle wildcard patterns
        if pattern.startswith("*."):
            # Convert "*.example.com" to fnmatch pattern
            fnmatch_pattern = f"*{pattern[1:]}"
            if fnmatch.fnmatch(hostname, fnmatch_pattern):
                return True
        elif hostname == pattern:
            return True

    return False


async def get_agent_by_public_id(
    public_id: str,
    db: AsyncSession,
) -> Agent | None:
    """Get agent by public ID."""
    result = await db.execute(select(Agent).where(Agent.public_id == public_id))
    return result.scalar_one_or_none()


@router.get("/{public_id}/config", response_model=EmbedConfigResponse)
async def get_embed_config(
    public_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    origin: str | None = Header(None),
) -> EmbedConfigResponse:
    """Get public agent configuration for widget initialization.

    This endpoint returns only the information needed to render the widget.
    It does NOT expose sensitive data like system prompts or API keys.
    """
    log = logger.bind(endpoint="embed_config", public_id=public_id, origin=origin)

    # Get agent
    agent = await get_agent_by_public_id(public_id, db)
    if not agent:
        log.warning("agent_not_found")
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.embed_enabled:
        log.warning("embed_disabled")
        raise HTTPException(status_code=403, detail="Embedding is disabled for this agent")

    if not agent.is_active:
        log.warning("agent_inactive")
        raise HTTPException(status_code=403, detail="Agent is not active")

    # Validate origin
    if not validate_origin(origin, agent.allowed_domains):
        log.warning("origin_not_allowed", allowed=agent.allowed_domains)
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # Extract embed settings with defaults
    embed_settings = agent.embed_settings or {}

    log.info("config_returned")

    return EmbedConfigResponse(
        public_id=public_id,
        name=agent.name,
        greeting_message=embed_settings.get("greeting_message", "Hi! How can I help you today?"),
        button_text=embed_settings.get("button_text", "Talk to us"),
        theme=embed_settings.get("theme", "auto"),
        position=embed_settings.get("position", "bottom-right"),
        primary_color=embed_settings.get("primary_color", "#6366f1"),
        language=agent.language,
        voice=agent.voice,
    )


@router.post("/{public_id}/session", response_model=EmbedSessionResponse)
async def create_embed_session(
    public_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    origin: str | None = Header(None),
) -> EmbedSessionResponse:
    """Create an ephemeral session for WebRTC/WebSocket connection.

    This creates a short-lived session token that can be used to
    establish a voice connection. The token expires after 5 minutes.
    """
    log = logger.bind(endpoint="embed_session", public_id=public_id, origin=origin)

    # Get agent
    agent = await get_agent_by_public_id(public_id, db)
    if not agent:
        log.warning("agent_not_found")
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.embed_enabled:
        log.warning("embed_disabled")
        raise HTTPException(status_code=403, detail="Embedding is disabled for this agent")

    if not agent.is_active:
        log.warning("agent_inactive")
        raise HTTPException(status_code=403, detail="Agent is not active")

    # Validate origin
    if not validate_origin(origin, agent.allowed_domains):
        log.warning("origin_not_allowed", allowed=agent.allowed_domains)
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # Generate session
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=SESSION_EXPIRY_MINUTES)

    # Store session (in production, use Redis with TTL)
    _embed_sessions[session_id] = {
        "agent_id": str(agent.id),
        "public_id": public_id,
        "origin": origin,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    # Clean up expired sessions (simple cleanup, production would use Redis TTL)
    cleanup_expired_sessions()

    # Build WebSocket URL
    ws_url = f"/ws/public/embed/{public_id}?session={session_id}"

    log.info("session_created", session_id=session_id[:8])

    return EmbedSessionResponse(
        session_id=session_id,
        expires_at=expires_at.isoformat(),
        websocket_url=ws_url,
    )


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from memory."""
    now = datetime.now(UTC)
    expired = [
        sid
        for sid, data in _embed_sessions.items()
        if datetime.fromisoformat(data["expires_at"]) < now
    ]
    for sid in expired:
        del _embed_sessions[sid]


def validate_session(session_id: str, public_id: str) -> dict[str, Any] | None:
    """Validate a session token.

    Args:
        session_id: The session token
        public_id: The expected public ID

    Returns:
        Session data if valid, None otherwise
    """
    session = _embed_sessions.get(session_id)
    if not session:
        return None

    # Check expiry
    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.now(UTC) > expires_at:
        del _embed_sessions[session_id]
        return None

    # Check public_id matches
    if session["public_id"] != public_id:
        return None

    return session


async def _get_embed_session_context(
    websocket: WebSocket,
    public_id: str,
    session_token: str,
    db: AsyncSession,
    log: Any,
) -> tuple[Agent, uuid.UUID, int] | None:
    """Validate session and get agent context for embed WebSocket.

    Returns (agent, workspace_id, user_id_int) or None if validation fails.
    """
    from app.core.auth import get_user_id_from_uuid
    from app.models.workspace import AgentWorkspace

    # Validate session
    session_data = validate_session(session_token, public_id)
    if not session_data:
        log.warning("invalid_session")
        await websocket.send_json({"type": "error", "error": "Invalid or expired session"})
        await websocket.close(code=4001)
        return None

    # Get agent
    agent = await get_agent_by_public_id(public_id, db)
    if not agent:
        await websocket.send_json({"type": "error", "error": "Agent not found"})
        await websocket.close(code=4004)
        return None

    if not agent.embed_enabled or not agent.is_active:
        await websocket.send_json({"type": "error", "error": "Agent not available"})
        await websocket.close(code=4003)
        return None

    log.info("agent_loaded", agent_name=agent.name, tier=agent.pricing_tier)

    # Get workspace for this agent
    workspace_result = await db.execute(
        select(AgentWorkspace).where(AgentWorkspace.agent_id == agent.id).limit(1)
    )
    agent_workspace = workspace_result.scalar_one_or_none()

    if not agent_workspace:
        log.warning("no_workspace_for_agent")
        await websocket.send_json({"type": "error", "error": "Agent not configured properly"})
        await websocket.close(code=4000)
        return None

    # Look up user_id for the agent
    user_id_int = await get_user_id_from_uuid(agent.user_id, db)
    if user_id_int is None:
        await websocket.send_json({"type": "error", "error": "Agent owner not found"})
        await websocket.close()
        return None

    return agent, agent_workspace.workspace_id, user_id_int


@ws_router.websocket("/{public_id}")
async def embed_websocket(
    websocket: WebSocket,
    public_id: str,
    session: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Public WebSocket endpoint for embed voice streaming."""
    ws_session_id = str(uuid.uuid4())
    log = logger.bind(endpoint="embed_websocket", public_id=public_id, ws_session_id=ws_session_id)

    await websocket.accept()
    log.info("websocket_connected")

    try:
        context = await _get_embed_session_context(websocket, public_id, session, db, log)
        if not context:
            return

        agent, workspace_id, user_id_int = context
        agent_config = {
            "system_prompt": agent.system_prompt,
            "enabled_tools": agent.enabled_tools,
            "language": agent.language,
            "voice": agent.voice or "shimmer",
        }

        if agent.pricing_tier in ("premium", "premium-mini"):
            async with GPTRealtimeSession(
                db=db,
                user_id=user_id_int,
                agent_config=agent_config,
                session_id=ws_session_id,
                workspace_id=workspace_id,
            ) as realtime_session:
                await websocket.send_json(
                    {
                        "type": "session.ready",
                        "session_id": ws_session_id,
                        "agent": {"name": agent.name, "voice": agent.voice},
                    }
                )
                await _bridge_embed_streams(websocket, realtime_session, log)
        else:
            await websocket.send_json(
                {"type": "error", "error": "Voice chat requires Premium tier agent"}
            )
            await websocket.close(code=4002)

    except WebSocketDisconnect:
        log.info("websocket_disconnected")
    except Exception as e:
        log.exception("websocket_error", error=str(e))
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "error": str(e)})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
        log.info("websocket_closed")


async def _bridge_embed_streams(
    client_ws: WebSocket,
    realtime_session: GPTRealtimeSession,
    logger: Any,
) -> None:
    """Bridge audio streams between embed client and GPT Realtime."""

    async def client_to_realtime() -> None:
        """Forward messages from client to GPT Realtime."""
        try:
            while True:
                message = await client_ws.receive()

                if message["type"] == "websocket.disconnect":
                    logger.info("client_initiated_disconnect")
                    break

                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        await realtime_session.send_audio(message["bytes"])
                    elif "text" in message:
                        try:
                            data = json.loads(message["text"])
                            logger.debug("client_event", event_type=data.get("type"))
                        except json.JSONDecodeError:
                            continue

        except WebSocketDisconnect:
            logger.info("client_disconnected")
        except Exception as e:
            logger.exception("client_to_realtime_error", error=str(e))

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

                    # Log non-audio events (audio deltas are too frequent)
                    if event_type != "response.audio.delta":
                        logger.info("realtime_event", event_type=event_type)
                    else:
                        logger.debug("audio_delta_received")

                    # Handle tool calls internally
                    if event_type == "response.function_call_arguments.done":
                        await realtime_session.handle_function_call_event(event)

                    # Forward events to client
                    await client_ws.send_json(
                        {
                            "type": event_type,
                            "event": event.model_dump() if hasattr(event, "model_dump") else {},
                        }
                    )
                    logger.debug("event_forwarded", event_type=event_type)

                except Exception as e:
                    logger.exception("event_forward_error", error=str(e))

        except Exception as e:
            logger.exception("realtime_to_client_error", error=str(e))

    # Run both directions concurrently
    await asyncio.gather(
        client_to_realtime(),
        realtime_to_client(),
        return_exceptions=True,
    )


@router.post("/{public_id}/token")
async def get_embed_ephemeral_token(  # noqa: PLR0915
    public_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    origin: str | None = Header(None),
) -> dict[str, Any]:
    """Get an ephemeral token for OpenAI Realtime API WebRTC connection.

    This public endpoint allows embed widgets to establish direct WebRTC
    connections to OpenAI without proxying through the backend.

    Security:
    - Origin validation against allowed domains
    - Rate limiting (inherited from router)
    - Short-lived tokens (expire in ~60 seconds)
    """
    import httpx

    from app.api.settings import get_user_api_keys
    from app.core.auth import get_user_id_from_uuid, user_id_to_uuid
    from app.models.workspace import AgentWorkspace
    from app.services.gpt_realtime import build_instructions_with_language

    log = logger.bind(endpoint="embed_token", public_id=public_id, origin=origin)

    # Get agent
    agent = await get_agent_by_public_id(public_id, db)
    if not agent:
        log.warning("agent_not_found")
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.embed_enabled:
        log.warning("embed_disabled")
        raise HTTPException(status_code=403, detail="Embedding is disabled for this agent")

    if not agent.is_active:
        log.warning("agent_inactive")
        raise HTTPException(status_code=403, detail="Agent is not active")

    # Validate origin
    if not validate_origin(origin, agent.allowed_domains):
        log.warning("origin_not_allowed", allowed=agent.allowed_domains)
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # Check premium tier
    if agent.pricing_tier not in ("premium", "premium-mini"):
        raise HTTPException(
            status_code=400, detail="WebRTC Realtime only available for Premium tier agents"
        )

    # Get workspace for API key lookup
    workspace_result = await db.execute(
        select(AgentWorkspace).where(AgentWorkspace.agent_id == agent.id).limit(1)
    )
    agent_workspace = workspace_result.scalar_one_or_none()

    if not agent_workspace:
        log.warning("no_workspace_for_agent")
        raise HTTPException(status_code=500, detail="Agent not configured properly")

    # Get OpenAI API key
    user_uuid = user_id_to_uuid(await get_user_id_from_uuid(agent.user_id, db) or 0)
    user_settings = await get_user_api_keys(
        user_uuid, db, workspace_id=agent_workspace.workspace_id
    )

    # Strictly use workspace API key - no fallback to global key for billing isolation
    if not user_settings or not user_settings.openai_api_key:
        log.warning("workspace_missing_openai_key", workspace_id=str(agent_workspace.workspace_id))
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured for this workspace. Please add it in Settings > Workspace API Keys.",
        )
    api_key = user_settings.openai_api_key
    log.info("using_workspace_openai_key")

    # Determine model based on tier
    realtime_model = (
        "gpt-4o-mini-realtime-preview-2024-12-17"
        if agent.pricing_tier == "premium-mini"
        else "gpt-realtime-2025-08-28"
    )

    # Build session configuration
    agent_voice = agent.voice or "marin"
    session_config: dict[str, Any] = {
        "model": realtime_model,
        "modalities": ["audio", "text"],
        "voice": agent_voice,
    }

    log.info("requesting_ephemeral_token", model=realtime_model)

    # Request ephemeral token from OpenAI
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
                log.error(
                    "openai_token_error",
                    status_code=response.status_code,
                    response_text=response.text,
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"OpenAI API error: {response.text}",
                )

            token_data = response.json()
            log.info("ephemeral_token_created")

            # Build instructions for the frontend
            system_prompt = agent.system_prompt or "You are a helpful voice assistant."
            instructions = build_instructions_with_language(system_prompt, agent.language)

            # Get tool definitions for this agent (matching realtime.py implementation)
            # Note: For embed widgets, we include tool definitions but execution
            # happens via the /tool-call endpoint
            from app.services.tools.registry import ToolRegistry

            # Get user_id for the agent owner (needed for tool registry)
            user_id_int = await get_user_id_from_uuid(agent.user_id, db) or 0

            # Get integration credentials for the workspace
            workspace_id = agent_workspace.workspace_id
            integrations = await get_workspace_integrations(agent.user_id, workspace_id, db)

            tool_registry = ToolRegistry(
                db=db,
                user_id=user_id_int,
                integrations=integrations,
                workspace_id=workspace_id,
            )
            tools = tool_registry.get_all_tool_definitions(
                agent.enabled_tools or [], agent.enabled_tool_ids
            )

            log.info(
                "tools_prepared",
                tool_count=len(tools),
                enabled_tools=agent.enabled_tools,
                enabled_tool_ids=agent.enabled_tool_ids,
                tool_names=[t.get("name") for t in tools],
            )

            return {
                "client_secret": token_data.get("client_secret", {}),
                "agent": {
                    "name": agent.name,
                    "voice": agent_voice,
                    "instructions": instructions,
                    "language": agent.language,
                    "initial_greeting": agent.initial_greeting,
                },
                "model": realtime_model,
                "tools": tools,
            }

    except httpx.RequestError as e:
        log.exception("openai_token_request_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to connect to OpenAI: {e!s}") from e


class ToolCallRequest(BaseModel):
    """Request model for tool execution."""

    tool_name: str
    arguments: dict[str, Any]


@router.post("/{public_id}/tool-call")
async def execute_embed_tool_call(
    public_id: str,
    tool_request: ToolCallRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    origin: str | None = Header(None),
) -> dict[str, Any]:
    """Execute a tool call for an embed widget.

    This endpoint allows the frontend to proxy tool calls from OpenAI
    Realtime API to the backend for execution with proper credentials.

    Security:
    - Origin validation against allowed domains
    - Only tools enabled for the agent are executed
    """
    from app.core.auth import get_user_id_from_uuid

    log = logger.bind(
        endpoint="embed_tool_call",
        public_id=public_id,
        tool_name=tool_request.tool_name,
        origin=origin,
    )

    # Get agent
    agent = await get_agent_by_public_id(public_id, db)
    if not agent:
        log.warning("agent_not_found")
        raise HTTPException(status_code=404, detail="Agent not found")

    if not agent.embed_enabled or not agent.is_active:
        log.warning("agent_not_available")
        raise HTTPException(status_code=403, detail="Agent not available")

    # Validate origin
    if not validate_origin(origin, agent.allowed_domains):
        log.warning("origin_not_allowed", allowed=agent.allowed_domains)
        raise HTTPException(status_code=403, detail="Origin not allowed")

    # Get user ID for tool execution
    user_id_int = await get_user_id_from_uuid(agent.user_id, db)
    if user_id_int is None:
        return {"success": False, "error": "Agent owner not found"}

    # Get workspace for this agent (needed for proper CRM scoping)
    from app.models.workspace import AgentWorkspace

    workspace_result = await db.execute(
        select(AgentWorkspace).where(AgentWorkspace.agent_id == agent.id).limit(1)
    )
    agent_workspace = workspace_result.scalar_one_or_none()
    workspace_id = agent_workspace.workspace_id if agent_workspace else None

    # Get integration credentials for the workspace
    integrations: dict[str, dict[str, Any]] = {}
    if workspace_id:
        integrations = await get_workspace_integrations(agent.user_id, workspace_id, db)

    # Create tool registry with workspace context
    from app.services.tools.registry import ToolRegistry

    tool_registry = ToolRegistry(
        db=db,
        user_id=user_id_int,
        integrations=integrations,
        workspace_id=workspace_id,
    )

    # Get the enabled tools for this agent (same method as token endpoint)
    enabled_tool_defs = tool_registry.get_all_tool_definitions(
        agent.enabled_tools or [], agent.enabled_tool_ids
    )
    enabled_tool_names = {
        t.get("name") or t.get("function", {}).get("name") for t in enabled_tool_defs
    }

    # Validate the requested tool is in the enabled tools list
    if tool_request.tool_name not in enabled_tool_names:
        log.warning(
            "tool_not_enabled",
            requested=tool_request.tool_name,
            enabled=list(enabled_tool_names),
        )
        return {
            "success": False,
            "error": f"Tool '{tool_request.tool_name}' is not enabled for this agent",
        }

    try:
        result = await tool_registry.execute_tool(
            tool_request.tool_name,
            tool_request.arguments,
        )
        log.info("tool_executed", success=result.get("success"))
        return result
    except Exception as e:
        log.exception("tool_execution_error", error=str(e))
        return {"success": False, "error": str(e)}
    finally:
        await tool_registry.close()
