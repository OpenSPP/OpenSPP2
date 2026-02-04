import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LogicTestPersona(models.Model):
    _name = "spp.studio.test.persona"
    _description = "Test Persona"
    _order = "sequence, name"

    name = fields.Char(
        string="Persona Name",
        required=True,
        help="Descriptive name, e.g., 'Poor Elderly Widow'",
    )
    description = fields.Text(
        string="Description",
        help="Detailed description of this persona and what scenarios it represents",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which personas are displayed",
    )

    # Persona Values
    values = fields.Text(
        string="Values",
        required=True,
        help="JSON object with variable values for this persona",
        default="{}",
    )
    values_display = fields.Html(
        string="Values Display",
        compute="_compute_values_display",
        help="Formatted display of persona values",
    )

    # Categorization
    category = fields.Selection(
        [
            ("eligible", "Eligible"),
            ("ineligible", "Ineligible"),
            ("edge", "Edge Case"),
        ],
        string="Category",
        help="Classification of this persona for testing purposes",
    )

    # Sharing
    is_global = fields.Boolean(
        string="Is Global",
        default=False,
        help="If true, this persona is available to all logic. If false, it belongs to a specific logic.",
    )
    logic_id = fields.Many2one(
        "spp.cel.expression",
        string="Logic",
        help="If not global, this persona belongs to this specific logic",
        ondelete="cascade",
    )

    # Metadata
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive personas are hidden but not deleted",
    )

    @api.depends("values")
    def _compute_values_display(self):
        """Parse JSON and format as readable HTML table."""
        for persona in self:
            if not persona.values:
                persona.values_display = "<p>No values defined</p>"
                continue

            try:
                values_dict = json.loads(persona.values)

                if not values_dict:
                    persona.values_display = "<p>No values defined</p>"
                    continue

                # Build HTML table
                html_parts = [
                    '<table class="table table-sm table-striped">',
                    "  <thead>",
                    "    <tr>",
                    "      <th>Variable</th>",
                    "      <th>Value</th>",
                    "      <th>Type</th>",
                    "    </tr>",
                    "  </thead>",
                    "  <tbody>",
                ]

                for key in sorted(values_dict.keys()):
                    value = values_dict[key]
                    value_type = type(value).__name__
                    value_display = self._format_value_for_display(value)

                    html_parts.extend(
                        [
                            "    <tr>",
                            f"      <td><strong>{key}</strong></td>",
                            f"      <td>{value_display}</td>",
                            f"      <td><em>{value_type}</em></td>",
                            "    </tr>",
                        ]
                    )

                html_parts.extend(
                    [
                        "  </tbody>",
                        "</table>",
                    ]
                )

                persona.values_display = "\n".join(html_parts)

            except json.JSONDecodeError as e:
                _logger.error("Invalid JSON in persona ID %s values: %s", persona.id, str(e))
                persona.values_display = f"<p class='text-danger'>Invalid JSON: {str(e)}</p>"
            except Exception as e:
                _logger.exception("Error formatting persona %s values display", persona.name)
                persona.values_display = f"<p class='text-danger'>Error: {str(e)}</p>"

    def _format_value_for_display(self, value):
        """Format a value for HTML display."""
        if value is None:
            return "<em>null</em>"
        elif isinstance(value, bool):
            return f"<strong>{'true' if value else 'false'}</strong>"
        elif isinstance(value, int | float):
            return str(value)
        elif isinstance(value, str):
            # Escape HTML
            from markupsafe import escape

            return escape(value)
        elif isinstance(value, list | dict):
            # Pretty print complex types
            from markupsafe import escape

            return f"<code>{escape(json.dumps(value, indent=2))}</code>"
        else:
            from markupsafe import escape

            return escape(str(value))

    def get_values_dict(self):
        """Return parsed JSON as Python dict."""
        self.ensure_one()

        if not self.values:
            return {}

        try:
            return json.loads(self.values)
        except json.JSONDecodeError as e:
            _logger.error("Invalid JSON in persona ID %s values: %s", self.id, str(e))
            raise UserError(f"Invalid JSON in persona '{self.name}': {str(e)}") from e

    def action_duplicate(self):
        """Create a copy of this persona."""
        self.ensure_one()

        new_persona = self.copy(
            {
                "name": f"{self.name} (Copy)",
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.studio.test.persona",
            "res_id": new_persona.id,
            "view_mode": "form",
            "target": "current",
        }

    def toggle_active(self):
        """Toggle the active state of the persona."""
        for record in self:
            record.active = not record.active

    @api.constrains("values")
    def _check_values_json(self):
        """Validate that values contains valid JSON."""
        for persona in self:
            if not persona.values:
                continue

            try:
                json.loads(persona.values)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Persona '{persona.name}': Invalid JSON in values field: {str(e)}") from e

    @api.constrains("is_global", "logic_id")
    def _check_global_logic_exclusivity(self):
        """Validate that global personas don't have a logic_id and vice versa."""
        for persona in self:
            if persona.is_global and persona.logic_id:
                raise ValidationError(
                    f"Persona '{persona.name}': Global personas cannot belong to a specific logic. "
                    "Either uncheck 'Is Global' or remove the Logic assignment."
                )
            if not persona.is_global and not persona.logic_id:
                raise ValidationError(
                    f"Persona '{persona.name}': Non-global personas must belong to a specific logic. "
                    "Either check 'Is Global' or assign a Logic."
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default values if not provided."""
        for vals in vals_list:
            if "values" not in vals or not vals["values"]:
                vals["values"] = "{}"
        return super().create(vals_list)

    def write(self, vals):
        """Override write to validate values if being updated."""
        if "values" in vals and not vals["values"]:
            vals["values"] = "{}"
        return super().write(vals)
