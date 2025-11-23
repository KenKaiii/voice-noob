"""Phone number model for managing purchased phone numbers."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.call import Call
    from app.models.user import User
    from app.models.voice_agent import VoiceAgent


class PhoneNumber(Base, TimestampMixin):
    """Phone number model."""

    __tablename__ = "phone_numbers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Phone number details
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(5), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # telnyx, twilio

    # Provider-specific IDs
    provider_phone_number_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="phone_numbers")
    voice_agent: Mapped["VoiceAgent"] = relationship(
        "VoiceAgent",
        back_populates="phone_number",
        uselist=False,
    )
    calls: Mapped[list["Call"]] = relationship(
        "Call",
        back_populates="phone_number",
        cascade="all, delete-orphan",
    )
