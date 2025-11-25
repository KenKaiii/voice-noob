"""API endpoints for managing voice agents."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    enabled_tools: list[str] = Field(default_factory=list)
    phone_number_id: str | None = None
    enable_recording: bool = False
    enable_transcript: bool = True


class AgentResponse(BaseModel):
    """Agent response."""

    id: str
    name: str
    description: str | None
    pricing_tier: str
    system_prompt: str
    language: str
    enabled_tools: list[str]
    phone_number_id: str | None
    enable_recording: bool
    enable_transcript: bool
    is_active: bool
    is_published: bool
    total_calls: int
    total_duration_seconds: int
    created_at: str
    updated_at: str
    last_call_at: str | None


# Dependency to get current user ID (placeholder)
async def get_current_user_id() -> uuid.UUID:
    """Get current user ID from auth token.

    TODO: Implement actual authentication
    """
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Create a new voice agent.

    Args:
        request: Agent creation request
        user_id: Current user ID
        db: Database session

    Returns:
        Created agent
    """
    # Build provider config based on tier (from pricing-tiers.ts)
    provider_config = _get_provider_config(request.pricing_tier)

    agent = Agent(
        user_id=user_id,
        name=request.name,
        description=request.description,
        pricing_tier=request.pricing_tier,
        system_prompt=request.system_prompt,
        language=request.language,
        enabled_tools=request.enabled_tools,
        phone_number_id=request.phone_number_id,
        enable_recording=request.enable_recording,
        enable_transcript=request.enable_transcript,
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
    skip: int = 0,
    limit: int = 50,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """List all agents for current user with pagination.

    Args:
        skip: Number of records to skip (default 0)
        limit: Maximum number of records to return (default 50, max 100)
        user_id: Current user ID
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

    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == user_id)
        .order_by(Agent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    agents = result.scalars().all()

    return [_agent_to_response(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Get a specific agent.

    Args:
        agent_id: Agent UUID
        user_id: Current user ID
        db: Database session

    Returns:
        Agent details

    Raises:
        HTTPException: If agent not found or unauthorized
    """
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_id,
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
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an agent.

    Args:
        agent_id: Agent UUID
        user_id: Current user ID
        db: Database session

    Raises:
        HTTPException: If agent not found or unauthorized
    """
    result = await db.execute(
        select(Agent).where(
            Agent.id == uuid.UUID(agent_id),
            Agent.user_id == user_id,
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
        enabled_tools=agent.enabled_tools,
        phone_number_id=agent.phone_number_id,
        enable_recording=agent.enable_recording,
        enable_transcript=agent.enable_transcript,
        is_active=agent.is_active,
        is_published=agent.is_published,
        total_calls=agent.total_calls,
        total_duration_seconds=agent.total_duration_seconds,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
        last_call_at=agent.last_call_at.isoformat() if agent.last_call_at else None,
    )
