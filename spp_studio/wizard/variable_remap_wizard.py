"""Variable Field Remap Wizard."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VariableRemapWizard(models.TransientModel):
    """Wizard to remap a variable to an existing field.

    This wizard allows users to:
    1. Map a 'field' type variable to a different field name
    2. Switch a 'computed' or 'aggregate' variable to use an existing field instead
    """

    _name = "spp.studio.variable.remap.wizard"
    _description = "Variable Field Remap Wizard"

    variable_id = fields.Many2one(
        "spp.cel.variable",
        string="Variable",
        required=True,
        readonly=True,
    )
    variable_name = fields.Char(
        related="variable_id.name",
        readonly=True,
    )
    variable_label = fields.Char(
        related="variable_id.label",
        readonly=True,
    )
    current_source_type = fields.Selection(
        related="variable_id.source_type",
        string="Current Source Type",
        readonly=True,
    )
    current_field = fields.Char(
        related="variable_id.source_field",
        string="Current Field",
        readonly=True,
    )
    current_expression = fields.Text(
        related="variable_id.cel_expression",
        string="Current Expression",
        readonly=True,
    )

    # Target model selection (default to res.partner for computed/aggregate)
    target_model = fields.Selection(
        selection="_get_target_model_selection",
        string="Target Model",
        default="res.partner",
        required=True,
    )

    # Field selection
    new_field_id = fields.Many2one(
        "ir.model.fields",
        string="Map to Field",
        required=True,
        domain="[('model', '=', target_model), ('ttype', 'not in', ['one2many', 'many2many', 'binary'])]",
        help="Select an existing field to map this variable to",
    )
    new_field_preview = fields.Char(
        string="Field Technical Name",
        compute="_compute_new_field_preview",
    )

    # Options
    update_cel_accessor = fields.Boolean(
        string="Update CEL Accessor",
        default=True,
        help="Also update the CEL accessor to match the new field name",
    )

    # Info flags
    is_type_change = fields.Boolean(
        compute="_compute_is_type_change",
        string="Is Type Change",
    )

    @api.model
    def _get_target_model_selection(self):
        """Get available target models."""
        return [
            ("res.partner", "Registrant (res.partner)"),
        ]

    @api.depends("variable_id", "variable_id.source_type")
    def _compute_is_type_change(self):
        """Check if this is a type change (computed/aggregate -> field)."""
        for wizard in self:
            wizard.is_type_change = wizard.current_source_type in ("computed", "aggregate")

    @api.depends("new_field_id")
    def _compute_new_field_preview(self):
        for wizard in self:
            if wizard.new_field_id:
                wizard.new_field_preview = wizard.new_field_id.name
            else:
                wizard.new_field_preview = ""

    @api.onchange("variable_id")
    def _onchange_variable_id(self):
        """Set target model from variable's source_model if available."""
        if self.variable_id and self.variable_id.source_model:
            self.target_model = self.variable_id.source_model

    def action_remap(self):
        """Apply the field remapping."""
        self.ensure_one()

        if not self.new_field_id:
            raise UserError(_("Please select a field to map to."))

        variable = self.variable_id
        new_field_name = self.new_field_id.name
        old_source_type = variable.source_type

        # Build update values
        update_vals = {
            "source_type": "field",
            "source_model": self.target_model,
            "source_field": new_field_name,
        }

        # Clear computed/aggregate specific fields when switching types
        if old_source_type in ("computed", "aggregate"):
            update_vals.update(
                {
                    "cel_expression": False,
                    "aggregate_type": False,
                    "aggregate_target": False,
                    "aggregate_filter": False,
                    "aggregate_field": False,
                }
            )

        if self.update_cel_accessor:
            update_vals["cel_accessor"] = new_field_name

        # Update the variable
        variable.write(update_vals)

        if old_source_type != "field":
            _logger.info(
                "Changed variable '%s' from %s to field '%s.%s'",
                variable.name,
                old_source_type,
                self.target_model,
                new_field_name,
            )
            message = _("Variable '%s' now uses field '%s' instead of %s.") % (
                variable.label or variable.name,
                self.new_field_id.field_description,
                dict(variable._fields["source_type"].selection).get(old_source_type, old_source_type),
            )
        else:
            _logger.info(
                "Remapped variable '%s' from field '%s' to '%s'",
                variable.name,
                self.current_field,
                new_field_name,
            )
            message = _("Variable '%s' is now mapped to field '%s'.") % (
                variable.label or variable.name,
                self.new_field_id.field_description,
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Field Mapped"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }
