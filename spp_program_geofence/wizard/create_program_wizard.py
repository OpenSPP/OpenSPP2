# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import Command, fields, models


class SPPCreateNewProgramWizGeofence(models.TransientModel):
    _inherit = "spp.program.create.wizard"

    geofence_ids = fields.Many2many(
        "spp.gis.geofence",
        string="Geofences",
        help="Define the geographic scope for this program.",
    )
    include_area_fallback = fields.Boolean(
        default=True,
        string="Fall back to admin area",
        help="When enabled, registrants whose administrative area intersects the geofence "
        "are included even if their GPS coordinates are not set.",
    )
    fallback_area_type_id = fields.Many2one(
        "spp.area.type",
        string="Area level",
        help="When set, only areas of this type are considered for the area fallback. "
        "Use this to restrict matching to a specific administrative level (e.g. District).",
    )

    def get_program_vals(self):
        vals = super().get_program_vals()
        if self.geofence_ids:
            vals["geofence_ids"] = [Command.set(self.geofence_ids.ids)]
        return vals

    def _get_eligibility_manager(self, program_id):
        if not self.geofence_ids:
            return super()._get_eligibility_manager(program_id)

        # Create a geofence eligibility manager instead of the default one
        geofence_mgr = self.env["spp.program.membership.manager.geofence"].create(
            {
                "name": "Geofence",
                "program_id": program_id,
                "include_area_fallback": self.include_area_fallback,
                "fallback_area_type_id": self.fallback_area_type_id.id or False,
            }
        )

        parent_mgr = self.env["spp.eligibility.manager"].create(
            self._get_eligibility_managers_val(program_id, geofence_mgr)
        )

        return {
            "eligibility_manager_ids": [Command.link(parent_mgr.id)],
        }
