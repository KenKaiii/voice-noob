"""Voice agent schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VoiceAgentBase(BaseModel):
    """Base voice agent schema."""

    name: str
    description: str | None = None
    pricing_tier: str
    system_prompt: str
    voice_id: str | None = None
    temperature: float = 0.7
    phone_number_id: int | None = None
    enabled_integrations: list[int] = []
    is_active: bool = True


class VoiceAgentCreate(VoiceAgentBase):
    """Voice agent creation schema."""

    llm_config: dict
    stt_config: dict
    tts_config: dict


class VoiceAgentUpdate(BaseModel):
    """Voice agent update schema."""

    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    voice_id: str | None = None
    temperature: float | None = None
    phone_number_id: int | None = None
    enabled_integrations: list[int] | None = None
    is_active: bool | None = None


class VoiceAgentResponse(VoiceAgentBase):
    """Voice agent response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    llm_config: dict
    stt_config: dict
    tts_config: dict
    created_at: datetime
    updated_at: datetime
