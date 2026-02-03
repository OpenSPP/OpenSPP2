from odoo import _, fields, models
from odoo.exceptions import UserError


class ApprovalRejectionWizard(models.TransientModel):
    """Wizard for rejecting records with a reason."""

    _name = "spp.approval.rejection.wizard"
    _description = "Approval Rejection Wizard"

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    reason = fields.Text(
        string="Rejection Reason",
        required=True,
        help="Please provide a reason for rejection",
    )

    def action_reject(self):
        """Perform the rejection."""
        self.ensure_one()

        if not self.reason:
            raise UserError(_("Please provide a rejection reason."))

        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError(_("The record no longer exists."))

        record._do_reject(self.reason)

        return {"type": "ir.actions.act_window_close"}
