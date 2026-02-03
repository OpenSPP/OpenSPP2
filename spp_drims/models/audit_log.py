# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import models


class AuditLogDrims(models.Model):
    """Extension of audit log for DRIMS activity feed navigation."""

    _inherit = "spp.audit.log"

    def action_view_record(self):
        """Navigate to the related record.

        Opens the form view of the record that was audited.
        """
        self.ensure_one()
        if not self.model_id or not self.res_id:
            return False

        # Check if record still exists
        record = self.env[self.model_id.model].browse(self.res_id).exists()
        if not record:
            return False

        return {
            "type": "ir.actions.act_window",
            "res_model": self.model_id.model,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
