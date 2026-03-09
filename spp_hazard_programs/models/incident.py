# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class HazardIncident(models.Model):
    """
    Extends spp.hazard.incident to add program integration.

    This extension links incidents to programs, enabling tracking of
    which programs are responding to which incidents.
    """

    _inherit = "spp.hazard.incident"

    program_ids = fields.Many2many(
        "spp.program",
        "spp_program_hazard_incident_rel",
        "incident_id",
        "program_id",
        string="Response Programs",
        help="Programs responding to this incident",
    )
    program_count = fields.Integer(
        compute="_compute_program_count",
        string="Number of Programs",
    )

    def _compute_program_count(self):
        """Compute the number of programs responding to this incident."""
        for rec in self:
            rec.program_count = len(rec.program_ids)

    def action_view_programs(self):
        """Open a list view of programs responding to this incident."""
        self.ensure_one()
        return {
            "name": _("Response Programs - %s", self.name),
            "type": "ir.actions.act_window",
            "res_model": "spp.program",
            "view_mode": "list,form",
            "domain": [("id", "in", self.program_ids.ids)],
            "context": {},
        }
