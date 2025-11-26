"""Workspace API endpoints."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.limiter import limiter
from app.db.session import get_db
from app.models.agent import Agent
from app.models.contact import Contact
from app.models.workspace import AgentWorkspace, Workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

# Constants
MAX_WORKSPACE_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000


# Pydantic schemas
class WorkspaceSettingsSchema(BaseModel):
    """Workspace settings schema."""

    timezone: str = "UTC"
    business_hours: dict[str, Any] | None = None
    booking_buffer_minutes: int = 15
    max_advance_booking_days: int = 30
    default_appointment_duration: int = 30
    allow_same_day_booking: bool = True


class WorkspaceResponse(BaseModel):
    """Workspace response schema."""

    id: str
    user_id: int
    name: str
    description: str | None
    settings: dict[str, Any]
    is_default: bool
    agent_count: int = 0
    contact_count: int = 0

    class Config:
        """Pydantic config."""

        from_attributes = True


class WorkspaceCreate(BaseModel):
    """Workspace creation schema."""

    name: str
    description: str | None = None
    settings: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate workspace name."""
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        if len(v) > MAX_WORKSPACE_NAME_LENGTH:
            raise ValueError(f"name cannot exceed {MAX_WORKSPACE_NAME_LENGTH} characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """Validate description length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_DESCRIPTION_LENGTH:
                raise ValueError(f"description cannot exceed {MAX_DESCRIPTION_LENGTH} characters")
            if not v:
                return None
        return v


class WorkspaceUpdate(BaseModel):
    """Workspace update schema."""

    name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None
    is_default: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate workspace name."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name cannot be empty")
            if len(v) > MAX_WORKSPACE_NAME_LENGTH:
                raise ValueError(f"name cannot exceed {MAX_WORKSPACE_NAME_LENGTH} characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """Validate description length."""
        if v is not None:
            v = v.strip()
            if len(v) > MAX_DESCRIPTION_LENGTH:
                raise ValueError(f"description cannot exceed {MAX_DESCRIPTION_LENGTH} characters")
            if not v:
                return None
        return v


class AgentWorkspaceResponse(BaseModel):
    """Agent-Workspace association response."""

    agent_id: str
    agent_name: str
    is_default: bool


class AddAgentToWorkspaceRequest(BaseModel):
    """Request to add an agent to a workspace."""

    agent_id: str
    is_default: bool = False


class AgentWorkspacesResponse(BaseModel):
    """Response for agent's workspaces."""

    workspace_id: str
    workspace_name: str


class SetAgentWorkspacesRequest(BaseModel):
    """Request to set all workspaces for an agent."""

    workspace_ids: list[str]


def _get_current_user_id() -> int:
    """Get current user ID (placeholder until auth is implemented)."""
    return 1


@router.get("", response_model=list[WorkspaceResponse])
@limiter.limit("100/minute")
async def list_workspaces(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all workspaces for the current user."""
    user_id = _get_current_user_id()

    try:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.user_id == user_id)
            .options(selectinload(Workspace.agent_workspaces))
            .order_by(Workspace.is_default.desc(), Workspace.created_at.desc()),
        )
        workspaces = list(result.scalars().all())
    except DBAPIError as e:
        logger.exception("Database error listing workspaces")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    response = []
    for ws in workspaces:
        # Get contact count for this workspace
        contact_count_result = await db.execute(
            select(Contact).where(Contact.workspace_id == ws.id)
        )
        contact_count = len(list(contact_count_result.scalars().all()))

        response.append(
            {
                "id": str(ws.id),
                "user_id": ws.user_id,
                "name": ws.name,
                "description": ws.description,
                "settings": ws.settings,
                "is_default": ws.is_default,
                "agent_count": len(ws.agent_workspaces),
                "contact_count": contact_count,
            }
        )

    return response


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
@limiter.limit("100/minute")
async def get_workspace(
    request: Request,
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single workspace by ID."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid workspace ID format") from e

    try:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.id == workspace_uuid, Workspace.user_id == user_id)
            .options(selectinload(Workspace.agent_workspaces)),
        )
        workspace = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving workspace: %s", workspace_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {
        "id": str(workspace.id),
        "user_id": workspace.user_id,
        "name": workspace.name,
        "description": workspace.description,
        "settings": workspace.settings,
        "is_default": workspace.is_default,
        "agent_count": len(workspace.agent_workspaces),
        "contact_count": 0,
    }


@router.post("", response_model=WorkspaceResponse, status_code=201)
@limiter.limit("100/minute")
async def create_workspace(
    request: Request,
    workspace_data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new workspace."""
    user_id = _get_current_user_id()

    try:
        workspace = Workspace(
            user_id=user_id,
            name=workspace_data.name,
            description=workspace_data.description,
            settings=workspace_data.settings or {},
            is_default=False,
        )
        db.add(workspace)
        await db.commit()
        await db.refresh(workspace)

        logger.info(
            "Created workspace: id=%s, user_id=%d, name=%s", workspace.id, user_id, workspace.name
        )

        return {
            "id": str(workspace.id),
            "user_id": workspace.user_id,
            "name": workspace.name,
            "description": workspace.description,
            "settings": workspace.settings,
            "is_default": workspace.is_default,
            "agent_count": 0,
            "contact_count": 0,
        }
    except IntegrityError as e:
        await db.rollback()
        logger.warning("Integrity error creating workspace: user_id=%d", user_id)
        raise HTTPException(
            status_code=400,
            detail="Failed to create workspace",
        ) from e
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error creating workspace")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
@limiter.limit("100/minute")
async def update_workspace(
    request: Request,
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update an existing workspace."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid workspace ID format") from e

    try:
        result = await db.execute(
            select(Workspace)
            .where(Workspace.id == workspace_uuid, Workspace.user_id == user_id)
            .options(selectinload(Workspace.agent_workspaces)),
        )
        workspace = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving workspace for update: %s", workspace_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Update fields
    update_data = workspace_data.model_dump(exclude_unset=True)

    # Handle is_default specially - if setting to true, unset other defaults
    if update_data.get("is_default") is True and not workspace.is_default:
        await db.execute(
            select(Workspace).where(Workspace.user_id == user_id, Workspace.is_default.is_(True))
        )
        # Reset other workspaces
        from sqlalchemy import update as sql_update

        await db.execute(
            sql_update(Workspace)
            .where(Workspace.user_id == user_id, Workspace.id != workspace_uuid)
            .values(is_default=False)
        )

    for field, value in update_data.items():
        setattr(workspace, field, value)

    try:
        await db.commit()
        await db.refresh(workspace)

        logger.info("Updated workspace: id=%s", workspace.id)

        return {
            "id": str(workspace.id),
            "user_id": workspace.user_id,
            "name": workspace.name,
            "description": workspace.description,
            "settings": workspace.settings,
            "is_default": workspace.is_default,
            "agent_count": len(workspace.agent_workspaces),
            "contact_count": 0,
        }
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error updating workspace: %s", workspace_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.delete("/{workspace_id}", status_code=204)
@limiter.limit("100/minute")
async def delete_workspace(
    request: Request,
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workspace (cannot delete default workspace)."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid workspace ID format") from e

    try:
        result = await db.execute(
            select(Workspace).where(Workspace.id == workspace_uuid, Workspace.user_id == user_id),
        )
        workspace = result.scalar_one_or_none()
    except DBAPIError as e:
        logger.exception("Database error retrieving workspace for deletion: %s", workspace_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if workspace.is_default:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the default workspace. Set another workspace as default first.",
        )

    try:
        await db.delete(workspace)
        await db.commit()
        logger.info("Deleted workspace: id=%s", workspace_id)
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error deleting workspace: %s", workspace_id)
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


# --- Agent-Workspace Management ---


@router.get("/{workspace_id}/agents", response_model=list[AgentWorkspaceResponse])
@limiter.limit("100/minute")
async def list_workspace_agents(
    request: Request,
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all agents assigned to a workspace."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid workspace ID format") from e

    # Verify workspace belongs to user
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid, Workspace.user_id == user_id),
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get agents
    result = await db.execute(
        select(AgentWorkspace, Agent)
        .join(Agent)
        .where(AgentWorkspace.workspace_id == workspace_uuid),
    )
    agent_workspaces = result.all()

    return [
        {
            "agent_id": str(aw.agent_id),
            "agent_name": agent.name,
            "is_default": aw.is_default,
        }
        for aw, agent in agent_workspaces
    ]


@router.post("/{workspace_id}/agents", status_code=201)
@limiter.limit("100/minute")
async def add_agent_to_workspace(
    request: Request,
    workspace_id: str,
    data: AddAgentToWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Add an agent to a workspace."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
        agent_uuid = uuid.UUID(data.agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid ID format") from e

    # Verify workspace belongs to user
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid, Workspace.user_id == user_id),
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Verify agent exists
    result = await db.execute(select(Agent).where(Agent.id == agent_uuid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check if already linked
    result = await db.execute(
        select(AgentWorkspace).where(
            AgentWorkspace.agent_id == agent_uuid,
            AgentWorkspace.workspace_id == workspace_uuid,
        ),
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Agent is already in this workspace")

    # If setting as default, unset other defaults for this agent
    if data.is_default:
        from sqlalchemy import update as sql_update

        await db.execute(
            sql_update(AgentWorkspace)
            .where(AgentWorkspace.agent_id == agent_uuid)
            .values(is_default=False)
        )

    try:
        agent_workspace = AgentWorkspace(
            agent_id=agent_uuid,
            workspace_id=workspace_uuid,
            is_default=data.is_default,
        )
        db.add(agent_workspace)
        await db.commit()

        logger.info("Added agent %s to workspace %s", agent_uuid, workspace_uuid)
        return {"message": "Agent added to workspace successfully"}
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error adding agent to workspace")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.delete("/{workspace_id}/agents/{agent_id}", status_code=204)
@limiter.limit("100/minute")
async def remove_agent_from_workspace(
    request: Request,
    workspace_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove an agent from a workspace."""
    user_id = _get_current_user_id()

    try:
        workspace_uuid = uuid.UUID(workspace_id)
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid ID format") from e

    # Verify workspace belongs to user
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid, Workspace.user_id == user_id),
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Find and delete the link
    result = await db.execute(
        select(AgentWorkspace).where(
            AgentWorkspace.agent_id == agent_uuid,
            AgentWorkspace.workspace_id == workspace_uuid,
        ),
    )
    agent_workspace = result.scalar_one_or_none()
    if not agent_workspace:
        raise HTTPException(status_code=404, detail="Agent is not in this workspace")

    try:
        await db.delete(agent_workspace)
        await db.commit()
        logger.info("Removed agent %s from workspace %s", agent_id, workspace_id)
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error removing agent from workspace")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e


@router.get("/agent/{agent_id}", response_model=list[AgentWorkspacesResponse])
@limiter.limit("100/minute")
async def get_agent_workspaces(
    request: Request,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, str]]:
    """Get all workspaces for an agent."""
    user_id = _get_current_user_id()

    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid agent ID format") from e

    # Verify agent exists
    result = await db.execute(select(Agent).where(Agent.id == agent_uuid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get workspaces that belong to the current user
    result = await db.execute(
        select(AgentWorkspace, Workspace)
        .join(Workspace)
        .where(
            AgentWorkspace.agent_id == agent_uuid,
            Workspace.user_id == user_id,
        ),
    )
    agent_workspaces = result.all()

    return [
        {
            "workspace_id": str(aw.workspace_id),
            "workspace_name": ws.name,
        }
        for aw, ws in agent_workspaces
    ]


@router.put("/agent/{agent_id}/workspaces")
@limiter.limit("100/minute")
async def set_agent_workspaces(
    request: Request,
    agent_id: str,
    data: SetAgentWorkspacesRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Set all workspaces for an agent (bulk operation)."""
    user_id = _get_current_user_id()

    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid agent ID format") from e

    # Verify agent exists
    result = await db.execute(select(Agent).where(Agent.id == agent_uuid))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Parse and validate workspace IDs
    workspace_uuids = []
    for ws_id in data.workspace_ids:
        try:
            workspace_uuids.append(uuid.UUID(ws_id))
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid workspace ID format: {ws_id}"
            ) from e

    # Verify all workspaces belong to user
    if workspace_uuids:
        result = await db.execute(
            select(Workspace).where(
                Workspace.id.in_(workspace_uuids),
                Workspace.user_id == user_id,
            ),
        )
        valid_workspaces = list(result.scalars().all())
        valid_ids = {ws.id for ws in valid_workspaces}

        invalid_ids = [str(ws_id) for ws_id in workspace_uuids if ws_id not in valid_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid workspace IDs: {', '.join(invalid_ids)}",
            )

    try:
        # Delete all existing workspace associations for this agent using bulk delete
        from sqlalchemy import delete as sql_delete

        await db.execute(sql_delete(AgentWorkspace).where(AgentWorkspace.agent_id == agent_uuid))
        await db.flush()  # Flush to ensure deletes are applied before inserts

        # Create new associations
        for workspace_uuid in workspace_uuids:
            agent_workspace = AgentWorkspace(
                agent_id=agent_uuid,
                workspace_id=workspace_uuid,
                is_default=False,
            )
            db.add(agent_workspace)

        await db.commit()
        logger.info(
            "Set workspaces for agent %s: %s",
            agent_id,
            [str(w) for w in workspace_uuids],
        )
        return {"message": "Agent workspaces updated successfully"}
    except DBAPIError as e:
        await db.rollback()
        logger.exception("Database error setting agent workspaces")
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable. Please try again later.",
        ) from e
