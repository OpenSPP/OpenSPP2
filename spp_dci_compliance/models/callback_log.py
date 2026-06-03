# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Callback Log model for compliance testing.

This module provides callback logging for DCI compliance verification.
PII is sanitized before storage to comply with data protection requirements.
"""

import hashlib
import json
import logging
import time
from enum import Enum
from typing import Any

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class RegistryType(str, Enum):
    """DCI Registry types for callback logging."""

    SR = "sr"
    CRVS = "crvs"
    DR = "dr"
    IBR = "ibr"
    FR = "fr"


class CallbackType(str, Enum):
    """DCI Callback types."""

    ON_SEARCH = "on_search"
    ON_SUBSCRIBE = "on_subscribe"
    ON_UNSUBSCRIBE = "on_unsubscribe"
    ON_TXN_STATUS = "on_txn_status"
    NOTIFY = "notify"


class CallbackStatus(str, Enum):
    """Callback processing status."""

    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# Sets for fast validation
VALID_REGISTRY_TYPES = {t.value for t in RegistryType}
VALID_CALLBACK_TYPES = {t.value for t in CallbackType}
VALID_STATUSES = {s.value for s in CallbackStatus}

# PII fields to redact from payload logging
PII_FIELDS = frozenset(
    {
        "name",
        "given_name",
        "family_name",
        "first_name",
        "last_name",
        "middle_name",
        "birthdate",
        "birth_date",
        "date_of_birth",
        "address",
        "address_line1",
        "address_line2",
        "street",
        "city",
        "phone",
        "phone_number",
        "mobile",
        "email",
        "email_address",
        "identifier_value",
        "id_value",
        "national_id",
        "passport",
        "ssn",
        "social_security",
        "reg_records",
        "personal_details",
        "identifiers",
    }
)


def _sanitize_payload(payload: dict[str, Any]) -> str:
    """Remove PII fields from payload before logging.

    Args:
        payload: The callback payload dict

    Returns:
        JSON string with PII fields redacted
    """
    if not payload:
        return None

    def redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: "[REDACTED]" if k.lower() in PII_FIELDS else redact(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [redact(item) for item in obj]
        return obj

    try:
        sanitized = redact(payload)
        return json.dumps(sanitized, default=str)
    except (TypeError, ValueError) as e:
        _logger.warning("Failed to sanitize payload: %s", str(e))
        return '{"error": "Failed to sanitize payload"}'


class DCICallbackLog(models.Model):
    """Log of DCI callbacks received for compliance testing.

    This model tracks all DCI callbacks received by OpenSPP, allowing
    compliance tests to verify that async operations complete correctly.

    SECURITY: Payloads are sanitized to remove PII before storage.

    Usage:
        1. DCI callback endpoints call log_callback() when receiving callbacks
        2. Compliance tests query the /test/callbacks endpoint to verify
        3. Logs are automatically cleaned up after a configurable period
    """

    _name = "spp.dci.callback.log"
    _description = "DCI Callback Log for Compliance Testing"
    _order = "create_date desc"

    # Odoo 19: Use models.Constraint instead of _sql_constraints
    _unique_callback_per_transaction = models.Constraint(
        "UNIQUE(transaction_id, callback_type, correlation_id)",
        "Duplicate callback detected for the same transaction and type",
    )

    transaction_id = fields.Char(
        required=True,
        index=True,
        help="DCI transaction ID from the callback",
    )
    correlation_id = fields.Char(
        index=True,
        help="DCI correlation ID from the callback",
    )
    registry_type = fields.Selection(
        selection=[(t.value, t.name.replace("_", " ").title()) for t in RegistryType],
        required=True,
        index=True,
        help="Type of registry that sent the callback",
    )
    callback_type = fields.Selection(
        selection=[(t.value, t.name.replace("_", " ").title()) for t in CallbackType],
        required=True,
        index=True,
        help="Type of callback received",
    )
    endpoint = fields.Char(
        help="Endpoint path that received the callback",
    )
    method = fields.Char(
        default="POST",
        help="HTTP method used for the callback",
    )
    status = fields.Selection(
        selection=[(s.value, s.name.title()) for s in CallbackStatus],
        default=CallbackStatus.RECEIVED.value,
        required=True,
        index=True,
        help="Processing status of the callback",
    )
    payload = fields.Text(
        help="Sanitized JSON payload (PII redacted)",
    )
    payload_hash = fields.Char(
        help="SHA256 hash of the original payload for verification",
    )
    response_code = fields.Integer(
        help="HTTP response code returned to the sender",
    )
    error_message = fields.Text(
        help="Error message if processing failed",
    )
    processing_time_ms = fields.Integer(
        help="Time taken to process the callback in milliseconds",
    )
    sender_id = fields.Char(
        index=True,
        help="DCI sender ID from the callback envelope",
    )

    @api.model
    def log_callback(
        self,
        transaction_id: str,
        registry_type: str,
        callback_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        endpoint: str | None = None,
        sender_id: str | None = None,
    ) -> "DCICallbackLog":
        """Log a received DCI callback.

        Args:
            transaction_id: DCI transaction ID
            registry_type: Type of registry (sr, crvs, dr, ibr, fr)
            callback_type: Type of callback (on_search, on_subscribe, etc.)
            payload: Full callback payload (will be hashed, PII sanitized)
            correlation_id: DCI correlation ID
            endpoint: Endpoint path that received the callback
            sender_id: DCI sender ID

        Returns:
            Created callback log record

        Raises:
            ValidationError: If registry_type or callback_type is invalid
        """
        # Validate inputs
        if registry_type not in VALID_REGISTRY_TYPES:
            raise ValidationError(
                f"Invalid registry_type: {registry_type}. Must be one of: {', '.join(VALID_REGISTRY_TYPES)}"
            )
        if callback_type not in VALID_CALLBACK_TYPES:
            raise ValidationError(
                f"Invalid callback_type: {callback_type}. Must be one of: {', '.join(VALID_CALLBACK_TYPES)}"
            )

        # Process payload: hash original, sanitize for storage
        payload_hash = None
        sanitized_payload = None

        if payload:
            # Hash the original payload for verification
            if isinstance(payload, dict):
                original_str = json.dumps(payload, sort_keys=True, default=str)
            else:
                original_str = str(payload)
            payload_hash = hashlib.sha256(original_str.encode()).hexdigest()

            # Sanitize payload (remove PII) for storage
            if isinstance(payload, dict):
                sanitized_payload = _sanitize_payload(payload)
            else:
                sanitized_payload = "[NON-DICT PAYLOAD REDACTED]"

        return self.create(
            {
                "transaction_id": transaction_id,
                "correlation_id": correlation_id,
                "registry_type": registry_type,
                "callback_type": callback_type,
                "endpoint": endpoint,
                "payload": sanitized_payload,
                "payload_hash": payload_hash,
                "sender_id": sender_id,
                "status": CallbackStatus.RECEIVED.value,
            }
        )

    def mark_processing(self) -> None:
        """Mark callback as being processed."""
        self.write({"status": CallbackStatus.PROCESSING.value})

    def mark_processed(self, response_code: int = 200, processing_time_ms: int | None = None) -> None:
        """Mark callback as successfully processed.

        Args:
            response_code: HTTP response code returned
            processing_time_ms: Processing time in milliseconds
        """
        self.write(
            {
                "status": CallbackStatus.PROCESSED.value,
                "response_code": response_code,
                "processing_time_ms": processing_time_ms,
            }
        )

    def mark_failed(self, error_message: str, response_code: int = 500) -> None:
        """Mark callback as failed.

        Args:
            error_message: Description of the failure
            response_code: HTTP response code returned
        """
        self.write(
            {
                "status": CallbackStatus.FAILED.value,
                "error_message": error_message,
                "response_code": response_code,
            }
        )

    @api.model
    def get_callbacks(
        self,
        transaction_id: str | None = None,
        correlation_id: str | None = None,
        registry_type: str | None = None,
        callback_type: str | None = None,
        status: str | None = None,
        since_minutes: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query callback logs with filters.

        Args:
            transaction_id: Filter by transaction ID
            correlation_id: Filter by correlation ID
            registry_type: Filter by registry type (validated)
            callback_type: Filter by callback type (validated)
            status: Filter by status (validated)
            since_minutes: Only return callbacks from last N minutes
            limit: Maximum number of records to return

        Returns:
            List of callback records as dicts

        Raises:
            ValueError: If filter values are invalid
        """
        # Validate filter values
        if registry_type and registry_type not in VALID_REGISTRY_TYPES:
            raise ValueError(
                f"Invalid registry_type: {registry_type}. Must be one of: {', '.join(VALID_REGISTRY_TYPES)}"
            )
        if callback_type and callback_type not in VALID_CALLBACK_TYPES:
            raise ValueError(
                f"Invalid callback_type: {callback_type}. Must be one of: {', '.join(VALID_CALLBACK_TYPES)}"
            )
        if status and status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of: {', '.join(VALID_STATUSES)}")

        domain = []

        if transaction_id:
            domain.append(("transaction_id", "=", transaction_id))
        if correlation_id:
            domain.append(("correlation_id", "=", correlation_id))
        if registry_type:
            domain.append(("registry_type", "=", registry_type))
        if callback_type:
            domain.append(("callback_type", "=", callback_type))
        if status:
            domain.append(("status", "=", status))
        if since_minutes:
            since_dt = fields.Datetime.subtract(fields.Datetime.now(), minutes=since_minutes)
            domain.append(("create_date", ">=", since_dt))

        callbacks = self.search(domain, limit=limit, order="create_date desc")

        return [
            {
                "id": cb.id,
                "transaction_id": cb.transaction_id,
                "correlation_id": cb.correlation_id,
                "registry_type": cb.registry_type,
                "callback_type": cb.callback_type,
                "endpoint": cb.endpoint,
                "status": cb.status,
                "payload_hash": cb.payload_hash,
                "response_code": cb.response_code,
                "error_message": cb.error_message,
                "processing_time_ms": cb.processing_time_ms,
                "sender_id": cb.sender_id,
                "received_at": cb.create_date.isoformat() if cb.create_date else None,
            }
            for cb in callbacks
        ]

    @api.model
    def cleanup_old_logs(self, days: int = 7, batch_size: int = 1000) -> int:
        """Queue cleanup job batches for old callback logs.

        Args:
            days: Number of days to keep logs
            batch_size: Number of records to delete per batch

        Returns:
            Total number of records to be deleted
        """
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        total = self.search_count([("create_date", "<", cutoff)])

        if not total:
            _logger.info("No old DCI callback logs to clean up")
            return 0

        # Queue batches using job_worker
        _logger.info("Queueing %d DCI callback logs for cleanup in batches of %d", total, batch_size)
        for offset in range(0, total, batch_size):
            self.with_delay(description=f"Cleanup DCI logs batch {offset // batch_size + 1}")._cleanup_batch(
                cutoff, batch_size, offset
            )

        return total

    def _cleanup_batch(self, cutoff, limit, offset):
        """Process one batch - each job runs in its own transaction.

        Args:
            cutoff: Datetime cutoff for deletion
            limit: Max records to delete in this batch
            offset: Offset for pagination

        Returns:
            Number of records deleted
        """
        old_logs = self.search([("create_date", "<", cutoff)], limit=limit, offset=offset)
        if old_logs:
            count = len(old_logs)
            old_logs.unlink()
            _logger.info("Cleaned up batch of %d DCI callback logs", count)
            return count
        return 0


class DCICallbackLogMixin(models.AbstractModel):
    """Mixin to add callback logging to DCI callback handlers.

    Inherit this mixin in your callback endpoint handlers to automatically
    log callbacks for compliance testing.

    Example:
        class MyCRVSCallback(models.AbstractModel):
            _name = 'my.crvs.callback'
            _inherit = 'spp.dci.callback.log.mixin'

            def handle_on_search(self, payload):
                with self.log_dci_callback(
                    transaction_id=payload.get('transaction_id'),
                    registry_type='crvs',
                    callback_type='on_search',
                    payload=payload,
                ):
                    # Process the callback
                    ...
    """

    _name = "spp.dci.callback.log.mixin"
    _description = "DCI Callback Logging Mixin"

    def log_dci_callback(
        self,
        transaction_id: str,
        registry_type: str,
        callback_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        endpoint: str | None = None,
        sender_id: str | None = None,
    ) -> "_DCICallbackLogContext":
        """Context manager for logging DCI callbacks.

        Creates a callback log record and updates its status based on
        whether the callback processing succeeds or fails.

        Usage:
            with self.log_dci_callback(...) as log:
                # Process callback
                # log.mark_processed() is called automatically on success
        """
        return _DCICallbackLogContext(
            self.env,
            transaction_id=transaction_id,
            registry_type=registry_type,
            callback_type=callback_type,
            payload=payload,
            correlation_id=correlation_id,
            endpoint=endpoint,
            sender_id=sender_id,
        )


class _DCICallbackLogContext:
    """Context manager for DCI callback logging."""

    def __init__(self, env, **kwargs):
        self.env = env
        self.kwargs = kwargs
        self.log: DCICallbackLog | None = None
        self.start_time: float | None = None

    def __enter__(self) -> "DCICallbackLog":
        self.start_time = time.time()
        self.log = self.env["spp.dci.callback.log"].log_callback(**self.kwargs)
        self.log.mark_processing()
        return self.log

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        processing_time_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is None:
            self.log.mark_processed(
                response_code=200,
                processing_time_ms=processing_time_ms,
            )
        else:
            self.log.mark_failed(
                error_message=str(exc_val),
                response_code=500,
            )

        return False
