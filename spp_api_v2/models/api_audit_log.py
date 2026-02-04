# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unified API audit log for all API operations (ADR-020)."""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApiAuditLog(models.Model):
    """
    Unified audit log for all API operations.

    Captures:
    - All API operations (read, search, export, create, update, patch)
    - API client context (who made the request)
    - Consent information (authorization basis)
    - Links to spp.audit.log for field-level change details

    Supports GDPR Article 30 (records of processing) and Article 15 (data subject access).
    See ADR-020 for design rationale.
    """

    _name = "spp.api.audit.log"
    _description = "API Audit Log"
    _order = "timestamp desc"
    _rec_name = "display_name"

    # ==========================================
    # API Context - WHO made the request
    # ==========================================
    api_client_id = fields.Many2one(
        "spp.api.client",
        string="API Client",
        required=True,
        index=True,
        ondelete="restrict",
    )

    request_id = fields.Char(
        string="Request ID",
        index=True,
        help="Unique request identifier for correlation across logs",
    )

    ip_address = fields.Char(
        string="IP Address",
        help="Client IP address",
    )

    user_agent = fields.Char(
        string="User Agent",
        help="Client user agent string",
    )

    # ==========================================
    # Operation - WHAT was done
    # ==========================================
    operation = fields.Selection(
        [
            ("read", "Read"),
            ("search", "Search"),
            ("export", "Export"),
            ("create", "Create"),
            ("update", "Update"),
            ("patch", "Patch"),
            ("delete", "Delete"),
        ],
        required=True,
        index=True,
    )

    resource_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group"),
            ("program", "Program"),
            ("program_membership", "Program Membership"),
        ],
        required=True,
        index=True,
    )

    # External identifier (NEVER database ID)
    resource_identifier = fields.Char(
        string="Resource Identifier",
        required=True,
        index=True,
        help="External identifier in format system|value (never database ID)",
    )

    # ==========================================
    # Consent - WHY access was authorized
    # ==========================================
    consent_id = fields.Many2one(
        "spp.consent",
        string="Consent",
        index=True,
        ondelete="restrict",
        help="Consent that authorized this access (if applicable)",
    )

    purpose = fields.Char(
        help="Purpose of use from consent scope",
    )

    legal_basis = fields.Selection(
        [
            ("consent", "User Consent"),
            ("legal_obligation", "Legal Obligation"),
            ("public_interest", "Public Interest"),
            ("vital_interests", "Vital Interests"),
            ("legitimate_interests", "Legitimate Interests"),
            ("contract", "Contract Performance"),
        ],
        help="Legal basis for processing (GDPR Article 6)",
    )

    # ==========================================
    # Request Details
    # ==========================================
    # For search operations
    search_parameters = fields.Json(
        help="Search parameters used (for search/export operations)",
    )

    result_count = fields.Integer(
        help="Number of results returned (for search operations)",
    )

    # For read operations with field filtering
    fields_returned = fields.Json(
        help="List of fields returned in response (for _elements filtering)",
    )

    extensions_returned = fields.Json(
        help="List of extensions returned in response",
    )

    # ==========================================
    # Change Tracking - links to detailed changes
    # ==========================================
    audit_log_id = fields.Integer(
        string="Audit Log ID",
        index=True,
        help="ID of linked spp.audit.log entry for field-level change details (write operations)",
    )

    # Store model and res_id for linking even if spp.audit.log entry is deleted
    model_name = fields.Char(
        help="Technical model name (e.g., res.partner)",
    )

    res_id = fields.Integer(
        help="Database record ID (internal use only, not exposed in API)",
    )

    # ==========================================
    # Result
    # ==========================================
    status = fields.Selection(
        [
            ("success", "Success"),
            ("access_denied", "Access Denied"),
            ("not_found", "Not Found"),
            ("validation_error", "Validation Error"),
            ("error", "Error"),
        ],
        default="success",
        required=True,
    )

    error_detail = fields.Char(
        help="Error message (no PII)",
    )

    # ==========================================
    # Timestamps
    # ==========================================
    timestamp = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    # ==========================================
    # Computed fields
    # ==========================================
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("operation", "resource_type", "timestamp")
    def _compute_display_name(self):
        for rec in self:
            timestamp_str = rec.timestamp.strftime("%Y-%m-%d %H:%M") if rec.timestamp else ""
            rec.display_name = f"{rec.operation} {rec.resource_type} @ {timestamp_str}"

    # ==========================================
    # API Methods
    # ==========================================
    @api.model
    def log_operation(
        self,
        api_client,
        operation: str,
        resource_type: str,
        resource_identifier: str,
        status: str = "success",
        consent=None,
        purpose: str = None,
        legal_basis: str = None,
        request_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        search_parameters: dict = None,
        result_count: int = None,
        fields_returned: list = None,
        extensions_returned: list = None,
        model_name: str = None,
        res_id: int = None,
        error_detail: str = None,
    ):
        """
        Log an API operation.

        Args:
            api_client: spp.api.client record
            operation: Type of operation (read, search, create, update, patch, delete)
            resource_type: Type of resource (individual, group, program, program_membership)
            resource_identifier: External identifier (system|value format)
            status: Result status
            consent: spp.consent record (if applicable)
            purpose: Purpose from consent scope
            legal_basis: GDPR legal basis
            request_id: Unique request correlation ID
            ip_address: Client IP
            user_agent: Client user agent
            search_parameters: Search params (for search ops)
            result_count: Number of results (for search ops)
            fields_returned: Fields in response (for _elements filtering)
            extensions_returned: Extensions in response
            model_name: Odoo model name (for linking to spp.audit.log)
            res_id: Database record ID (internal, for linking)
            error_detail: Error message (no PII)

        Returns:
            Created spp.api.audit.log record
        """
        vals = {
            "api_client_id": api_client.id,
            "operation": operation,
            "resource_type": resource_type,
            "resource_identifier": resource_identifier,
            "status": status,
            "timestamp": fields.Datetime.now(),
        }

        # Optional fields
        if consent:
            vals["consent_id"] = consent.id
        if purpose:
            vals["purpose"] = purpose
        if legal_basis:
            vals["legal_basis"] = legal_basis
        if request_id:
            vals["request_id"] = request_id
        if ip_address:
            vals["ip_address"] = ip_address
        if user_agent:
            vals["user_agent"] = user_agent
        if search_parameters:
            vals["search_parameters"] = search_parameters
        if result_count is not None:
            vals["result_count"] = result_count
        if fields_returned:
            vals["fields_returned"] = fields_returned
        if extensions_returned:
            vals["extensions_returned"] = extensions_returned
        if model_name:
            vals["model_name"] = model_name
        if res_id:
            vals["res_id"] = res_id
        if error_detail:
            vals["error_detail"] = error_detail

        return self.create(vals)

    @api.model
    def link_audit_log(self, api_audit_log, model_name: str, res_id: int):
        """
        Link an API audit log entry to its corresponding spp.audit.log entry.

        Called after write operations to connect the API audit log to the
        detailed field-level changes captured by spp.audit.

        Note: This method uses order="create_date desc" to find the most recent
        spp.audit.log entry. In high-concurrency scenarios with rapid updates to
        the same record, this may rarely link to the wrong entry if create_date
        timestamps are identical. For most use cases, Odoo's microsecond timestamp
        precision is sufficient. If exact linking is critical in high-volume
        scenarios, consider passing a correlation ID through the audit context.

        Args:
            api_audit_log: spp.api.audit.log record to update
            model_name: Odoo model name
            res_id: Database record ID
        """
        # Only link if spp.audit.log model is available (requires spp_audit module)
        if "spp.audit.log" not in self.env:
            return

        # Find the most recent spp.audit.log entry for this record
        model_id = self.env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model_id:
            return

        audit_log = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", model_id.id),
                ("res_id", "=", res_id),
            ],
            order="create_date desc",
            limit=1,
        )

        if audit_log:
            api_audit_log.write({"audit_log_id": audit_log.id})

    def get_activity_summary(self, api_client_id=None, resource_identifier=None, date_from=None, date_to=None):
        """
        Get summary of API activity for reporting.

        Useful for compliance reporting and data subject access requests (GDPR Article 15).

        Args:
            api_client_id: Filter by API client
            resource_identifier: Filter by resource
            date_from: Start date filter
            date_to: End date filter

        Returns:
            Dict with activity summary
        """
        domain = []
        if api_client_id:
            domain.append(("api_client_id", "=", api_client_id))
        if resource_identifier:
            domain.append(("resource_identifier", "=", resource_identifier))
        if date_from:
            domain.append(("timestamp", ">=", date_from))
        if date_to:
            domain.append(("timestamp", "<=", date_to))

        # Database-level aggregation using _read_group for scalability (Odoo 19)
        by_operation = {
            op: 0
            for op in [
                "read",
                "search",
                "export",
                "create",
                "update",
                "patch",
                "delete",
            ]
        }
        operation_data = self._read_group(domain, ["operation"], ["__count"])
        for operation, count in operation_data:
            if operation in by_operation:
                by_operation[operation] = count

        by_resource_type = {rt: 0 for rt in ["individual", "group", "program", "program_membership"]}
        resource_type_data = self._read_group(domain, ["resource_type"], ["__count"])
        for resource_type, count in resource_type_data:
            if resource_type in by_resource_type:
                by_resource_type[resource_type] = count

        by_status = {
            st: 0
            for st in [
                "success",
                "access_denied",
                "not_found",
                "validation_error",
                "error",
            ]
        }
        status_data = self._read_group(domain, ["status"], ["__count"])
        for status_val, count in status_data:
            if status_val in by_status:
                by_status[status_val] = count

        by_client = {}
        client_data = self._read_group(domain, ["api_client_id"], ["__count"])
        for client, count in client_data:
            client_name = client.name if client else "Unknown"
            by_client[client_name] = count

        # Get total count and date range in a single _read_group query
        total_operations = 0
        first_timestamp = None
        last_timestamp = None
        totals_data = self._read_group(domain, [], ["__count", "timestamp:min", "timestamp:max"])
        if totals_data:
            total_operations, first_timestamp, last_timestamp = totals_data[0]

        return {
            "total_operations": total_operations,
            "by_operation": by_operation,
            "by_resource_type": by_resource_type,
            "by_status": by_status,
            "by_client": by_client,
            "date_range": {
                "first": first_timestamp.isoformat() if first_timestamp else None,
                "last": last_timestamp.isoformat() if last_timestamp else None,
            },
        }

    @api.model
    def get_consent_access_summary(self, consent_id, date_from=None, date_to=None):
        """
        Get summary of accesses for a specific consent.

        Useful for data subject access requests (GDPR Article 15).

        Args:
            consent_id: ID of consent to summarize
            date_from: Optional start date filter
            date_to: Optional end date filter

        Returns:
            Dict with access summary compatible with consent router
        """
        domain = [("consent_id", "=", consent_id)]
        if date_from:
            domain.append(("timestamp", ">=", date_from))
        if date_to:
            domain.append(("timestamp", "<=", date_to))

        # Database-level aggregation using _read_group for scalability
        # Map operations to action categories
        by_action = {"read": 0, "search": 0, "export": 0}

        # Single _read_group to get counts by operation, then map to action categories
        operation_data = self._read_group(domain, ["operation"], ["__count"])
        for operation, count in operation_data:
            if operation in ("search", "export"):
                by_action[operation] = count
            elif operation in ("read", "create", "update", "patch", "delete"):
                by_action["read"] += count

        by_resource_type = {rt: 0 for rt in ["individual", "group", "program", "program_membership"]}
        resource_type_data = self._read_group(domain, ["resource_type"], ["__count"])
        for resource_type, count in resource_type_data:
            if resource_type in by_resource_type:
                by_resource_type[resource_type] = count

        by_client = {}
        client_data = self._read_group(domain, ["api_client_id"], ["__count"])
        for client, count in client_data:
            client_name = client.name if client else "Unknown"
            by_client[client_name] = count

        # Get total count and date range in a single _read_group query
        total_accesses = 0
        first_timestamp = None
        last_timestamp = None
        totals_data = self._read_group(domain, [], ["__count", "timestamp:min", "timestamp:max"])
        if totals_data:
            total_accesses, first_timestamp, last_timestamp = totals_data[0]

        return {
            "total_accesses": total_accesses,
            "by_action": by_action,
            "by_resource_type": by_resource_type,
            "by_client": by_client,
            "date_range": {
                "first": first_timestamp.isoformat() if first_timestamp else None,
                "last": last_timestamp.isoformat() if last_timestamp else None,
            },
        }
