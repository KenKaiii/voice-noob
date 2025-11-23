"""Rate limiter configuration."""

import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def log_rate_limit_violation(request_route: str) -> None:
    """Log rate limit violations."""
    logger.warning("Rate limit exceeded for route: %s", request_route)


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
