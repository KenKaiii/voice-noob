"""Call record model for telephony call history."""

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.contact import Contact


class CallDirection(str, Enum):
    """Call direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    """Call status."""

    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    CANCELED = "canceled"


class CallRecord(Base):
    """Telephony call record.

    Stores details of each phone call made or received via Twilio/Telnyx.
    """

    __tablename__ = "call_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True, comment="Owner user ID"
    )

    # Provider call identifiers
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Telephony provider: twilio or telnyx"
    )
    provider_call_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Provider call ID (CallSid for Twilio, call_control_id for Telnyx)",
    )

    # Agent reference
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Agent that handled the call",
    )

    # Contact reference (if call was to/from a CRM contact)
    contact_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="CRM contact if applicable",
    )

    # Call details
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Call direction: inbound or outbound"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CallStatus.INITIATED.value,
        comment="Call status",
    )
    from_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Caller phone number"
    )
    to_number: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Recipient phone number"
    )

    # Call metrics
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Call duration in seconds"
    )

    # Recording and transcript
    recording_url: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="URL to call recording"
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Call transcript")

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the call was initiated",
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the call was answered"
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="When the call ended"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    agent: Mapped["Agent | None"] = relationship("Agent", lazy="selectin")
    contact: Mapped["Contact | None"] = relationship("Contact", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<CallRecord(id={self.id}, direction={self.direction}, "
            f"status={self.status}, from={self.from_number}, to={self.to_number})>"
        )
