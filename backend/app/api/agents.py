"""API endpoints for managing voice agents."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, user_id_to_uuid
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
    pricing_tier: str = Field(..., pattern="^(budget|balanced|premium)$")
    system_prompt: str = Field(..., min_length=10)
    language: str = Field(default="en-US")
    voice: str = Field(default="shimmer")
    enabled_tools: list[str] = Field(default_factory=list)
    phone_number_id: str | None = None
    enable_recording: bool = False
    enable_transcript: bool = True
    # Turn detection settings
    turn_detection_mode: str = Field(default="normal", pattern="^(normal|semantic|disabled)$")
    turn_detection_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    turn_detection_prefix_padding_ms: int = Field(default=300, ge=0, le=1000)
    turn_detection_silence_duration_ms: int = Field(default=500, ge=0, le=2000)


class UpdateAgentRequest(BaseModel):
    """Request to update a voice agent."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    pricing_tier: str | None = Field(None, pattern="^(budget|balanced|premium)$")
    system_prompt: str | None = Field(None, min_length=10)
    language: str | None = None
    voice: str | None = None
    enabled_tools: list[str] | None = None
    phone_number_id: str | None = None
    enable_recording: bool | None = None
    enable_transcript: bool | None = None
    is_active: bool | None = None
    # Turn detection settings
    turn_detection_mode: str | None = Field(None, pattern="^(normal|semantic|disabled)$")
    turn_detection_threshold: float | None = Field(None, ge=0.0, le=1.0)
    turn_detection_prefix_padding_ms: int | None = Field(None, ge=0, le=1000)
    turn_detection_silence_duration_ms: int | None = Field(None, ge=0, le=2000)


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
    phone_number_id: str | None
    enable_recording: bool
    enable_transcript: bool
    # Turn detection settings
    turn_detection_mode: str
    turn_detection_threshold: float
    turn_detection_prefix_padding_ms: int
    turn_detection_silence_duration_ms: int
    is_active: bool
    is_published: bool
    total_calls: int
    total_duration_seconds: int
    created_at: str
    updated_at: str
    last_call_at: str | None


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Create a new voice agent.

    Args:
        request: Agent creation request
        current_user: Authenticated user
        db: Database session

    Returns:
        Created agent
    """
    # Build provider config based on tier (from pricing-tiers.ts)
    provider_config = _get_provider_config(request.pricing_tier)
    user_uuid = user_id_to_uuid(current_user.id)

    agent = Agent(
        user_id=user_uuid,
        name=request.name,
        description=request.description,
        pricing_tier=request.pricing_tier,
        system_prompt=request.system_prompt,
        language=request.language,
        voice=request.voice,
        enabled_tools=request.enabled_tools,
        phone_number_id=request.phone_number_id,
        enable_recording=request.enable_recording,
        enable_transcript=request.enable_transcript,
        turn_detection_mode=request.turn_detection_mode,
        turn_detection_threshold=request.turn_detection_threshold,
        turn_detection_prefix_padding_ms=request.turn_detection_prefix_padding_ms,
        turn_detection_silence_duration_ms=request.turn_detection_silence_duration_ms,
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
async def delete_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an agent.

    Args:
        agent_id: Agent UUID
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
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Update an agent.

    Args:
        agent_id: Agent UUID
        request: Update request
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
    _apply_agent_updates(agent, request)

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
        "phone_number_id",
        "enable_recording",
        "enable_transcript",
        "is_active",
        "turn_detection_mode",
        "turn_detection_threshold",
        "turn_detection_prefix_padding_ms",
        "turn_detection_silence_duration_ms",
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
    configs = {
        "budget": {
            "llm_provider": "cerebras",
            "llm_model": "llama-3.1-70b",
            "stt_provider": "deepgram",
            "stt_model": "nova-2",
            "tts_provider": "elevenlabs",
            "tts_model": "flash-v2.5",
        },
        "balanced": {
            "llm_provider": "google",
            "llm_model": "gemini-2.5-flash",
            "stt_provider": "google",
            "stt_model": "built-in",
            "tts_provider": "google",
            "tts_model": "built-in",
        },
        "premium": {
            "llm_provider": "openai-realtime",
            "llm_model": "gpt-4o-realtime-preview-2024-12-17",
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
        phone_number_id=agent.phone_number_id,
        enable_recording=agent.enable_recording,
        enable_transcript=agent.enable_transcript,
        turn_detection_mode=agent.turn_detection_mode,
        turn_detection_threshold=agent.turn_detection_threshold,
        turn_detection_prefix_padding_ms=agent.turn_detection_prefix_padding_ms,
        turn_detection_silence_duration_ms=agent.turn_detection_silence_duration_ms,
        is_active=agent.is_active,
        is_published=agent.is_published,
        total_calls=agent.total_calls,
        total_duration_seconds=agent.total_duration_seconds,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
        last_call_at=agent.last_call_at.isoformat() if agent.last_call_at else None,
    )
