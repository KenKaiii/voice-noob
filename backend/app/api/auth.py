"""Authentication API routes."""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = structlog.get_logger()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Pydantic Models
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str  # Will be used as full_name
    password: str


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User response."""

    id: int
    email: str
    username: str | None = None  # Maps to full_name

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        """Create response from User model."""
        return cls(id=user.id, email=user.email, username=user.full_name)


# =============================================================================
# Helper Functions
# =============================================================================


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(subject: str | int, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        subject: The subject of the token (user ID or email)
        expires_delta: Optional custom expiration time. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"sub": str(subject), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


# =============================================================================
# Auth Endpoints
# =============================================================================


@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")  # Strict rate limit to prevent account spam
async def register(
    request: RegisterRequest,
    http_request: Request,  # Required for rate limiter
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Register a new user.

    Args:
        request: Registration request with email, username, password
        db: Database session

    Returns:
        Created user
    """
    log = logger.bind(email=request.email, username=request.username)
    log.info("registering_user")

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user (username is stored as full_name)
    user = User(
        email=request.email,
        full_name=request.username,
        hashed_password=get_password_hash(request.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    log.info("user_registered", user_id=user.id)
    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # Strict rate limit to prevent brute force attacks
async def login(
    request: Request,  # Required for rate limiter
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Login and get an access token.

    Args:
        form_data: OAuth2 form with username (email) and password
        db: Database session

    Returns:
        Access token
    """
    log = logger.bind(username=form_data.username)
    log.info("login_attempt")

    # Find user by email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        log.warning("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.id)
    log.info("login_success", user_id=user.id)

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUser) -> UserResponse:
    """Get current user information.

    Args:
        current_user: Authenticated user

    Returns:
        User information
    """
    return UserResponse.from_user(current_user)
