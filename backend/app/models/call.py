"""Call model for tracking call history and logs."""

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.phone_number import PhoneNumber
    from app.models.user import User
    from app.models.voice_agent import VoiceAgent


class Call(Base, TimestampMixin):
    """Call history model."""

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_agent_id: Mapped[int] = mapped_column(
        ForeignKey("voice_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number_id: Mapped[int] = mapped_column(
        ForeignKey("phone_numbers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Call details
    call_sid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # inbound, outbound
    from_number: Mapped[str] = mapped_column(String(20), nullable=False)
    to_number: Mapped[str] = mapped_column(String(20), nullable=False)

    # Call status and duration
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # initiated, ringing, in-progress, completed, failed
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Transcript and recording
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Cost tracking
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="calls")
    voice_agent: Mapped["VoiceAgent"] = relationship("VoiceAgent", back_populates="calls")
    phone_number: Mapped["PhoneNumber"] = relationship("PhoneNumber", back_populates="calls")
