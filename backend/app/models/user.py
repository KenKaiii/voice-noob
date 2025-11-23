"""User model for authentication and authorization."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.call import Call
    from app.models.integration import Integration
    from app.models.phone_number import PhoneNumber
    from app.models.voice_agent import VoiceAgent


class User(Base, TimestampMixin):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    voice_agents: Mapped[list["VoiceAgent"]] = relationship(
        "VoiceAgent",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(
        "PhoneNumber",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    calls: Mapped[list["Call"]] = relationship(
        "Call",
        back_populates="user",
        cascade="all, delete-orphan",
    )
