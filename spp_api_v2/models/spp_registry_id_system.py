# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Protect system_id registry entries from manual edits."""

from odoo import _, api, models
from odoo.exceptions import UserError


class SPPRegistryIdSystem(models.Model):
    _inherit = "spp.registry.id"

    @api.ondelete(at_uninstall=False)
    def _prevent_system_id_delete(self):
        """Prevent deletion of system_id entries."""
        for rec in self:
            if rec.id_type_id and rec.id_type_id.code == "system_id":
                raise UserError(_("System ID is auto-generated and cannot be deleted."))

    def write(self, vals):
        """Prevent editing value of system_id entries."""
        if "value" in vals:
            for rec in self:
                if rec.id_type_id and rec.id_type_id.code == "system_id":
                    raise UserError(_("System ID is auto-generated and cannot be modified."))
        return super().write(vals)
