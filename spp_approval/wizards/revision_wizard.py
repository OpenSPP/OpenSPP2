from odoo import _, fields, models
from odoo.exceptions import UserError


class ApprovalRevisionWizard(models.TransientModel):
    """Wizard for requesting revisions with notes."""

    _name = "spp.approval.revision.wizard"
    _description = "Approval Revision Request Wizard"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    notes = fields.Text(
        string="Revision Notes",
        required=True,
        help="Please describe what changes are needed",
    )

    def action_request_revision(self):
        """Perform the revision request."""
        self.ensure_one()

        if not self.notes:
            raise UserError(_("Please provide revision notes describing what needs to be changed."))

        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_("The record no longer exists."))

        record._do_request_revision(self.notes)

        return {"type": "ir.actions.act_window_close"}
