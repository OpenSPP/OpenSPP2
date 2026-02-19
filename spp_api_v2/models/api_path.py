# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""API Path model for configuring API endpoint settings and filters."""

import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppApiPath(models.Model):
    """
    Configure API endpoint paths and their filter settings.

    Each record represents an API resource endpoint (e.g., Individual, Group)
    and its associated filter configuration.
    """

    _name = "spp.api.path"
    _description = "API Path Configuration"
    _order = "sequence, name"

    sequence = fields.Integer(default=10, help="Display order")
    name = fields.Char(required=True, help="API resource name (e.g., Individual, Group)")
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        help="Odoo model this API path exposes",
    )
    model_name = fields.Char(related="model_id.model", string="Model Name", store=True)
    description = fields.Text(help="Description of this API resource")

    # Filter configuration
    filter_ids = fields.One2many(
        "spp.api.path.filter",
        "path_id",
        string="Filters",
        help="Configured filters for this endpoint",
    )
    filter_preset_ids = fields.One2many(
        "spp.api.filter.preset",
        "path_id",
        string="Filter Presets",
        help="Saved filter presets for this endpoint",
    )
    allow_custom_filters = fields.Boolean(
        default=False,
        help="Allow filtering on any model field (not just configured filters). "
        "Use with caution as it may expose sensitive fields.",
    )
    max_filter_complexity = fields.Integer(
        default=10,
        help="Maximum number of filter conditions allowed per request",
    )

    # Static filter domain (applied to all requests)
    filter_domain = fields.Char(
        help="Static domain filter applied to all requests (Python expression). Example: [('active', '=', True)]",
    )

    active = fields.Boolean(default=True)

    # Computed fields
    filter_count = fields.Integer(compute="_compute_filter_count", string="Filter Count")
    preset_count = fields.Integer(compute="_compute_preset_count", string="Preset Count")

    @api.constrains("name")
    def _check_unique_name(self):
        """Ensure API path name is unique."""
        for record in self:
            if not record.name:
                continue

            domain = [
                ("name", "=", record.name),
                ("id", "!=", record.id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    _("API path name must be unique. A path named '%s' already exists.") % record.name
                )

    @api.depends("filter_ids")
    def _compute_filter_count(self):
        for record in self:
            record.filter_count = len(record.filter_ids)

    @api.depends("filter_preset_ids")
    def _compute_preset_count(self):
        for record in self:
            record.preset_count = len(record.filter_preset_ids)

    def eval_domain(self, additional_domain=None):
        """
        Evaluate the static filter domain and combine with additional domain.

        Args:
            additional_domain: Optional list of domain tuples to combine

        Returns:
            Combined domain list
        """
        self.ensure_one()
        domain = []

        # Evaluate static filter domain using ast.literal_eval for safety
        if self.filter_domain:
            try:
                # Use ast.literal_eval for safe evaluation of literal expressions only
                static_domain = ast.literal_eval(self.filter_domain)
                if isinstance(static_domain, list):
                    domain.extend(static_domain)
            except (ValueError, SyntaxError) as e:
                _logger.warning("Failed to evaluate filter_domain for path ID %s: %s", self.id, e)

        # Combine with additional domain
        if additional_domain:
            domain.extend(additional_domain)

        return domain

    def get_available_filters(self, api_client=None):
        """
        Get available filters for this path, optionally filtered by client permissions.

        Args:
            api_client: Optional API client to filter by scope permissions

        Returns:
            Recordset of spp.api.path.filter records
        """
        self.ensure_one()
        filters = self.filter_ids.filtered(lambda f: f.active)

        if api_client and hasattr(api_client, "has_scope_string"):
            # Filter by scope requirements using has_scope_string method
            filters = filters.filtered(lambda f: not f.requires_scope or api_client.has_scope_string(f.requires_scope))

        return filters

    def get_available_presets(self, api_client=None, include_private=False):
        """
        Get available filter presets for this path.

        Args:
            api_client: Optional API client for permission checks
            include_private: Whether to include non-public presets

        Returns:
            Recordset of spp.api.filter.preset records
        """
        self.ensure_one()
        presets = self.filter_preset_ids.filtered(lambda p: p.active)

        if not include_private:
            presets = presets.filtered(lambda p: p.is_public)

        return presets
