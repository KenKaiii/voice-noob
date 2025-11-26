"""CallInteraction model for CRM - tracks voice agent calls."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.workspace import Workspace


class CallInteraction(Base, TimestampMixin):
    """CallInteraction model - logs all voice agent interactions with contacts."""

    __tablename__ = "call_interactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)

    # Workspace association (nullable for migration, will be required after data migration)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Call details
    call_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    call_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Voice agent info
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Call outcome
    outcome: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # answered, voicemail, no_answer, callback_requested, busy

    # AI-generated content
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)

    # Sentiment analysis (optional, -1.0 to 1.0)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Action items extracted from call (JSON or comma-separated)
    action_items: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)

    # Additional notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, deferred=True)

    # Relationships
    workspace: Mapped["Workspace | None"] = relationship(
        "Workspace", back_populates="call_interactions"
    )
    contact: Mapped["Contact"] = relationship("Contact", back_populates="call_interactions")

    def __repr__(self) -> str:
        """String representation."""
        return f"<CallInteraction {self.id} - {self.call_started_at} ({self.outcome})>"
