# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Audit log for outgoing API calls to external services."""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ApiOutgoingLog(models.Model):
    """
    Audit log for outgoing HTTP calls to external services.

    Captures all outgoing API requests (DCI, webhooks, etc.) with
    request/response details for troubleshooting and compliance.
    """

    _name = "spp.api.outgoing.log"
    _description = "Outgoing API Log"
    _order = "timestamp desc"
    _rec_name = "display_name"

    # ==========================================
    # Request - WHAT was sent
    # ==========================================
    url = fields.Char(
        required=True,
        index=True,
        groups="spp_api_v2.group_api_v2_auditor",
        help="Full URL called (may contain sensitive query parameters)",
    )

    endpoint = fields.Char(
        index=True,
        help="Path portion of the URL, e.g. /registry/sync/search",
    )

    http_method = fields.Selection(
        [
            ("POST", "POST"),
            ("GET", "GET"),
            ("PUT", "PUT"),
            ("PATCH", "PATCH"),
            ("DELETE", "DELETE"),
        ],
        default="POST",
        required=True,
    )

    request_summary = fields.Json(
        groups="spp_api_v2.group_api_v2_auditor",
        help="Request payload (secrets redacted)",
    )

    # ==========================================
    # Response - WHAT came back
    # ==========================================
    response_summary = fields.Json(
        groups="spp_api_v2.group_api_v2_auditor",
        help="Response payload",
    )

    response_status_code = fields.Integer(
        index=True,
    )

    # ==========================================
    # Context - WHO triggered it
    # ==========================================
    user_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.uid,
        index=True,
    )

    origin_model = fields.Char(
        index=True,
        help="Model that triggered the call, e.g. spp.dci.data.source",
    )

    origin_record_id = fields.Integer(
        help="Record ID that triggered the call",
    )

    # ==========================================
    # Timestamps & Performance
    # ==========================================
    timestamp = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    duration_ms = fields.Integer(
        help="Request duration in milliseconds",
    )

    # ==========================================
    # Service Context
    # ==========================================
    service_name = fields.Char(
        index=True,
        help="Human-readable service name, e.g. DCI Client",
    )

    service_code = fields.Char(
        index=True,
        help="Machine-readable service code, e.g. crvs_main",
    )

    # ==========================================
    # Result
    # ==========================================
    status = fields.Selection(
        [
            ("success", "Success"),
            ("http_error", "HTTP Error"),
            ("connection_error", "Connection Error"),
            ("timeout", "Timeout"),
            ("error", "Error"),
        ],
        default="success",
        required=True,
        index=True,
    )

    error_detail = fields.Text(
        groups="spp_api_v2.group_api_v2_auditor",
        help="Error message or traceback",
    )

    # ==========================================
    # Computed fields
    # ==========================================
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("http_method", "endpoint", "timestamp")
    def _compute_display_name(self):
        for record in self:
            timestamp_str = record.timestamp.strftime("%Y-%m-%d %H:%M") if record.timestamp else ""
            record.display_name = f"{record.http_method} {record.endpoint or record.url} @ {timestamp_str}"

    # ==========================================
    # API Methods
    # ==========================================
    @api.model
    def log_call(
        self,
        url: str,
        http_method: str = "POST",
        endpoint: str = None,
        request_summary: dict = None,
        response_summary: dict = None,
        response_status_code: int = None,
        user_id: int = None,
        origin_model: str = None,
        origin_record_id: int = None,
        duration_ms: int = None,
        service_name: str = None,
        service_code: str = None,
        status: str = "success",
        error_detail: str = None,
    ):
        """
        Log an outgoing API call.

        Args:
            url: Full URL called
            http_method: HTTP method (POST, GET, PUT, PATCH, DELETE)
            endpoint: Path portion of the URL
            request_summary: Request payload (secrets redacted)
            response_summary: Response payload
            response_status_code: HTTP response status code
            user_id: User who triggered the call
            origin_model: Odoo model that triggered the call
            origin_record_id: Record ID that triggered the call
            duration_ms: Request duration in milliseconds
            service_name: Human-readable service name
            service_code: Machine-readable service code
            status: Result status
            error_detail: Error message or traceback

        Returns:
            Created spp.api.outgoing.log record
        """
        vals = {
            "url": url,
            "http_method": http_method,
            "status": status,
            "timestamp": fields.Datetime.now(),
        }

        # Optional fields
        if endpoint:
            vals["endpoint"] = endpoint
        if request_summary is not None:
            vals["request_summary"] = request_summary
        if response_summary is not None:
            vals["response_summary"] = response_summary
        if response_status_code is not None:
            vals["response_status_code"] = response_status_code
        if user_id is not None:
            vals["user_id"] = user_id
        if origin_model:
            vals["origin_model"] = origin_model
        if origin_record_id is not None:
            vals["origin_record_id"] = origin_record_id
        if duration_ms is not None:
            vals["duration_ms"] = duration_ms
        if service_name:
            vals["service_name"] = service_name
        if service_code:
            vals["service_code"] = service_code
        if error_detail:
            vals["error_detail"] = error_detail

        return self.create(vals)
