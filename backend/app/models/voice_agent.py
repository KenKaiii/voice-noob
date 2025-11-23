"""Voice agent model for storing agent configurations."""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.call import Call
    from app.models.phone_number import PhoneNumber
    from app.models.user import User


class VoiceAgent(Base, TimestampMixin):
    """Voice agent configuration model."""

    __tablename__ = "voice_agents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing tier configuration
    pricing_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # budget, balanced, premium

    # Provider configuration (stored as JSON)
    llm_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # {provider, model, params}
    stt_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # {provider, model, params}
    tts_config: Mapped[dict] = mapped_column(JSON, nullable=False)  # {provider, model, params}

    # Agent behavior
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    voice_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    temperature: Mapped[float] = mapped_column(default=0.7, nullable=False)

    # Phone number assignment
    phone_number_id: Mapped[int | None] = mapped_column(
        ForeignKey("phone_numbers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Tool/integration assignments (stored as JSON array of integration IDs)
    enabled_integrations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="voice_agents")
    phone_number: Mapped["PhoneNumber"] = relationship("PhoneNumber", back_populates="voice_agent")
    calls: Mapped[list["Call"]] = relationship(
        "Call",
        back_populates="voice_agent",
        cascade="all, delete-orphan",
    )
