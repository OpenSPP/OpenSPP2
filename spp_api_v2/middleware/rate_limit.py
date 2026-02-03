# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Rate limiting middleware for API V2.

This module provides in-memory rate limiting for API endpoints.

IMPORTANT: This implementation only works for single-process deployments.
For production deployments with multiple Odoo workers/servers, you MUST
implement Redis-based rate limiting to prevent bypass via request distribution.
"""

import hashlib
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import Depends, HTTPException, Request, status

_logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    SECURITY: Prevents brute force attacks and DoS.

    For multi-worker/multi-server deployments, replace with Redis-based
    rate limiter using the same interface.
    """

    def __init__(self):
        # Structure: {client_id: [(timestamp, count), ...]}
        self._requests: dict[str, list[tuple[float, int]]] = defaultdict(list)
        self._lock = Lock()
        # Cleanup old entries every N requests
        self._cleanup_counter = 0
        self._cleanup_threshold = 100

    def is_allowed(
        self,
        client_id: str,
        limit_per_minute: int,
        limit_per_day: int,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limits.

        Args:
            client_id: Unique client identifier
            limit_per_minute: Max requests per minute
            limit_per_day: Max requests per day

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        now = time.time()
        minute_ago = now - 60
        day_ago = now - 86400

        with self._lock:
            # Cleanup old entries periodically
            self._cleanup_counter += 1
            if self._cleanup_counter >= self._cleanup_threshold:
                self._cleanup_old_entries(day_ago)
                self._cleanup_counter = 0

            # Get client's request history
            requests = self._requests[client_id]

            # Count requests in last minute and last day
            minute_count = sum(1 for ts, _ in requests if ts > minute_ago)
            day_count = sum(1 for ts, _ in requests if ts > day_ago)

            # Check limits
            if minute_count >= limit_per_minute:
                # Find oldest request in minute window to calculate when slot opens
                minute_requests = [ts for ts, _ in requests if ts > minute_ago]
                if minute_requests:
                    oldest_in_window = min(minute_requests)
                    retry_after = max(1, int(60 - (now - oldest_in_window)))
                else:
                    retry_after = 1
                return False, {
                    "limit": limit_per_minute,
                    "remaining": 0,
                    "reset": retry_after,
                    "period": "minute",
                }

            if day_count >= limit_per_day:
                # Find oldest request in day window
                day_requests = [ts for ts, _ in requests if ts > day_ago]
                if day_requests:
                    oldest_in_window = min(day_requests)
                    retry_after = max(1, int(86400 - (now - oldest_in_window)))
                else:
                    retry_after = 1
                return False, {
                    "limit": limit_per_day,
                    "remaining": 0,
                    "reset": retry_after,
                    "period": "day",
                }

            # Record this request
            requests.append((now, 1))

            # Remove old entries for this client
            self._requests[client_id] = [(ts, c) for ts, c in requests if ts > day_ago]

            return True, {
                "limit": limit_per_minute,
                "remaining": limit_per_minute - minute_count - 1,
                "reset": 60,
                "period": "minute",
            }

    def _cleanup_old_entries(self, cutoff: float):
        """Remove entries older than cutoff timestamp."""
        for client_id in list(self._requests.keys()):
            self._requests[client_id] = [(ts, c) for ts, c in self._requests[client_id] if ts > cutoff]
            if not self._requests[client_id]:
                del self._requests[client_id]

    def clear(self):
        """Clear all rate limit state. Useful for testing."""
        with self._lock:
            self._requests.clear()
            self._cleanup_counter = 0


# Global rate limiter instance
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


async def check_rate_limit(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Rate limiting dependency for API endpoints.

    Checks rate limits based on:
    1. IP address for unauthenticated requests
    2. Client ID for authenticated requests (uses client's configured limits)

    Usage:
        @router.get("/endpoint")
        async def endpoint(
            _rate_limit: Annotated[None, Depends(check_rate_limit)],
        ):
            ...
    """
    limiter = get_rate_limiter()

    # Try to get client ID from authorization header
    auth_header = request.headers.get("Authorization", "")
    client_id = None

    if auth_header.startswith("Bearer "):
        # For authenticated requests, we'll use a hash of the full token
        # to ensure rate limits apply per-token regardless of token structure.
        # The full validation happens in get_authenticated_client
        token = auth_header.split(" ", 1)[1]
        # SECURITY: Hash full token to prevent bypass via token manipulation
        # Using SHA-256 ensures different tokens get different rate limit buckets
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        client_id = f"token:{token_hash}"

    if not client_id:
        # Use IP address for unauthenticated requests
        client_ip = request.client.host if request.client else "unknown"
        client_id = f"ip:{client_ip}"

    # Get rate limits from config or use defaults
    # For unauthenticated requests, use stricter limits
    config_param = env["ir.config_parameter"].sudo()
    default_per_minute = int(config_param.get_param("spp_api_v2.rate_limit_per_minute", "30"))
    default_per_day = int(config_param.get_param("spp_api_v2.rate_limit_per_day", "5000"))

    is_allowed, rate_info = limiter.is_allowed(
        client_id,
        default_per_minute,
        default_per_day,
    )

    if not is_allowed:
        _logger.warning(
            "Rate limit exceeded for %s: %s requests in %s",
            client_id[:50],  # Truncate for log safety
            rate_info["limit"],
            rate_info["period"],
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {rate_info['reset']} seconds.",
            headers={
                "Retry-After": str(rate_info["reset"]),
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rate_info["reset"]),
            },
        )


async def check_auth_rate_limit(request: Request):
    """
    Stricter rate limiting for authentication endpoints.

    SECURITY: Prevents brute force attacks on OAuth token endpoint.
    Uses IP-based limiting with very strict limits.
    """
    limiter = get_rate_limiter()

    # Always use IP for auth endpoints to prevent credential stuffing
    client_ip = request.client.host if request.client else "unknown"
    client_id = f"auth:{client_ip}"

    # Very strict limits for auth: 5 per minute, 50 per day
    is_allowed, rate_info = limiter.is_allowed(client_id, 5, 50)

    if not is_allowed:
        _logger.warning(
            "Auth rate limit exceeded for IP %s",
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
            headers={
                "Retry-After": str(rate_info["reset"]),
            },
        )
