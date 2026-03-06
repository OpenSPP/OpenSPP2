# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields, models


class SPPCreateNewProgramWizGeofence(models.TransientModel):
    _inherit = "spp.program.create.wizard"

    geofence_ids = fields.Many2many(
        "spp.gis.geofence",
        string="Geofences",
        help="Define the geographic scope for this program.",
    )

    def get_program_vals(self):
        vals = super().get_program_vals()
        if self.geofence_ids:
            vals["geofence_ids"] = [Command.set(self.geofence_ids.ids)]
        return vals
