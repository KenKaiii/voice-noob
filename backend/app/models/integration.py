"""Integration model for storing user API credentials."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Integration(Base, TimestampMixin):
    """User integration credentials model."""

    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Integration type (openai, deepgram, elevenlabs, telnyx, twilio, salesforce, etc.)
    integration_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Friendly name for display
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # API credentials
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)

    # OAuth tokens (encrypted in production)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expiry: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Additional metadata
    account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="integrations")
