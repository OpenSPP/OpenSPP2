import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SimulationScenarioTemplate(models.Model):
    """Pre-built targeting scenario templates for non-technical users."""

    _name = "spp.simulation.scenario.template"
    _description = "Simulation Scenario Template"
    _order = "category, sequence, name"

    name = fields.Char(string="Name", required=True, translate=True)
    description = fields.Text(string="Description", translate=True)
    category = fields.Selection(
        selection=[
            ("age", "Age-Based"),
            ("geographic", "Geographic"),
            ("vulnerability", "Vulnerability"),
            ("economic", "Economic"),
            ("categorical", "Categorical"),
        ],
        string="Category",
        required=True,
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    target_type = fields.Selection(
        selection=[
            ("group", "Group"),
            ("individual", "Individual"),
        ],
        string="Target Type",
        required=True,
        default="group",
    )
    targeting_expression = fields.Text(
        string="Targeting Expression (CEL)",
        required=True,
        help="CEL expression that defines who is eligible.",
    )
    default_amount = fields.Float(
        string="Default Amount",
        help="Default entitlement amount for this template.",
    )
    default_amount_mode = fields.Selection(
        selection=[
            ("fixed", "Fixed Amount"),
            ("multiplier", "Multiplier"),
        ],
        string="Default Amount Mode",
        default="fixed",
    )
    ideal_population_expression = fields.Text(
        string="Ideal Population Expression (CEL)",
        help="CEL expression for the ideal target population (for accuracy measurement).",
    )
    icon = fields.Char(
        string="Icon",
        default="fa-users",
        help="Font Awesome icon class for visual identification.",
    )
    active = fields.Boolean(string="Active", default=True)
    cel_profile = fields.Char(
        string="CEL Profile",
        compute="_compute_cel_profile",
        store=False,
        help="CEL profile based on target type (registry_groups or registry_individuals)",
    )

    @api.depends("target_type")
    def _compute_cel_profile(self):
        """Compute the CEL profile based on target type."""
        for record in self:
            record.cel_profile = (
                "registry_groups" if record.target_type == "group" else "registry_individuals"
            )
