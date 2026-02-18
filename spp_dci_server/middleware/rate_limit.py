# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI API rate limiting middleware.

Enforces per-minute and per-day rate limits on DCI API endpoints
using sender registry rate_limit fields.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated, Any

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import Depends, HTTPException, status

from .signature import verify_dci_signature

_logger = logging.getLogger(__name__)


class DCIRateLimitMiddleware:
    """Enforce rate limits on DCI API endpoints.

    Implements sliding window approximation for per-minute limits
    and daily counters for per-day limits.
    """

    @staticmethod
    def check_rate_limit(env: Environment, sender: Any) -> None:
        """Check if sender has exceeded rate limits.

        Args:
            env: Odoo environment
            sender: Sender registry record (spp.dci.sender.registry)

        Raises:
            HTTPException: 429 Too Many Requests if limit exceeded
        """
        if not sender:
            # No sender means unsigned request in dev mode - skip rate limiting
            _logger.warning("Rate limiting skipped - no sender record")
            return

        sender.ensure_one()

        # Get rate limits from sender (inherited from spp.api.client)
        per_minute_limit = sender.rate_limit_per_minute or 60
        per_day_limit = sender.rate_limit_per_day or 10000

        now = datetime.now()

        # ===================================================================
        # PER-MINUTE RATE LIMIT (sliding window approximation)
        # ===================================================================
        # If last request was within the last minute, check counter
        if sender.last_request_minute:
            time_since_last = (now - sender.last_request_minute).total_seconds()

            if time_since_last < 60:
                # Still within the same minute window
                if sender.request_count_minute >= per_minute_limit:
                    _logger.warning(
                        "Rate limit exceeded (per minute) for sender_id=%s: %d/%d requests",
                        sender.id,
                        sender.request_count_minute,
                        per_minute_limit,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "rate_limit_exceeded",
                            "error_code": "RATE_LIMIT_PER_MINUTE",
                            "error_message": f"Rate limit exceeded: {per_minute_limit} requests per minute allowed",
                            "retry_after": int(60 - time_since_last),
                        },
                    )
            else:
                # Minute window has passed - reset counter
                # Use SQL UPDATE for atomic operation
                env.cr.execute(
                    """
                    UPDATE spp_dci_sender_registry
                    SET request_count_minute = 0,
                        last_request_minute = %s
                    WHERE id = %s
                    """,
                    (now, sender.id),
                )
                # Invalidate cache to reflect the update
                sender.invalidate_recordset(["request_count_minute", "last_request_minute"])
        else:
            # First request ever - initialize minute tracking
            env.cr.execute(
                """
                UPDATE spp_dci_sender_registry
                SET request_count_minute = 0,
                    last_request_minute = %s
                WHERE id = %s
                """,
                (now, sender.id),
            )
            sender.invalidate_recordset(["last_request_minute"])

        # ===================================================================
        # PER-DAY RATE LIMIT
        # ===================================================================
        today = now.date()

        # Check if we need to reset daily counter
        if sender.last_request_reset:
            last_reset_date = sender.last_request_reset
            if last_reset_date < today:
                # Day has changed - reset daily counter
                env.cr.execute(
                    """
                    UPDATE spp_dci_sender_registry
                    SET request_count_today = 0,
                        last_request_reset = %s
                    WHERE id = %s
                    """,
                    (today, sender.id),
                )
                sender.invalidate_recordset(["request_count_today", "last_request_reset"])
        else:
            # First request ever - initialize daily tracking
            env.cr.execute(
                """
                UPDATE spp_dci_sender_registry
                SET request_count_today = 0,
                    last_request_reset = %s
                WHERE id = %s
                """,
                (today, sender.id),
            )
            sender.invalidate_recordset(["last_request_reset"])

        # Check daily limit
        if sender.request_count_today >= per_day_limit:
            _logger.warning(
                "Rate limit exceeded (per day) for sender_id=%s: %d/%d requests",
                sender.id,
                sender.request_count_today,
                per_day_limit,
            )
            # Calculate seconds until midnight (reset time)
            tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
            retry_after = int((tomorrow - now).total_seconds())

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "error_code": "RATE_LIMIT_PER_DAY",
                    "error_message": f"Daily rate limit exceeded: {per_day_limit} requests per day allowed",
                    "retry_after": retry_after,
                },
            )

        # ===================================================================
        # INCREMENT COUNTERS
        # ===================================================================
        # Use atomic SQL UPDATE to increment both counters
        env.cr.execute(
            """
            UPDATE spp_dci_sender_registry
            SET request_count_minute = request_count_minute + 1,
                request_count_today = request_count_today + 1,
                last_request_minute = %s
            WHERE id = %s
            """,
            (now, sender.id),
        )

        # Invalidate cache to reflect the updates
        sender.invalidate_recordset(["request_count_minute", "request_count_today", "last_request_minute"])

        _logger.debug(
            "Rate limit check passed for sender_id=%s (minute: %d/%d, day: %d/%d)",
            sender.id,
            sender.request_count_minute + 1,  # +1 because we just incremented
            per_minute_limit,
            sender.request_count_today + 1,
            per_day_limit,
        )


async def check_dci_rate_limit(
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
) -> None:
    """FastAPI dependency for DCI rate limiting.

    Args:
        env: Odoo environment
        verified_sender_id: Sender ID from signature verification (via dependency)

    Raises:
        HTTPException: 429 Too Many Requests if limit exceeded
    """
    # Look up sender registry record
    sender = (
        env["spp.dci.sender.registry"]
        .sudo()
        .search(
            [("sender_id", "=", verified_sender_id)],
            limit=1,
        )
    )

    # Apply rate limiting
    DCIRateLimitMiddleware.check_rate_limit(env, sender)
