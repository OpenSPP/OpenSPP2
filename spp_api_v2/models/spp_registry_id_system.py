# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Hide system_id from the ID type dropdown in the UI."""

from odoo import models


class SPPRegistryIdSystem(models.Model):
    _inherit = "spp.registry.id"

    def _compute_available_id_type_ids(self):  # pylint: disable=missing-return
        """Exclude system_id from the dropdown — it is auto-assigned, not user-selectable."""
        super()._compute_available_id_type_ids()
        for rec in self:
            rec.available_id_type_ids = rec.available_id_type_ids.filtered(lambda c: c.code != "system_id")
