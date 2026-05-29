# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Data Provider - External data source configuration.

This module provides configuration for external data providers that can
push/pull variable values via APIs. Used by variables with source_type='external'.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DataProvider(models.Model):
    """External Data Provider Configuration.

    Providers represent external systems that can supply variable values:
    - Education ministry APIs (attendance, enrollment)
    - Health ministry APIs (vaccination, checkups)
    - DCI registries (civil registration, disability)
    - Custom external systems

    Configuration includes:
    - Connection settings (URL, authentication)
    - Behavior settings (TTL, batch size, retries)
    - ID mapping configuration (how to match external IDs to registrants)
    """

    _name = "spp.data.provider"
    _description = "External Data Provider"
    _order = "name"

    # ─── Identity ───────────────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        required=True,
        help="Human-readable name (e.g., 'Education Ministry API')",
    )
    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Unique identifier for this provider (e.g., 'edu_ministry')",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    provider_kind = fields.Selection(
        selection=[("generic", "Generic")],
        string="Provider Kind",
        required=True,
        default="generic",
        help=(
            "Typed discriminator used by the evaluator and executor to dispatch "
            "external-value resolution to provider-specific overrides. Downstream "
            "modules extend this selection via `_selection_add` (e.g. 'notary')."
        ),
    )

    # ─── Connection Settings ─────────────────────────────────────────────
    base_url = fields.Char(
        string="Base URL",
        help="Base URL for the provider's API (e.g., 'https://api.edu.gov/v1')",
    )
    auth_type = fields.Selection(
        selection=[
            ("none", "No Authentication"),
            ("api_key", "API Key"),
            ("oauth2", "OAuth 2.0"),
            ("hmac", "HMAC Signature"),
        ],
        string="Authentication Type",
        default="none",
    )
    api_key = fields.Char(
        string="API Key",
        help="API key for authentication (stored encrypted)",
        groups="spp_cel_domain.group_cel_domain_manager",
    )
    oauth_client_id = fields.Char(
        string="OAuth Client ID",
        groups="spp_cel_domain.group_cel_domain_manager",
    )
    oauth_client_secret = fields.Char(
        string="OAuth Client Secret",
        groups="spp_cel_domain.group_cel_domain_manager",
    )
    oauth_token_url = fields.Char(
        string="OAuth Token URL",
    )

    # ─── Behavior Settings ───────────────────────────────────────────────
    default_ttl_seconds = fields.Integer(
        string="Default TTL (seconds)",
        default=86400,
        help="Default cache TTL for values from this provider (24 hours default)",
    )
    max_batch_size = fields.Integer(
        string="Max Batch Size",
        default=1000,
        help="Maximum number of subjects per API request",
    )
    timeout_ms = fields.Integer(
        string="Timeout (ms)",
        default=5000,
        help="Request timeout in milliseconds",
    )
    retry_max = fields.Integer(
        string="Max Retries",
        default=3,
        help="Maximum retry attempts on failure",
    )
    recommended_concurrency = fields.Integer(
        string="Recommended Concurrency",
        default=5,
        help="Recommended number of parallel requests",
    )

    # ─── ID Mapping ─────────────────────────────────────────────────────
    id_mapping_fields = fields.Char(
        string="ID Mapping Fields",
        help=(
            "Comma-separated field names to try for external ID matching "
            "(e.g., 'school_student_id,external_id,national_id')"
        ),
    )
    is_id_mapping_required = fields.Boolean(
        string="ID Mapping Required",
        default=False,
        help="If true, reject values where subject cannot be mapped",
    )
    id_mapping_namespace = fields.Char(
        string="ID Namespace",
        help="External identifier namespace label (e.g., 'EDU_MINISTRY')",
    )

    # ─── Multi-tenancy ─────────────────────────────────────────────────
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # ─── Relationships ─────────────────────────────────────────────────
    variable_ids = fields.One2many(
        comodel_name="spp.cel.variable",
        inverse_name="external_provider_id",
        string="Variables",
        help="Variables that use this provider",
    )
    variable_count = fields.Integer(
        string="Variable Count",
        compute="_compute_variable_count",
    )

    # Uniqueness constraint
    _unique_code_company = models.Constraint(
        "UNIQUE(code, company_id)",
        "Provider code must be unique per company.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _compute_variable_count(self):
        for rec in self:
            rec.variable_count = len(rec.variable_ids)

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains("code")
    def _check_code_format(self):
        """Ensure code is lowercase alphanumeric with underscores."""
        import re

        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for rec in self:
            if not pattern.match(rec.code):
                raise ValidationError(
                    _("Provider code must be lowercase alphanumeric with underscores, starting with a letter.")
                )

    @api.constrains("default_ttl_seconds")
    def _check_ttl(self):
        """Ensure TTL is positive."""
        for rec in self:
            if rec.default_ttl_seconds <= 0:
                raise ValidationError(_("Default TTL must be positive."))

    @api.constrains("max_batch_size")
    def _check_batch_size(self):
        """Ensure batch size is reasonable."""
        for rec in self:
            if rec.max_batch_size <= 0:
                raise ValidationError(_("Max batch size must be positive."))
            if rec.max_batch_size > 10000:
                raise ValidationError(_("Max batch size cannot exceed 10000."))

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_id_mapping_field_list(self):
        """Get list of ID mapping fields.

        Returns:
            list: Field names to try for external ID matching
        """
        self.ensure_one()
        if not self.id_mapping_fields:
            return []
        return [f.strip() for f in self.id_mapping_fields.split(",") if f.strip()]

    def name_get(self):
        """Display name with code."""
        return [(rec.id, f"{rec.name} ({rec.code})") for rec in self]

    # ═══════════════════════════════════════════════════════════════════════
    # EXTERNAL-VALUE HOOKS
    # ═══════════════════════════════════════════════════════════════════════
    # These are the integration points used by the evaluator and executor when
    # a variable has `source_type='external'`. The base implementation is a
    # no-op that warns. Downstream modules (e.g. spp_notary_evidence) override
    # them on providers whose `provider_kind` matches their integration.

    def _compute_external_values(self, variable, subject_ids, period_key):
        """Batch-compute external values for a variable across subjects.

        Called from `spp.data.cache.manager._compute_variable_values` when
        `variable.source_type == 'external'`. Downstream modules override
        this on their own `provider_kind` to issue the actual upstream call
        (e.g. POST `/claims/batch-evaluate` for Notary).

        Args:
            variable: `spp.cel.variable` record (source_type='external').
            subject_ids: List of subject record IDs to compute values for.
            period_key: Period key string (or None / 'current').

        Returns:
            dict: `{subject_id: value, ...}` for subjects that returned a value.
                  Subjects without a value are omitted (the framework treats
                  missing keys as "no cached value").
        """
        self.ensure_one()
        _logger.warning(
            "Provider '%s' (kind=%s) has no `_compute_external_values` override "
            "for variable '%s'. Returning empty dict; cached values must be "
            "supplied via API push or a provider-specific override.",
            self.code,
            self.provider_kind,
            variable.name,
        )
        return {}

    def _refresh_external_value(self, variable, subject_id, period_key):
        """Refresh a single external value on cache miss.

        Called from `spp.cel.executor._exec_metric` when an external variable
        has no cached value for `(subject_id, period_key)` and lazy refresh is
        wanted. Downstream modules override this to issue the upstream call
        (e.g. POST `/claims/evaluate` for Notary, possibly session-batched).

        Args:
            variable: `spp.cel.variable` record (source_type='external').
            subject_id: Subject record ID.
            period_key: Period key string (or None / 'current').

        Returns:
            The resolved value, or None if no value is available.

        Implementations that write through to `spp.data.value` (the usual case)
        should do so before returning, so subsequent reads hit the cache.
        """
        self.ensure_one()
        _logger.warning(
            "Provider '%s' (kind=%s) has no `_refresh_external_value` override "
            "for variable '%s'. Returning None.",
            self.code,
            self.provider_kind,
            variable.name,
        )
        return None

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_view_variables(self):
        """Open list of variables using this provider."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Variables - %s") % self.name,
            "res_model": "spp.cel.variable",
            "view_mode": "list,form",
            "domain": [("external_provider_id", "=", self.id)],
            "context": {"default_external_provider_id": self.id},
        }

    def action_test_connection(self):
        """Test connection to external provider.

        For API providers, attempts a test request to verify connectivity.
        """
        self.ensure_one()

        if not self.base_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No URL Configured"),
                    "message": _("Please configure a base URL first."),
                    "type": "warning",
                },
            }

        # Try to make a test request
        try:
            import requests

            # Build authentication headers based on auth_type
            headers = {}
            if self.auth_type == "api_key" and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Simple HEAD request to test connectivity
            response = requests.head(  # nosec B113 — explicit timeout via self.timeout_ms
                self.base_url,
                headers=headers,
                timeout=self.timeout_ms / 1000,  # Convert ms to seconds
            )

            if response.ok:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Connection Successful"),
                        "message": _("Successfully connected to %s") % self.base_url,
                        "type": "success",
                    },
                }
            else:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Connection Failed"),
                        "message": _("Server returned status %s") % response.status_code,
                        "type": "warning",
                    },
                }

        except requests.RequestException as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Error"),
                    "message": str(e),
                    "type": "danger",
                },
            }
