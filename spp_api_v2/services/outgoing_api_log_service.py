# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for logging outgoing API calls."""

import json
import logging

import psycopg2

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class OutgoingApiLogService:
    """
    Service for logging outgoing HTTP calls to the audit log.

    Wraps spp.api.outgoing.log with try/except so logging failures
    never prevent the actual API call from succeeding.

    Usage:
        service = OutgoingApiLogService(env, "DCI Client", "crvs_main")
        service.log_call(
            url="https://crvs.example.org/api/registry/sync/search",
            endpoint="/registry/sync/search",
            http_method="POST",
            request_summary={"header": {...}},
            response_summary={"header": {...}},
            response_status_code=200,
            duration_ms=350,
            origin_model="spp.dci.data.source",
            origin_record_id=42,
            status="success",
        )
    """

    def __init__(
        self,
        env: Environment,
        service_name: str,
        service_code: str,
        user_id: int = None,
    ):
        """
        Initialize the outgoing API log service.

        Args:
            env: Odoo environment
            service_name: Human-readable service name (e.g. "DCI Client")
            service_code: Machine-readable service code (e.g. "crvs_main")
            user_id: User ID to record (defaults to env.uid)
        """
        self.env = env
        self.service_name = service_name
        self.service_code = service_code
        self.user_id = user_id or env.uid

    def log_call(
        self,
        url: str,
        endpoint: str = None,
        http_method: str = "POST",
        request_summary: dict = None,
        response_summary: dict = None,
        response_status_code: int = None,
        duration_ms: int = None,
        origin_model: str = None,
        origin_record_id: int = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log an outgoing API call.

        Returns the created record, or None if logging fails.
        Logging failures never raise exceptions.
        """
        try:
            # Truncate large payloads
            truncated_request = self._truncate_payload(request_summary)
            truncated_response = self._truncate_payload(response_summary)

            log_model = self.env["spp.api.outgoing.log"].sudo()  # nosemgrep: odoo-sudo-without-context
            return log_model.log_call(
                url=url,
                endpoint=endpoint,
                http_method=http_method,
                request_summary=truncated_request,
                response_summary=truncated_response,
                response_status_code=response_status_code,
                user_id=self.user_id,
                origin_model=origin_model,
                origin_record_id=origin_record_id,
                duration_ms=duration_ms,
                service_name=self.service_name,
                service_code=self.service_code,
                status=status,
                error_detail=error_detail,
            )
        except (KeyError, AttributeError, TypeError) as e:
            _logger.warning("Failed to log outgoing API call due to data error: %s", type(e).__name__)
            return None
        except (psycopg2.Error, ValueError, RuntimeError):
            _logger.exception("Failed to log outgoing API call")
            return None

    def _truncate_payload(self, payload, max_length=10000):
        """Truncate large payloads for DB storage.

        Args:
            payload: Dict payload to potentially truncate
            max_length: Maximum JSON string length (default 10000)

        Returns:
            Original payload if within limit, or truncated version
        """
        if payload is None:
            return None

        try:
            serialized = json.dumps(payload)
        except (TypeError, ValueError):
            return {"_truncated": True, "_error": "Could not serialize payload"}

        if len(serialized) <= max_length:
            return payload

        return {
            "_truncated": True,
            "_original_length": len(serialized),
            "_preview": serialized[:max_length],
        }
