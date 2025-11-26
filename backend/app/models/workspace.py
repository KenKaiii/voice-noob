"""Workspace model for organizing agents, contacts, and appointments."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.appointment import Appointment
    from app.models.call_interaction import CallInteraction
    from app.models.contact import Contact
    from app.models.user import User


class Workspace(Base, TimestampMixin):
    """Workspace for organizing agents and CRM data.

    Workspaces allow users to organize their voice agents and CRM data
    into logical groups (e.g., different businesses, departments, or projects).

    Each workspace has its own:
    - Contacts (CRM)
    - Appointments
    - Call interactions
    - Business settings (hours, timezone, booking rules)

    Agents can belong to multiple workspaces via the AgentWorkspace junction table.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="Workspace name")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Workspace description"
    )

    # Settings JSON field for flexible configuration
    # Contains: timezone, business_hours, booking_buffer_minutes,
    # max_advance_booking_days, default_appointment_duration, allow_same_day_booking
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Workspace settings (timezone, business hours, booking rules)",
    )

    # Default workspace flag (one per user)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="User's default workspace"
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workspaces")
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="workspace", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="workspace", cascade="all, delete-orphan"
    )
    call_interactions: Mapped[list["CallInteraction"]] = relationship(
        "CallInteraction", back_populates="workspace", cascade="all, delete-orphan"
    )
    agent_workspaces: Mapped[list["AgentWorkspace"]] = relationship(
        "AgentWorkspace", back_populates="workspace", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Workspace {self.id} - {self.name}>"


class AgentWorkspace(Base, TimestampMixin):
    """Junction table linking agents to workspaces.

    Allows many-to-many relationship between agents and workspaces:
    - An agent can serve multiple workspaces
    - A workspace can have multiple agents
    """

    __tablename__ = "agent_workspaces"
    __table_args__ = (UniqueConstraint("agent_id", "workspace_id", name="uq_agent_workspace"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Is this the agent's default/primary workspace?
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Agent's default workspace for new contacts/appointments",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="agent_workspaces")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="agent_workspaces")

    def __repr__(self) -> str:
        """String representation."""
        return f"<AgentWorkspace agent={self.agent_id} workspace={self.workspace_id}>"
