# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for unified API audit logging (ADR-020)."""

import logging
import uuid
from typing import Any

import psycopg2

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class ApiAuditService:
    """
    Service for logging all API operations to the unified audit log.

    This service provides a clean interface for logging read and write operations,
    automatically handling consent context, request correlation, and linking to
    spp.audit.log for field-level change details.

    Usage:
        audit_service = ApiAuditService(env, api_client, request)

        # Log a read operation
        audit_service.log_read("individual", "urn:...|123", consent=consent)

        # Log a write operation (links to spp.audit.log automatically)
        audit_service.log_write("create", "individual", "urn:...|123", partner)
    """

    def __init__(
        self,
        env: Environment,
        api_client,
        request_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """
        Initialize the audit service.

        Args:
            env: Odoo environment
            api_client: spp.api.client record
            request_id: Unique request ID (generated if not provided)
            ip_address: Client IP address
            user_agent: Client user agent string
        """
        self.env = env
        self.api_client = api_client
        self.request_id = request_id or str(uuid.uuid4())
        self.ip_address = ip_address
        self.user_agent = user_agent

    def log_read(
        self,
        resource_type: str,
        resource_identifier: str,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        fields_returned: list = None,
        extensions_returned: list = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a read (single record) operation.

        Args:
            resource_type: individual, group, program, program_membership
            resource_identifier: External identifier (system|value)
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            fields_returned: List of fields returned (for _elements filtering)
            extensions_returned: List of extensions returned
            status: success, access_denied, not_found, error
            error_detail: Error message (no PII)
        """
        self._log(
            operation="read",
            resource_type=resource_type,
            resource_identifier=resource_identifier,
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            fields_returned=fields_returned,
            extensions_returned=extensions_returned,
            status=status,
            error_detail=error_detail,
        )

    def log_search(
        self,
        resource_type: str,
        search_parameters: dict,
        result_count: int,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a search operation.

        Args:
            resource_type: individual, group, program, program_membership
            search_parameters: Dict of search parameters used
            result_count: Number of results returned
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, access_denied, error
            error_detail: Error message (no PII)
        """
        self._log(
            operation="search",
            resource_type=resource_type,
            resource_identifier="search",
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            search_parameters=search_parameters,
            result_count=result_count,
            status=status,
            error_detail=error_detail,
        )

    def log_export(
        self,
        resource_type: str,
        identifiers: list,
        result_count: int,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a bulk export operation.

        Args:
            resource_type: individual, group
            identifiers: List of identifiers exported
            result_count: Number of successful exports
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, error
            error_detail: Error message (no PII)
        """
        self._log(
            operation="export",
            resource_type=resource_type,
            resource_identifier=f"bulk:{len(identifiers)}",
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            search_parameters={"identifiers": identifiers},
            result_count=result_count,
            status=status,
            error_detail=error_detail,
        )

    def log_create(
        self,
        resource_type: str,
        resource_identifier: str,
        record,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a create operation and link to spp.audit.log.

        Args:
            resource_type: individual, group, program_membership
            resource_identifier: External identifier of created resource
            record: Created Odoo record (for linking to spp.audit.log)
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, validation_error, error
            error_detail: Error message (no PII)
        """
        api_log = self._log(
            operation="create",
            resource_type=resource_type,
            resource_identifier=resource_identifier,
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            model_name=record._name if record else None,
            res_id=record.id if record else None,
            status=status,
            error_detail=error_detail,
        )

        # Link to spp.audit.log for field-level changes
        if api_log and record and status == "success":
            self._link_audit_log(api_log, record)

    def log_update(
        self,
        resource_type: str,
        resource_identifier: str,
        record,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log an update (PUT) operation and link to spp.audit.log.

        Args:
            resource_type: individual, group, program_membership
            resource_identifier: External identifier of updated resource
            record: Updated Odoo record
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, validation_error, not_found, error
            error_detail: Error message (no PII)
        """
        api_log = self._log(
            operation="update",
            resource_type=resource_type,
            resource_identifier=resource_identifier,
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            model_name=record._name if record else None,
            res_id=record.id if record else None,
            status=status,
            error_detail=error_detail,
        )

        # Link to spp.audit.log
        if api_log and record and status == "success":
            self._link_audit_log(api_log, record)

    def log_patch(
        self,
        resource_type: str,
        resource_identifier: str,
        record,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a patch (partial update) operation and link to spp.audit.log.

        Args:
            resource_type: individual, group
            resource_identifier: External identifier of patched resource
            record: Patched Odoo record
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, validation_error, not_found, error
            error_detail: Error message (no PII)
        """
        api_log = self._log(
            operation="patch",
            resource_type=resource_type,
            resource_identifier=resource_identifier,
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            model_name=record._name if record else None,
            res_id=record.id if record else None,
            status=status,
            error_detail=error_detail,
        )

        # Link to spp.audit.log
        if api_log and record and status == "success":
            self._link_audit_log(api_log, record)

    def log_delete(
        self,
        resource_type: str,
        resource_identifier: str,
        record=None,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log a delete operation.

        Args:
            resource_type: individual, group, program_membership
            resource_identifier: External identifier of deleted resource
            record: Odoo record before deletion (optional)
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            status: success, not_found, error
            error_detail: Error message (no PII)
        """
        self._log(
            operation="delete",
            resource_type=resource_type,
            resource_identifier=resource_identifier,
            consent=consent,
            purpose=purpose,
            legal_basis=legal_basis,
            model_name=record._name if record else None,
            res_id=record.id if record else None,
            status=status,
            error_detail=error_detail,
        )

    def _log(
        self,
        operation: str,
        resource_type: str,
        resource_identifier: str,
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        search_parameters: dict = None,
        result_count: int = None,
        fields_returned: list = None,
        extensions_returned: list = None,
        model_name: str = None,
        res_id: int = None,
        status: str = "success",
        error_detail: str = None,
    ) -> Any:
        """
        Internal method to create audit log entry.

        Returns the created spp.api.audit.log record, or None if logging fails.
        Logging failures do not block the API request.
        """
        try:
            return (
                self.env["spp.api.audit.log"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .log_operation(
                    api_client=self.api_client,
                    operation=operation,
                    resource_type=resource_type,
                    resource_identifier=resource_identifier,
                    status=status,
                    consent=consent,
                    purpose=purpose,
                    legal_basis=legal_basis,
                    request_id=self.request_id,
                    ip_address=self.ip_address,
                    user_agent=self.user_agent,
                    search_parameters=search_parameters,
                    result_count=result_count,
                    fields_returned=fields_returned,
                    extensions_returned=extensions_returned,
                    model_name=model_name,
                    res_id=res_id,
                    error_detail=error_detail,
                )
            )
        except (KeyError, AttributeError, TypeError) as e:
            # Don't fail the API request if audit logging fails due to data issues
            _logger.warning("Failed to log API operation due to data error: %s", type(e).__name__)
            return None
        except (psycopg2.Error, ValueError, RuntimeError):
            # Database errors, value conversion errors, or ORM runtime errors
            # Audit logging must never block API requests
            _logger.exception("Failed to log API operation")
            return None

    def _link_audit_log(self, api_log, record):
        """Link the API audit log to the corresponding spp.audit.log entry."""
        try:
            self.env["spp.api.audit.log"].sudo().link_audit_log(  # nosemgrep: odoo-sudo-without-context
                api_log,
                record._name,
                record.id,
            )
        except (KeyError, AttributeError, TypeError) as e:
            # Don't fail if linking fails due to data issues
            _logger.warning("Failed to link audit log due to data error: %s", type(e).__name__)
        except (psycopg2.Error, ValueError, RuntimeError):
            # Database or ORM errors - audit linking must never block API requests
            _logger.exception("Failed to link audit log")
