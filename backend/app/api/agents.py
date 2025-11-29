"""API endpoints for managing voice agents."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, user_id_to_uuid
from app.core.limiter import limiter
from app.core.public_id import generate_public_id
from app.db.session import get_db
from app.models.agent import Agent

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Pagination constants
MAX_AGENTS_LIMIT = 100


# Pydantic schemas
class CreateAgentRequest(BaseModel):
    """Request to create a voice agent."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    pricing_tier: str = Field(..., pattern="^(budget|balanced|premium-mini|premium)$")
    system_prompt: str = Field(..., min_length=10)
    language: str = Field(default="en-US")
    voice: str = Field(default="shimmer")
    enabled_tools: list[str] = Field(default_factory=list)
    enabled_tool_ids: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Granular tool selection: {integration_id: [tool_id1, tool_id2]}",
    )
    phone_number_id: str | None = None
    enable_recording: bool = False
    enable_transcript: bool = True
    # Turn detection settings
    turn_detection_mode: str = Field(default="normal", pattern="^(normal|semantic|disabled)$")
    turn_detection_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    turn_detection_prefix_padding_ms: int = Field(default=300, ge=0, le=1000)
    turn_detection_silence_duration_ms: int = Field(default=500, ge=0, le=2000)
    # LLM settings
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=16000)
    # Initial greeting (optional)
    initial_greeting: str | None = Field(
        default=None,
        description="Optional initial greeting the agent speaks when call starts",
    )


class UpdateAgentRequest(BaseModel):
    """Request to update a voice agent."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    pricing_tier: str | None = Field(None, pattern="^(budget|balanced|premium-mini|premium)$")
    system_prompt: str | None = Field(None, min_length=10)
    language: str | None = None
    voice: str | None = None
    enabled_tools: list[str] | None = None
    enabled_tool_ids: dict[str, list[str]] | None = Field(
        default=None,
        description="Granular tool selection: {integration_id: [tool_id1, tool_id2]}",
    )
    phone_number_id: str | None = None
    enable_recording: bool | None = None
    enable_transcript: bool | None = None
    is_active: bool | None = None
    # Turn detection settings
    turn_detection_mode: str | None = Field(None, pattern="^(normal|semantic|disabled)$")
    turn_detection_threshold: float | None = Field(None, ge=0.0, le=1.0)
    turn_detection_prefix_padding_ms: int | None = Field(None, ge=0, le=1000)
    turn_detection_silence_duration_ms: int | None = Field(None, ge=0, le=2000)
    # LLM settings
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=100, le=16000)
    # Initial greeting (optional)
    initial_greeting: str | None = Field(
        default=None,
        description="Optional initial greeting the agent speaks when call starts",
    )


class AgentResponse(BaseModel):
    """Agent response."""

    id: str
    name: str
    description: str | None
    pricing_tier: str
    system_prompt: str
    language: str
    voice: str
    enabled_tools: list[str]
    enabled_tool_ids: dict[str, list[str]]
    phone_number_id: str | None
    enable_recording: bool
    enable_transcript: bool
    # Turn detection settings
    turn_detection_mode: str
    turn_detection_threshold: float
    turn_detection_prefix_padding_ms: int
    turn_detection_silence_duration_ms: int
    temperature: float
    max_tokens: int
    initial_greeting: str | None
    is_active: bool
    is_published: bool
    total_calls: int
    total_duration_seconds: int
    created_at: str
    updated_at: str
    last_call_at: str | None


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")  # Rate limit agent creation
async def create_agent(
    agent_request: CreateAgentRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Create a new voice agent.

    Args:
        agent_request: Agent creation request
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Created agent
    """
    # Build provider config based on tier (from pricing-tiers.ts)
    provider_config = _get_provider_config(agent_request.pricing_tier)
    user_uuid = user_id_to_uuid(current_user.id)

    agent = Agent(
        user_id=user_uuid,
        name=agent_request.name,
        description=agent_request.description,
        pricing_tier=agent_request.pricing_tier,
        system_prompt=agent_request.system_prompt,
        language=agent_request.language,
        voice=agent_request.voice,
        enabled_tools=agent_request.enabled_tools,
        enabled_tool_ids=agent_request.enabled_tool_ids,
        phone_number_id=agent_request.phone_number_id,
        enable_recording=agent_request.enable_recording,
        enable_transcript=agent_request.enable_transcript,
        turn_detection_mode=agent_request.turn_detection_mode,
        turn_detection_threshold=agent_request.turn_detection_threshold,
        turn_detection_prefix_padding_ms=agent_request.turn_detection_prefix_padding_ms,
        turn_detection_silence_duration_ms=agent_request.turn_detection_silence_duration_ms,
        temperature=agent_request.temperature,
        max_tokens=agent_request.max_tokens,
        initial_greeting=agent_request.initial_greeting,
        provider_config=provider_config,
        is_active=True,
        is_published=False,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return _agent_to_response(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """List all agents for current user with pagination.

    Args:
        current_user: Authenticated user
        skip: Number of records to skip (default 0)
        limit: Maximum number of records to return (default 50, max 100)
        db: Database session

    Returns:
        List of agents

    Raises:
        HTTPException: If pagination parameters are invalid
    """
    # Validate pagination parameters
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip must be non-negative")
    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit must be at least 1")
    if limit > MAX_AGENTS_LIMIT:
        raise HTTPException(status_code=400, detail=f"Limit cannot exceed {MAX_AGENTS_LIMIT}")

    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user_uuid)
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    agents = result.scalars().all()

    return [_agent_to_response(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Get a specific agent.

    Args:
        agent_id: Agent UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Agent details

    Raises:
        HTTPException: If agent not found or unauthorized
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return _agent_to_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")  # Rate limit agent deletion
async def delete_agent(
    agent_id: str,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an agent.

    Args:
        agent_id: Agent UUID
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException: If agent not found or unauthorized
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    await db.delete(agent)
    await db.commit()


@router.put("/{agent_id}", response_model=AgentResponse)
@limiter.limit("60/minute")  # Rate limit agent updates
async def update_agent(
    agent_id: str,
    update_request: UpdateAgentRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Update an agent.

    Args:
        agent_id: Agent UUID
        update_request: Update request body
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated agent

    Raises:
        HTTPException: If agent not found or unauthorized
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Apply updates from request
    _apply_agent_updates(agent, update_request)

    await db.commit()
    await db.refresh(agent)

    return _agent_to_response(agent)


def _apply_agent_updates(agent: Agent, request: UpdateAgentRequest) -> None:
    """Apply update request fields to agent model.

    Args:
        agent: Agent model to update
        request: Update request with optional fields
    """
    # Map of simple field updates (field_name -> request attribute)
    simple_fields = [
        "name",
        "description",
        "system_prompt",
        "language",
        "voice",
        "enabled_tools",
        "enabled_tool_ids",
        "phone_number_id",
        "enable_recording",
        "enable_transcript",
        "is_active",
        "turn_detection_mode",
        "turn_detection_threshold",
        "turn_detection_prefix_padding_ms",
        "turn_detection_silence_duration_ms",
        "temperature",
        "max_tokens",
        "initial_greeting",
    ]

    for field in simple_fields:
        value = getattr(request, field)
        if value is not None:
            setattr(agent, field, value)

    # Handle pricing_tier specially (updates provider_config too)
    if request.pricing_tier is not None:
        agent.pricing_tier = request.pricing_tier
        agent.provider_config = _get_provider_config(request.pricing_tier)


def _get_provider_config(tier: str) -> dict[str, Any]:
    """Get provider configuration for pricing tier.

    Args:
        tier: Pricing tier (budget, balanced, premium)

    Returns:
        Provider configuration
    """
    # Latest models as of Nov 2025:
    # - Deepgram: nova-3 (GA Feb 2025, 54% better accuracy than nova-2)
    # - ElevenLabs: eleven_flash_v2_5 (~75ms latency, 32 languages)
    # - OpenAI: gpt-realtime-2025-08-28 (GA Aug 2025)
    # - Google: gemini-2.5-flash with native audio (30 HD voices)
    configs = {
        "budget": {
            "llm_provider": "cerebras",
            "llm_model": "llama-3.3-70b",
            "stt_provider": "deepgram",
            "stt_model": "nova-3",
            "tts_provider": "elevenlabs",
            "tts_model": "eleven_flash_v2_5",
        },
        "balanced": {
            "llm_provider": "google",
            "llm_model": "gemini-2.5-flash",
            "stt_provider": "google",
            "stt_model": "built-in",
            "tts_provider": "google",
            "tts_model": "built-in",
        },
        "premium-mini": {
            "llm_provider": "openai-realtime",
            "llm_model": "gpt-4o-mini-realtime-preview-2024-12-17",
            "stt_provider": "openai",
            "stt_model": "built-in",
            "tts_provider": "openai",
            "tts_model": "built-in",
        },
        "premium": {
            "llm_provider": "openai-realtime",
            "llm_model": "gpt-realtime-2025-08-28",
            "stt_provider": "openai",
            "stt_model": "built-in",
            "tts_provider": "openai",
            "tts_model": "built-in",
        },
    }

    return configs.get(tier, configs["balanced"])


def _agent_to_response(agent: Agent) -> AgentResponse:
    """Convert Agent model to response schema.

    Args:
        agent: Agent model

    Returns:
        AgentResponse
    """
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        pricing_tier=agent.pricing_tier,
        system_prompt=agent.system_prompt,
        language=agent.language,
        voice=agent.voice,
        enabled_tools=agent.enabled_tools,
        enabled_tool_ids=agent.enabled_tool_ids,
        phone_number_id=agent.phone_number_id,
        enable_recording=agent.enable_recording,
        enable_transcript=agent.enable_transcript,
        turn_detection_mode=agent.turn_detection_mode,
        turn_detection_threshold=agent.turn_detection_threshold,
        turn_detection_prefix_padding_ms=agent.turn_detection_prefix_padding_ms,
        turn_detection_silence_duration_ms=agent.turn_detection_silence_duration_ms,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        initial_greeting=agent.initial_greeting,
        is_active=agent.is_active,
        is_published=agent.is_published,
        total_calls=agent.total_calls,
        total_duration_seconds=agent.total_duration_seconds,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
        last_call_at=agent.last_call_at.isoformat() if agent.last_call_at else None,
    )


# ============================================================================
# Embed Settings Endpoints
# ============================================================================


class EmbedSettingsResponse(BaseModel):
    """Response for agent embed settings."""

    public_id: str
    embed_enabled: bool
    allowed_domains: list[str]
    embed_settings: dict[str, Any]
    script_tag: str
    iframe_code: str


class UpdateEmbedSettingsRequest(BaseModel):
    """Request to update embed settings."""

    embed_enabled: bool | None = None
    allowed_domains: list[str] | None = None
    embed_settings: dict[str, Any] | None = None


@router.get("/{agent_id}/embed", response_model=EmbedSettingsResponse)
async def get_embed_settings(
    agent_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> EmbedSettingsResponse:
    """Get embed settings for an agent.

    If the agent doesn't have a public_id yet, one will be generated.

    Args:
        agent_id: Agent UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Embed settings including embed code snippets
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Generate public_id if not exists
    if not agent.public_id:
        # Generate unique public_id
        while True:
            new_public_id = generate_public_id()
            # Check for collision
            existing = await db.execute(select(Agent).where(Agent.public_id == new_public_id))
            if not existing.scalar_one_or_none():
                agent.public_id = new_public_id
                await db.commit()
                await db.refresh(agent)
                break

    # Build embed code snippets
    # In production, replace with actual domain
    base_url = "https://yourplatform.com"  # TODO: Get from config
    script_tag = f"""<script src="{base_url}/widget/v1/widget.js" defer></script>
<voice-agent agent-id="{agent.public_id}"></voice-agent>"""

    iframe_code = f"""<iframe
  src="{base_url}/embed/{agent.public_id}"
  allow="microphone"
  style="border: none; position: fixed; bottom: 20px; right: 20px; width: 400px; height: 600px; z-index: 9999;"
></iframe>"""

    return EmbedSettingsResponse(
        public_id=agent.public_id,
        embed_enabled=agent.embed_enabled,
        allowed_domains=agent.allowed_domains,
        embed_settings=agent.embed_settings,
        script_tag=script_tag,
        iframe_code=iframe_code,
    )


@router.patch("/{agent_id}/embed", response_model=EmbedSettingsResponse)
@limiter.limit("30/minute")
async def update_embed_settings(
    agent_id: str,
    update_request: UpdateEmbedSettingsRequest,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> EmbedSettingsResponse:
    """Update embed settings for an agent.

    Args:
        agent_id: Agent UUID
        update_request: Settings to update
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated embed settings
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Apply updates
    if update_request.embed_enabled is not None:
        agent.embed_enabled = update_request.embed_enabled

    if update_request.allowed_domains is not None:
        agent.allowed_domains = update_request.allowed_domains

    if update_request.embed_settings is not None:
        # Merge with existing settings - create new dict to ensure SQLAlchemy detects change
        current_settings = dict(agent.embed_settings or {})
        current_settings.update(update_request.embed_settings)
        agent.embed_settings = current_settings

    await db.commit()
    await db.refresh(agent)

    # Return via get_embed_settings to ensure consistency
    return await get_embed_settings(agent_id, current_user, db)


@router.post("/{agent_id}/embed/regenerate-id", response_model=EmbedSettingsResponse)
@limiter.limit("5/minute")
async def regenerate_public_id(
    agent_id: str,
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> EmbedSettingsResponse:
    """Regenerate the public ID for an agent.

    WARNING: This will invalidate all existing embed codes using the old ID.

    Args:
        agent_id: Agent UUID
        request: HTTP request (for rate limiting)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated embed settings with new public_id
    """
    user_uuid = user_id_to_uuid(current_user.id)
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_uuid,
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Generate new unique public_id
    while True:
        new_public_id = generate_public_id()
        # Check for collision
        existing = await db.execute(select(Agent).where(Agent.public_id == new_public_id))
        if not existing.scalar_one_or_none():
            agent.public_id = new_public_id
            break

    await db.commit()
    await db.refresh(agent)

    # Return via get_embed_settings to ensure consistency
    return await get_embed_settings(agent_id, current_user, db)
