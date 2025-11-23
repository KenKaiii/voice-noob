"""Integration schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegrationBase(BaseModel):
    """Base integration schema."""

    integration_type: str
    name: str
    is_active: bool = True


class IntegrationCreate(IntegrationBase):
    """Integration creation schema."""

    api_key: str | None = None
    api_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_expiry: str | None = None
    account_id: str | None = None


class IntegrationUpdate(BaseModel):
    """Integration update schema."""

    name: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    is_active: bool | None = None


class IntegrationResponse(IntegrationBase):
    """Integration response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_id: str | None = None
    created_at: datetime
    updated_at: datetime
