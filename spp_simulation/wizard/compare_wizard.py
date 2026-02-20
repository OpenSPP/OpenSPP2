import logging

from odoo import Command, _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SimulationCompareWizard(models.TransientModel):
    """Wizard for creating simulation comparisons."""

    _name = "spp.simulation.compare.wizard"
    _description = "Compare Simulation Runs Wizard"

    run_ids = fields.Many2many(
        comodel_name="spp.simulation.run",
        string="Runs to Compare",
        required=True,
        domain=[("state", "=", "completed")],
    )
    name = fields.Char(
        string="Comparison Name",
        default="Simulation Comparison",
    )

    def action_compare(self):
        """Create a comparison from selected runs."""
        self.ensure_one()
        if len(self.run_ids) < 2:
            raise ValidationError(_("Please select at least 2 completed runs to compare."))

        # Generate a meaningful name if default
        if self.name == "Simulation Comparison":
            scenario_names = self.run_ids.mapped("scenario_id.name")
            self.name = " vs ".join(scenario_names[:3])
            if len(scenario_names) > 3:
                self.name += f" (+{len(scenario_names) - 3} more)"

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": self.name,
                "run_ids": [Command.set(self.run_ids.ids)],
            }
        )
        comparison.action_compute_comparison()

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.simulation.comparison",
            "res_id": comparison.id,
            "view_mode": "form",
            "target": "current",
        }
