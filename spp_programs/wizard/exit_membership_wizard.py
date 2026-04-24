# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import UserError


class ExitMembershipWizard(models.TransientModel):
    """Capture the exit reason when a beneficiary leaves a program.

    Launched from the Exit button on `spp.program.membership`; applies
    state / exit_date / exit_reason atomically on confirm.
    """

    _name = "spp.program.membership.exit.wizard"
    _description = "Exit Program Membership Wizard"

    membership_id = fields.Many2one(
        "spp.program.membership",
        string="Membership",
        required=True,
        readonly=True,
    )
    registrant_name = fields.Char(related="membership_id.partner_id.name", readonly=True)
    program_name = fields.Char(related="membership_id.program_id.name", readonly=True)
    exit_date = fields.Date(
        default=fields.Date.today,
        required=True,
    )
    exit_reason = fields.Char(
        string="Reason",
        required=True,
        help="Free-text reason recorded on the program membership (e.g. 'Graduated', 'Opted out', 'Moved').",
    )

    def action_confirm_exit(self):
        self.ensure_one()
        if self.membership_id.state not in ("enrolled", "paused"):
            raise UserError(_("Only enrolled or paused memberships can be exited."))
        self.membership_id.write(
            {
                "state": "exited",
                "exit_date": self.exit_date,
                "exit_reason": self.exit_reason,
            }
        )
        return {"type": "ir.actions.act_window_close"}
