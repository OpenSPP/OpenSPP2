# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Single-record request-changes wizard for DRIMS requests (OP#1161).

The "Request Changes" button called ``action_request_revision`` directly with
no notes, so a reviewer sending a request back could never explain what needed
to change. Mirroring the Reject wizard, this collects a required notes text
before invoking ``action_request_revision(notes=...)`` on the request.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class DrimsRequestRevisionWizard(models.TransientModel):
    _name = "spp.drims.request.revision.wizard"
    _description = "DRIMS Request Revision Wizard"

    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        required=True,
        readonly=True,
    )
    notes = fields.Text(
        string="Requested Changes",
        required=True,
        help="Explain what the submitter needs to change. Stored on the request and shown to the submitter.",
    )

    def action_request_revision(self):
        self.ensure_one()
        if not self.notes or not self.notes.strip():
            raise UserError(_("Please describe the changes you are requesting."))
        self.request_id.action_request_revision(notes=self.notes)
        return {"type": "ir.actions.act_window_close"}
