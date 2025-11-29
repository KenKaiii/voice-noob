"""Voice agent model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.workspace import AgentWorkspace


class Agent(Base):
    """Voice agent configuration.

    Stores configuration for a voice agent including:
    - Pricing tier (determines voice provider: Budget/Balanced/Premium)
    - System prompt and personality
    - Enabled integrations/tools
    - Phone number assignment
    - Recording/transcript settings
    """

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True, comment="Owner user ID"
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="Agent name")
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Agent description"
    )

    # Pricing tier determines voice provider
    pricing_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Pricing tier: budget, balanced, premium-mini, or premium",
    )

    # Agent configuration
    system_prompt: Mapped[str] = mapped_column(
        Text, nullable=False, comment="System prompt/instructions for agent"
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en-US", comment="Agent language (e.g., en-US, es-ES)"
    )
    voice: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="shimmer",
        comment="Voice for TTS (e.g., alloy, shimmer, coral)",
    )

    # Turn detection settings (for OpenAI Realtime API)
    turn_detection_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="Turn detection mode: normal, semantic, or disabled",
    )
    turn_detection_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="VAD threshold (0.0-1.0)",
    )
    turn_detection_prefix_padding_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Prefix padding in milliseconds",
    )
    turn_detection_silence_duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=500,
        comment="Silence duration in milliseconds before turn ends",
    )

    # LLM settings
    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
        comment="LLM temperature (0.0-2.0)",
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2000,
        comment="Maximum response tokens",
    )

    # Integrations/tools
    enabled_tools: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="List of enabled integration IDs (legacy, for backward compatibility)",
    )
    enabled_tool_ids: Mapped[dict[str, list[str]]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Granular tool selection: {integration_id: [tool_id1, tool_id2]}",
    )

    # Phone settings
    phone_number_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Assigned phone number ID (Telnyx/Twilio)"
    )
    enable_recording: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Enable call recording"
    )
    enable_transcript: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Enable call transcription"
    )

    # Provider configuration (auto-generated from pricing_tier)
    provider_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Voice provider configuration (LLM, STT, TTS settings)",
    )

    # Agent status
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="Whether agent is active"
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Whether agent is published/deployed"
    )

    # Statistics
    total_calls: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Total number of calls handled"
    )
    total_duration_seconds: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Total call duration in seconds"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Last time agent handled a call"
    )

    # Relationships
    agent_workspaces: Mapped[list["AgentWorkspace"]] = relationship(
        "AgentWorkspace", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Agent(id={self.id}, name={self.name}, "
            f"tier={self.pricing_tier}, user_id={self.user_id})>"
        )
