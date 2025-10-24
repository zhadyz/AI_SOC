"""
Rate Limiting Middleware - Common Utilities
AI-Augmented SOC - Production Security

Implements sliding window rate limiting for API endpoints.
Prevents DoS attacks and ensures fair resource usage.

Author: LOVELESS (Elite Security Specialist)
Mission: OPERATION SECURITY-FORTRESS
Date: 2025-10-23
"""

import logging
import time
from typing import Optional, Dict, Callable
from collections import defaultdict, deque
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter with per-client tracking.

    Implements a sliding window algorithm for accurate rate limiting:
    - Tracks requests per time window
    - Supports per-IP and per-API-key limits
    - Automatic cleanup of old entries
    """

    def __init__(
        self,
        requests_per_window: int,
        window_seconds: int,
        cleanup_interval: int = 300
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_window: Maximum requests allowed per window
            window_seconds: Time window in seconds
            cleanup_interval: Cleanup old entries every N seconds
        """
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # Store: client_id -> deque of timestamps
        self.request_log: Dict[str, deque] = defaultdict(deque)

        # Last cleanup time
        self.last_cleanup = time.time()

        logger.info(
            f"Rate limiter initialized: {requests_per_window} req/{window_seconds}s"
        )

    def _cleanup_old_entries(self):
        """Remove expired entries from memory."""
        current_time = time.time()

        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        cutoff_time = current_time - self.window_seconds
        cleaned_clients = 0

        for client_id, timestamps in list(self.request_log.items()):
            # Remove old timestamps
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()

            # Remove empty entries
            if not timestamps:
                del self.request_log[client_id]
                cleaned_clients += 1

        self.last_cleanup = current_time

        if cleaned_clients > 0:
            logger.debug(f"Cleaned up {cleaned_clients} inactive clients")

    def is_allowed(self, client_id: str) -> tuple[bool, Optional[float]]:
        """
        Check if request is allowed for client.

        Args:
            client_id: Client identifier (IP or API key)

        Returns:
            tuple: (is_allowed, retry_after_seconds)
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        # Cleanup periodically
        self._cleanup_old_entries()

        # Get client's request log
        timestamps = self.request_log[client_id]

        # Remove expired timestamps
        while timestamps and timestamps[0] < cutoff_time:
            timestamps.popleft()

        # Check if limit exceeded
        if len(timestamps) >= self.requests_per_window:
            # Calculate retry time
            oldest_timestamp = timestamps[0]
            retry_after = oldest_timestamp + self.window_seconds - current_time

            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{len(timestamps)}/{self.requests_per_window} in {self.window_seconds}s"
            )

            return False, max(0, retry_after)

        # Allow request and log timestamp
        timestamps.append(current_time)
        return True, None

    def get_remaining_requests(self, client_id: str) -> int:
        """
        Get remaining requests for client in current window.

        Args:
            client_id: Client identifier

        Returns:
            int: Remaining requests allowed
        """
        current_time = time.time()
        cutoff_time = current_time - self.window_seconds

        timestamps = self.request_log.get(client_id, deque())

        # Count valid timestamps
        valid_count = sum(1 for ts in timestamps if ts > cutoff_time)
        remaining = max(0, self.requests_per_window - valid_count)

        return remaining

    def reset_client(self, client_id: str):
        """
        Reset rate limit for a client.

        Args:
            client_id: Client identifier
        """
        if client_id in self.request_log:
            del self.request_log[client_id]
            logger.info(f"Reset rate limit for {client_id}")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limits to all endpoints with configurable rules.
    """

    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 60,
        endpoint_limits: Optional[Dict[str, tuple[int, int]]] = None,
        get_client_id: Optional[Callable] = None
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            default_limit: Default requests per window
            default_window: Default window in seconds
            endpoint_limits: Custom limits per endpoint {path: (limit, window)}
            get_client_id: Custom function to extract client ID
        """
        super().__init__(app)

        # Default rate limiter
        self.default_limiter = SlidingWindowRateLimiter(
            default_limit,
            default_window
        )

        # Endpoint-specific limiters
        self.endpoint_limiters: Dict[str, SlidingWindowRateLimiter] = {}

        if endpoint_limits:
            for path, (limit, window) in endpoint_limits.items():
                self.endpoint_limiters[path] = SlidingWindowRateLimiter(
                    limit,
                    window
                )

        self.get_client_id = get_client_id or self._default_client_id

        logger.info(
            f"Rate limit middleware initialized: "
            f"default={default_limit}/{default_window}s, "
            f"custom_endpoints={len(self.endpoint_limiters)}"
        )

    def _default_client_id(self, request: Request) -> str:
        """
        Extract client ID from request.

        Priority:
        1. API key from Authorization header
        2. X-Forwarded-For header (behind proxy)
        3. Client IP address

        Args:
            request: FastAPI request

        Returns:
            str: Client identifier
        """
        # Check for API key
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            if token.startswith("aisoc_"):
                return f"key:{token[:20]}"  # Use key prefix

        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in chain
            return forwarded_for.split(",")[0].strip()

        # Use direct client IP
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        """
        Process request through rate limiter.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with rate limit headers
        """
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client ID
        client_id = self.get_client_id(request)

        # Get appropriate limiter
        limiter = self.endpoint_limiters.get(
            request.url.path,
            self.default_limiter
        )

        # Check rate limit
        is_allowed, retry_after = limiter.is_allowed(client_id)

        if not is_allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: client={client_id}, "
                f"path={request.url.path}, retry_after={retry_after:.1f}s"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Too many requests. Please retry after {int(retry_after)} seconds",
                    "retry_after": int(retry_after)
                },
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(limiter.requests_per_window),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after))
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = limiter.get_remaining_requests(client_id)
        reset_time = int(time.time() + limiter.window_seconds)

        response.headers["X-RateLimit-Limit"] = str(limiter.requests_per_window)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response


# Predefined rate limit profiles
RATE_LIMIT_PROFILES = {
    "strict": {
        "default_limit": 30,
        "default_window": 60,
        "endpoint_limits": {
            "/analyze": (10, 60),  # 10 req/min for AI inference
            "/batch": (5, 60),     # 5 req/min for batch processing
            "/retrieve": (20, 60)   # 20 req/min for RAG queries
        }
    },
    "moderate": {
        "default_limit": 100,
        "default_window": 60,
        "endpoint_limits": {
            "/analyze": (30, 60),
            "/batch": (10, 60),
            "/retrieve": (50, 60)
        }
    },
    "permissive": {
        "default_limit": 300,
        "default_window": 60,
        "endpoint_limits": {
            "/analyze": (100, 60),
            "/batch": (50, 60),
            "/retrieve": (150, 60)
        }
    }
}


def create_rate_limit_middleware(
    app,
    profile: str = "moderate",
    custom_limits: Optional[Dict] = None
) -> RateLimitMiddleware:
    """
    Factory function to create rate limit middleware.

    Args:
        app: FastAPI application
        profile: Rate limit profile (strict/moderate/permissive)
        custom_limits: Custom limit configuration

    Returns:
        RateLimitMiddleware: Configured middleware
    """
    if custom_limits:
        config = custom_limits
    elif profile in RATE_LIMIT_PROFILES:
        config = RATE_LIMIT_PROFILES[profile]
    else:
        logger.warning(f"Unknown profile '{profile}', using 'moderate'")
        config = RATE_LIMIT_PROFILES["moderate"]

    return RateLimitMiddleware(app, **config)
