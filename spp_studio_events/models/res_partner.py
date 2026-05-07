# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Route the Event Data button on the registrant form to the Studio-aware
wizard whenever any active Studio event type covers the registrant's
target type. Falls back to the basic wizard from `spp_event_data` when no
Studio types apply, preserving the legacy / non-Studio entry path."""

from odoo import _, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def open_create_event_wizard(self):
        """Open the Studio entry wizard if active Studio event types exist
        for this registrant's target type; otherwise fall back to the basic
        wizard provided by `spp_event_data`.
        """
        for rec in self:
            target_type = "group" if rec.is_group else "individual"
            studio_types = self.env["spp.studio.event.type"].search(
                [
                    ("state", "=", "active"),
                    ("target_type", "in", (target_type, "both")),
                ],
                limit=1,
            )
            if not studio_types:
                # No Studio types apply — keep the legacy basic wizard.
                return super().open_create_event_wizard()

            view = self.env.ref("spp_studio_events.view_event_data_entry_wizard_form")
            return {
                "name": _("Create Event Data"),
                "type": "ir.actions.act_window",
                "res_model": "spp.event.data.entry.wizard",
                "view_mode": "form",
                "view_id": view.id,
                "target": "new",
                "context": dict(
                    self.env.context,
                    default_partner_id=rec.id,
                ),
            }
