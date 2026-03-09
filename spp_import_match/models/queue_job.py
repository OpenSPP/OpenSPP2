# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, models


class SPPQueueJob(models.Model):
    """Job status and result"""

    _inherit = "queue.job"

    def _related_action_attachment(self):
        res_id = self.kwargs.get("att_id")
        action = {
            "name": _("Attachment"),
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "view_mode": "form",
            "res_id": res_id,
        }
        return action
