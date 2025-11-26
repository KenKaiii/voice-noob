"""Appointment model for CRM."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.workspace import Workspace


class Appointment(Base, TimestampMixin):
    """Appointment model - bookings made via voice agents."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)

    # Workspace association (nullable for migration, will be required after data migration)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Agent that created this appointment (UUID reference)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Appointment details
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        index=True,
    )  # scheduled, completed, cancelled, no_show

    # Service/appointment type
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Notes and details
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)

    # Which voice agent created this appointment (optional)
    created_by_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    workspace: Mapped["Workspace | None"] = relationship("Workspace", back_populates="appointments")
    contact: Mapped["Contact"] = relationship("Contact", back_populates="appointments")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Appointment {self.id} - {self.scheduled_at} ({self.status})>"
