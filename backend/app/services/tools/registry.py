"""Tool registry for managing available tools for voice agents."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tools.crm_tools import CRMTools


class ToolRegistry:
    """Registry of all available tools for voice agents.

    Manages:
    - Internal tools (CRM, bookings)
    - External integrations (when needed)
    - Tool execution routing
    """

    def __init__(self, db: AsyncSession, user_id: uuid.UUID) -> None:
        """Initialize tool registry.

        Args:
            db: Database session
            user_id: User ID
        """
        self.db = db
        self.user_id = user_id
        self.crm_tools = CRMTools(db, user_id)

    def get_all_tool_definitions(self, enabled_tools: list[str]) -> list[dict[str, Any]]:
        """Get tool definitions for enabled tools.

        Args:
            enabled_tools: List of enabled tool IDs

        Returns:
            List of OpenAI function calling tool definitions
        """
        tools: list[dict[str, Any]] = []

        # Internal CRM tools - always available if "crm" is enabled
        if "crm" in enabled_tools or "bookings" in enabled_tools:
            tools.extend(CRMTools.get_tool_definitions())

        return tools

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by routing to appropriate handler.

        Args:
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        # CRM tools
        crm_tool_names = {
            "search_customer",
            "create_contact",
            "check_availability",
            "book_appointment",
            "list_appointments",
            "cancel_appointment",
            "reschedule_appointment",
        }

        if tool_name in crm_tool_names:
            return await self.crm_tools.execute_tool(tool_name, arguments)

        # Unknown tool
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
