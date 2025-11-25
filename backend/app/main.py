"""Main FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import agents, crm, health, realtime
from app.api import settings as settings_api
from app.core.config import settings
from app.core.limiter import limiter
from app.db.redis import close_redis, get_redis
from app.db.session import engine
from app.middleware.security import SecurityHeadersMiddleware

# Configure structured logging with async processors
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.WARNING if not settings.DEBUG else logging.DEBUG
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("Starting application", app_name=settings.APP_NAME)

    try:
        # Initialize Redis (fatal if fails)
        await get_redis()
        logger.info("Redis connection established")
    except Exception:
        logger.exception("Failed to initialize Redis - application cannot start")
        raise  # Re-raise to prevent app startup

    # Initialize Sentry if configured (non-fatal)
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.SENTRY_ENVIRONMENT,
                traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            )
            logger.info("Sentry initialized")
        except Exception:
            logger.exception("Failed to initialize Sentry - continuing without error tracking")

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Close Redis connection
    try:
        await close_redis()
        logger.info("Redis connection closed")
    except Exception:
        logger.exception("Error closing Redis connection")

    # Dispose database engine and close all connections
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception:
        logger.exception("Error closing database connections")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(crm.router, prefix=settings.API_V1_PREFIX)
app.include_router(agents.router)
app.include_router(settings_api.router)
app.include_router(realtime.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
    )
