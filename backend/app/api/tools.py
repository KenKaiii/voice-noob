"""API endpoints for tool execution."""

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import get_current_user_id
from app.db.session import get_db
from app.services.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])
logger = structlog.get_logger()


class ToolExecuteRequest(BaseModel):
    """Request body for tool execution."""

    tool_name: str
    arguments: dict[str, Any]
    agent_id: str


@router.post("/execute")
async def execute_tool(
    request: ToolExecuteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Execute a tool and return the result.

    This endpoint is called by the frontend when the GPT Realtime model
    makes a function call. The tool is executed on the backend and the
    result is returned to be sent back to the model.

    Args:
        request: Tool execution request
        user_id: Current user ID
        db: Database session

    Returns:
        Tool execution result
    """
    tool_logger = logger.bind(
        endpoint="execute_tool",
        tool_name=request.tool_name,
        agent_id=request.agent_id,
        user_id=str(user_id),
    )

    tool_logger.info("tool_execution_requested", arguments=request.arguments)

    try:
        # Create tool registry and execute tool
        tool_registry = ToolRegistry(db, user_id)
        result = await tool_registry.execute_tool(request.tool_name, request.arguments)

        tool_logger.info("tool_execution_completed", success=result.get("success", False))

        return result

    except Exception as e:
        tool_logger.exception("tool_execution_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {e!s}") from e
