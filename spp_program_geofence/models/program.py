# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class SPPProgram(models.Model):
    _inherit = "spp.program"

    geofence_ids = fields.Many2many(
        "spp.gis.geofence",
        "spp_program_geofence_rel",
        "program_id",
        "geofence_id",
        string="Geofences",
        help="Geographic boundaries that define this program's scope.",
    )
    geofence_count = fields.Integer(
        compute="_compute_geofence_count",
        string="Geofence Count",
    )

    @api.depends("geofence_ids")
    def _compute_geofence_count(self):
        for rec in self:
            rec.geofence_count = len(rec.geofence_ids)

    def action_open_geofences(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Program Geofences",
            "res_model": "spp.gis.geofence",
            "view_mode": "list,form",
            "domain": [("id", "in", self.geofence_ids.ids)],
            "context": dict(self.env.context),
        }
