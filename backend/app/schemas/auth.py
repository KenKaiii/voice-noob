"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: int
    exp: int


class UserRegister(BaseModel):
    """User registration schema."""

    email: EmailStr
    password: str
    full_name: str | None = None


class UserLogin(BaseModel):
    """User login schema."""

    email: EmailStr
    password: str


class RefreshToken(BaseModel):
    """Refresh token request schema."""

    refresh_token: str
