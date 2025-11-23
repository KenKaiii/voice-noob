"""Voice agent API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.models import VoiceAgent
from app.schemas.voice_agent import VoiceAgentCreate, VoiceAgentResponse, VoiceAgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=VoiceAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: VoiceAgentCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceAgent:
    """Create a new voice agent."""
    agent = VoiceAgent(
        user_id=current_user.id,
        **agent_data.model_dump(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return agent


@router.get("", response_model=list[VoiceAgentResponse])
async def list_agents(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[VoiceAgent]:
    """List all voice agents for current user."""
    result = await db.execute(
        select(VoiceAgent)
        .where(VoiceAgent.user_id == current_user.id)
        .order_by(VoiceAgent.created_at.desc()),
    )
    agents = result.scalars().all()

    return list(agents)


@router.get("/{agent_id}", response_model=VoiceAgentResponse)
async def get_agent(
    agent_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceAgent:
    """Get a specific voice agent."""
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
        ),
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return agent


@router.patch("/{agent_id}", response_model=VoiceAgentResponse)
async def update_agent(
    agent_id: int,
    agent_update: VoiceAgentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VoiceAgent:
    """Update a voice agent."""
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
        ),
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    update_data = agent_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a voice agent."""
    result = await db.execute(
        select(VoiceAgent).where(
            VoiceAgent.id == agent_id,
            VoiceAgent.user_id == current_user.id,
        ),
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    await db.delete(agent)
    await db.commit()
