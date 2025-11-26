"""API endpoints for user settings."""

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user_settings import UserSettings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class UpdateSettingsRequest(BaseModel):
    """Request to update user settings."""

    openai_api_key: str | None = None
    deepgram_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    telnyx_api_key: str | None = None
    telnyx_public_key: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None


class SettingsResponse(BaseModel):
    """Settings response (API keys masked for security)."""

    openai_api_key_set: bool
    deepgram_api_key_set: bool
    elevenlabs_api_key_set: bool
    telnyx_api_key_set: bool
    twilio_account_sid_set: bool


async def get_current_user_id() -> uuid.UUID:
    """Get current user ID.

    TODO: Implement actual authentication
    """
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=SettingsResponse)
async def get_settings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Get user settings (API keys masked).

    Args:
        user_id: Current user ID
        db: Database session

    Returns:
        Settings with masked API keys
    """
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()

    if not settings:
        return SettingsResponse(
            openai_api_key_set=False,
            deepgram_api_key_set=False,
            elevenlabs_api_key_set=False,
            telnyx_api_key_set=False,
            twilio_account_sid_set=False,
        )

    return SettingsResponse(
        openai_api_key_set=bool(settings.openai_api_key),
        deepgram_api_key_set=bool(settings.deepgram_api_key),
        elevenlabs_api_key_set=bool(settings.elevenlabs_api_key),
        telnyx_api_key_set=bool(settings.telnyx_api_key),
        twilio_account_sid_set=bool(settings.twilio_account_sid),
    )


@router.post("", status_code=status.HTTP_200_OK)
async def update_settings(
    request: UpdateSettingsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update user settings.

    Args:
        request: Settings update request
        user_id: Current user ID
        db: Database session

    Returns:
        Success message
    """
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()

    if settings:
        # Update existing
        if request.openai_api_key is not None:
            settings.openai_api_key = request.openai_api_key or None
        if request.deepgram_api_key is not None:
            settings.deepgram_api_key = request.deepgram_api_key or None
        if request.elevenlabs_api_key is not None:
            settings.elevenlabs_api_key = request.elevenlabs_api_key or None
        if request.telnyx_api_key is not None:
            settings.telnyx_api_key = request.telnyx_api_key or None
        if request.telnyx_public_key is not None:
            settings.telnyx_public_key = request.telnyx_public_key or None
        if request.twilio_account_sid is not None:
            settings.twilio_account_sid = request.twilio_account_sid or None
        if request.twilio_auth_token is not None:
            settings.twilio_auth_token = request.twilio_auth_token or None

        db.add(settings)
    else:
        # Create new
        settings = UserSettings(
            user_id=user_id,
            openai_api_key=request.openai_api_key,
            deepgram_api_key=request.deepgram_api_key,
            elevenlabs_api_key=request.elevenlabs_api_key,
            telnyx_api_key=request.telnyx_api_key,
            telnyx_public_key=request.telnyx_public_key,
            twilio_account_sid=request.twilio_account_sid,
            twilio_auth_token=request.twilio_auth_token,
        )
        db.add(settings)

    await db.commit()

    return {"message": "Settings updated successfully"}


async def get_user_api_keys(user_id: uuid.UUID, db: AsyncSession) -> UserSettings | None:
    """Get user API keys for internal use.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        UserSettings or None
    """
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    return result.scalar_one_or_none()
