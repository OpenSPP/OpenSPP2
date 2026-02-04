# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Program Parameter - Program-level overrides for CEL Variables.

Allows programs to override default values for constant variables.
For example, each program can have its own poverty_line threshold.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CELProgramParameter(models.Model):
    """Program-level parameter overrides for CEL Variables."""

    _name = "spp.cel.program.parameter"
    _description = "CEL Program Parameter"
    _order = "program_id, variable_id"

    program_id = fields.Many2one(
        comodel_name="spp.program",
        string="Program",
        required=True,
        ondelete="cascade",
        index=True,
    )
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="Variable",
        required=True,
        ondelete="cascade",
        domain="[('source_type', '=', 'constant'), ('is_program_configurable', '=', True)]",
        index=True,
    )
    value = fields.Char(
        string="Value",
        required=True,
        help="Override value for this program",
    )

    # Display helpers
    variable_name = fields.Char(
        related="variable_id.name",
        string="Variable Name",
        readonly=True,
    )
    default_value = fields.Char(
        related="variable_id.default_value",
        string="Default Value",
        readonly=True,
    )
    value_type = fields.Selection(
        related="variable_id.value_type",
        string="Value Type",
        readonly=True,
    )

    @api.constrains("program_id", "variable_id")
    def _check_unique_program_variable(self):
        """Ensure each variable is configured only once per program."""
        for rec in self:
            if rec.program_id and rec.variable_id:
                duplicate = self.search_count(
                    [
                        ("program_id", "=", rec.program_id.id),
                        ("variable_id", "=", rec.variable_id.id),
                        ("id", "!=", rec.id),
                    ]
                )
                if duplicate:
                    raise ValidationError(_("Each variable can only be configured once per program."))

    @api.constrains("value", "variable_id")
    def _check_value_type(self):
        """Validate that value matches expected type."""
        for rec in self:
            if not rec.value or not rec.variable_id:
                continue

            value_type = rec.variable_id.value_type
            value = rec.value.strip()

            try:
                if value_type == "number":
                    float(value)
                elif value_type == "boolean":
                    if value.lower() not in ("true", "false", "1", "0"):
                        raise ValueError("Must be true/false")
                elif value_type == "money":
                    float(value)
            except ValueError as e:
                raise ValidationError(
                    _("Invalid value '%(value)s' for variable '%(name)s' (expected %(type)s): %(error)s")
                    % {
                        "value": value,
                        "name": rec.variable_id.name,
                        "type": value_type,
                        "error": str(e),
                    }
                ) from e

    @api.model
    def get_program_value(self, program_id, variable_name):
        """Get the program-specific value for a variable."""
        param = self.search(
            [
                ("program_id", "=", program_id),
                ("variable_id.name", "=", variable_name),
            ],
            limit=1,
        )
        return param.value if param else None

    def name_get(self):
        """Display as 'Program: Variable = Value'."""
        return [(rec.id, f"{rec.program_id.name}: {rec.variable_id.name} = {rec.value}") for rec in self]

    # ═══════════════════════════════════════════════════════════════════════
    # CACHE INVALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def _invalidate_resolver_cache(self):
        """Invalidate the variable resolver cache."""
        try:
            resolver = self.env["spp.cel.variable.resolver"]
            resolver.invalidate_variable_cache()
        except Exception as e:
            _logger.debug("Could not invalidate resolver cache: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to invalidate resolver cache."""
        records = super().create(vals_list)
        if records:
            records[0]._invalidate_resolver_cache()
        return records

    def write(self, vals):
        """Override write to invalidate resolver cache when value changes."""
        result = super().write(vals)
        if "value" in vals:
            self._invalidate_resolver_cache()
        return result

    def unlink(self):
        """Override unlink to invalidate resolver cache."""
        self._invalidate_resolver_cache()
        return super().unlink()
