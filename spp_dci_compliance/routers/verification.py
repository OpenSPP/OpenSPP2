# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Callback Verification Endpoint for Compliance Testing.

This router provides endpoints for compliance tests to verify that
async callbacks have been received and processed by OpenSPP.

SECURITY NOTE: These endpoints are only available when:
1. Odoo is running in test mode (--test-enable), OR
2. System parameter 'dci.enable_compliance_endpoints' is set to 'true'

See fastapi_endpoint_compliance.py for the protection mechanism.
"""

import logging
from typing import Annotated

from pydantic import BaseModel

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, HTTPException, Query, status

_logger = logging.getLogger(__name__)


class CallbackRecord(BaseModel):
    """Single callback log record."""

    id: int
    transaction_id: str
    correlation_id: str | None = None
    registry_type: str
    callback_type: str
    endpoint: str | None = None
    status: str
    payload_hash: str | None = None
    response_code: int | None = None
    error_message: str | None = None
    processing_time_ms: int | None = None
    sender_id: str | None = None
    received_at: str | None = None


class CallbacksResponse(BaseModel):
    """Response containing callback records."""

    callbacks: list[CallbackRecord]
    total: int


class CallbackStats(BaseModel):
    """Statistics about received callbacks."""

    total: int
    by_status: dict[str, int]
    by_registry_type: dict[str, int]
    by_callback_type: dict[str, int]


class ClearCallbacksResponse(BaseModel):
    """Response for clearing callback logs."""

    deleted: int
    message: str | None = None
    error: str | None = None


verification_router = APIRouter(tags=["DCI Compliance Testing"], prefix="/test")


@verification_router.get(
    "/callbacks",
    response_model=CallbacksResponse,
    response_model_exclude_none=True,
    summary="Get DCI Callback Logs",
    description="""
Query DCI callback logs for compliance testing verification.

This endpoint allows compliance tests to verify that async callbacks
have been received and processed by OpenSPP.

**Use Cases**:
- Verify async search callbacks were received
- Check callback processing status
- Validate callback payload hashes

**Note**: This endpoint is only available in test mode or when explicitly enabled.
""",
)
async def get_callbacks(
    env: Annotated[Environment, Depends(odoo_env)],
    transaction_id: str | None = Query(
        None,
        description="Filter by DCI transaction ID",
    ),
    correlation_id: str | None = Query(
        None,
        description="Filter by DCI correlation ID",
    ),
    registry_type: str | None = Query(
        None,
        description="Filter by registry type (sr, crvs, dr, ibr, fr)",
    ),
    callback_type: str | None = Query(
        None,
        description="Filter by callback type (on_search, on_subscribe, etc.)",
    ),
    # Named status_filter so it does not shadow fastapi.status (used by the
    # exception handlers below); the wire-level query param stays "status".
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status (received, processing, processed, failed)",
    ),
    since_minutes: int | None = Query(
        None,
        description="Only return callbacks from the last N minutes",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of records to return",
    ),
):
    """Query callback logs with optional filters."""
    try:
        # sudo: technical callback-log model; compliance-test-only endpoints
        CallbackLog = env["spp.dci.callback.log"].sudo()  # nosemgrep: odoo-sudo-without-context
        callbacks = CallbackLog.get_callbacks(
            transaction_id=transaction_id,
            correlation_id=correlation_id,
            registry_type=registry_type,
            callback_type=callback_type,
            status=status_filter,
            since_minutes=since_minutes,
            limit=limit,
        )

        _logger.debug(
            "Callback verification query returned %d records (transaction_id=%s, registry_type=%s)",
            len(callbacks),
            transaction_id,
            registry_type,
        )

        return CallbacksResponse(
            callbacks=[CallbackRecord(**cb) for cb in callbacks],
            total=len(callbacks),
        )

    except ValueError as e:
        # Validation error from get_callbacks (invalid filter values)
        _logger.warning("Invalid filter value in callback query: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.error("Error querying callback logs: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while querying callbacks",
        ) from e


@verification_router.get(
    "/callbacks/stats",
    response_model=CallbackStats,
    summary="Get Callback Statistics",
    description="""
Get statistics about received DCI callbacks.

Returns counts grouped by status, registry type, and callback type.
Useful for monitoring callback processing health.
""",
)
async def get_callback_stats(
    env: Annotated[Environment, Depends(odoo_env)],
    since_minutes: int | None = Query(
        60,
        description="Calculate stats for callbacks from the last N minutes",
    ),
):
    """Get callback processing statistics."""
    try:
        # sudo: technical callback-log model; compliance-test-only endpoints
        CallbackLog = env["spp.dci.callback.log"].sudo()  # nosemgrep: odoo-sudo-without-context

        # Build domain for time filter
        domain = []
        if since_minutes:
            from odoo import fields

            since_dt = fields.Datetime.subtract(fields.Datetime.now(), minutes=since_minutes)
            domain.append(("create_date", ">=", since_dt))

        callbacks = CallbackLog.search(domain)

        # Calculate statistics
        by_status: dict[str, int] = {}
        by_registry_type: dict[str, int] = {}
        by_callback_type: dict[str, int] = {}

        for cb in callbacks:
            by_status[cb.status] = by_status.get(cb.status, 0) + 1
            by_registry_type[cb.registry_type] = by_registry_type.get(cb.registry_type, 0) + 1
            by_callback_type[cb.callback_type] = by_callback_type.get(cb.callback_type, 0) + 1

        return CallbackStats(
            total=len(callbacks),
            by_status=by_status,
            by_registry_type=by_registry_type,
            by_callback_type=by_callback_type,
        )

    except Exception as e:
        _logger.error("Error calculating callback stats: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while calculating statistics",
        ) from e


@verification_router.delete(
    "/callbacks",
    response_model=ClearCallbacksResponse,
    summary="Clear Callback Logs",
    description="""
Clear callback logs for testing purposes.

Can clear all logs or only logs older than a specified number of days.

**Warning**: This is a destructive operation intended for test cleanup.
Only available in test mode or when explicitly enabled.
""",
)
async def clear_callbacks(
    env: Annotated[Environment, Depends(odoo_env)],
    older_than_days: int | None = Query(
        None,
        description="Only clear logs older than N days (None = clear all)",
    ),
):
    """Clear callback logs."""
    try:
        # sudo: technical callback-log model; compliance-test-only endpoints
        CallbackLog = env["spp.dci.callback.log"].sudo()  # nosemgrep: odoo-sudo-without-context

        if older_than_days:
            count = CallbackLog.cleanup_old_logs(days=older_than_days)
        else:
            # Clear all
            all_logs = CallbackLog.search([])
            count = len(all_logs)
            all_logs.unlink()

        _logger.info("Cleared %d callback log records", count)

        return ClearCallbacksResponse(
            deleted=count,
            message=f"Cleared {count} callback log records",
        )

    except Exception as e:
        _logger.error("Error clearing callback logs: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while clearing callbacks",
        ) from e


@verification_router.post(
    "/callbacks/wait",
    response_model=CallbacksResponse,
    summary="Wait for Callback",
    description="""
Wait for a specific callback to be received.

Polls until the callback with the specified transaction_id is found
or the timeout is reached.

**Use Case**: Compliance tests can use this to wait for async callbacks
instead of polling the regular endpoint.

**Note**: This endpoint is only available in test mode or when explicitly enabled.
""",
)
async def wait_for_callback(
    env: Annotated[Environment, Depends(odoo_env)],
    transaction_id: str = Query(
        ...,
        description="Transaction ID to wait for",
    ),
    timeout_seconds: int = Query(
        30,
        ge=1,
        le=120,
        description="Maximum time to wait in seconds",
    ),
    poll_interval_ms: int = Query(
        500,
        ge=100,
        le=5000,
        description="Polling interval in milliseconds",
    ),
):
    """Wait for a callback with the specified transaction_id."""
    import asyncio

    # sudo: technical callback-log model; compliance-test-only endpoints
    CallbackLog = env["spp.dci.callback.log"].sudo()  # nosemgrep: odoo-sudo-without-context
    start_time = asyncio.get_event_loop().time()
    poll_interval = poll_interval_ms / 1000

    # Safety: Calculate maximum iterations to prevent infinite loop
    max_iterations = int(timeout_seconds / poll_interval) + 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        try:
            callbacks = CallbackLog.get_callbacks(
                transaction_id=transaction_id,
                limit=10,
            )

            if callbacks:
                return CallbacksResponse(
                    callbacks=[CallbackRecord(**cb) for cb in callbacks],
                    total=len(callbacks),
                )
        except ValueError as e:
            # Should not happen with transaction_id filter, but handle anyway
            _logger.warning("Unexpected validation error in wait: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout_seconds:
            _logger.debug(
                "Timeout waiting for callback transaction_id=%s after %.1fs",
                transaction_id,
                elapsed,
            )
            return CallbacksResponse(callbacks=[], total=0)

        await asyncio.sleep(poll_interval)

    # Safety net: should not reach here, but return empty if we do
    _logger.warning(
        "Max iterations reached waiting for callback transaction_id=%s",
        transaction_id,
    )
    return CallbacksResponse(callbacks=[], total=0)
