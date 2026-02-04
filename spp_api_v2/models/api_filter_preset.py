# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""API Filter Preset model for saved filter combinations."""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SppApiFilterPreset(models.Model):
    """
    Saved filter combinations that API consumers can reuse.

    Presets allow common filter combinations to be named and
    referenced by API clients instead of specifying all conditions.
    """

    _name = "spp.api.filter.preset"
    _description = "API Filter Preset"
    _order = "name"

    name = fields.Char(
        required=True,
        help="Unique preset name (e.g., 'vulnerable_seniors', 'active_beneficiaries')",
    )
    path_id = fields.Many2one(
        "spp.api.path",
        string="API Path",
        required=True,
        ondelete="cascade",
        help="API endpoint this preset applies to",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        related="path_id.model_id",
        store=True,
    )

    description = fields.Text(
        help="Human-readable description of what this preset filters for",
    )
    filter_json = fields.Text(
        required=True,
        help="JSON array of filter conditions. Format: " '[{"field": "age", "operator": "gte", "value": 65}, ...]',
    )

    # Access control
    is_public = fields.Boolean(
        default=True,
        help="Whether this preset is visible to all API clients",
    )
    active = fields.Boolean(default=True)

    @api.constrains("path_id", "name")
    def _check_unique_name_per_path(self):
        """Ensure preset name is unique per API path."""
        for record in self:
            if not record.path_id or not record.name:
                continue

            domain = [
                ("path_id", "=", record.path_id.id),
                ("name", "=", record.name),
                ("id", "!=", record.id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    _("Preset name must be unique per API path. " "A preset named '%s' already exists for this path.")
                    % record.name
                )

    @api.constrains("filter_json")
    def _check_filter_json(self):
        """Validate that filter_json is valid JSON with correct structure."""
        for record in self:
            if not record.filter_json:
                continue

            try:
                filters = json.loads(record.filter_json)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON in filter_json: {e}") from e

            if not isinstance(filters, list):
                raise ValidationError("filter_json must be a JSON array")

            for i, condition in enumerate(filters):
                if not isinstance(condition, dict):
                    raise ValidationError(f"Filter condition {i + 1} must be an object")

                # Check for either simple condition or compound logic
                if "logic" in condition:
                    # Compound condition with AND/OR
                    if condition["logic"] not in ("AND", "OR"):
                        raise ValidationError(f"Filter condition {i + 1}: 'logic' must be 'AND' or 'OR'")
                    if "conditions" not in condition:
                        raise ValidationError(f"Filter condition {i + 1}: compound logic requires 'conditions' array")
                    if not isinstance(condition["conditions"], list):
                        raise ValidationError(f"Filter condition {i + 1}: 'conditions' must be an array")
                else:
                    # Simple condition
                    if "field" not in condition:
                        raise ValidationError(f"Filter condition {i + 1}: missing required 'field' property")

    @api.constrains("name")
    def _check_name_format(self):
        """Ensure preset name follows valid format (alphanumeric + underscores)."""
        import re

        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        for record in self:
            if not pattern.match(record.name):
                raise ValidationError(
                    f"Preset name '{record.name}' is invalid. "
                    "Use lowercase letters, numbers, and underscores. "
                    "Must start with a letter."
                )

    def get_filters(self):
        """
        Parse and return the filter conditions.

        Returns:
            List of filter condition dictionaries
        """
        self.ensure_one()
        if not self.filter_json:
            return []
        try:
            return json.loads(self.filter_json)
        except json.JSONDecodeError:
            _logger.warning("Failed to parse filter_json for preset ID %s", self.id)
            return []

    def to_domain(self, filter_service):
        """
        Convert this preset's filters to an Odoo domain.

        Args:
            filter_service: FilterService instance to use for domain generation

        Returns:
            List of domain tuples
        """
        self.ensure_one()
        filters = self.get_filters()
        return filter_service.filters_to_domain(filters, self.path_id)

    def to_metadata(self):
        """
        Convert this preset to metadata dictionary for API response.

        Returns:
            Dictionary with preset metadata
        """
        self.ensure_one()
        return {
            "name": self.name,
            "description": self.description or "",
        }
