# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Single-record reject wizard for DRIMS requests (OP#966).

The Reject button on the request form was calling ``action_reject``
directly and the user had no way to supply a rejection reason — the
audit trail lost the rationale. This wizard collects a required reason
before invoking ``action_reject(reason=...)`` on the request.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class DrimsRequestRejectWizard(models.TransientModel):
    _name = "spp.drims.request.reject.wizard"
    _description = "DRIMS Request Reject Wizard"

    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Rejection Reason",
        required=True,
        help="This text is stored on the request and shown in the audit trail.",
    )

    def action_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_("Please provide a rejection reason."))
        self.request_id.action_reject(reason=self.reason)
        return {"type": "ir.actions.act_window_close"}
