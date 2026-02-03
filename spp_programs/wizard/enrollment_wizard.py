# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPProgramEnrollmentWizard(models.TransientModel):
    _name = "spp.program.enrollment.wizard"
    _description = "Program Enrollment Wizard"

    partner_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        readonly=True,
    )
    partner_name = fields.Char(related="partner_id.name", readonly=True)

    # Computed field to determine target type based on registrant
    target_type = fields.Selection(
        selection=[("group", "Group"), ("individual", "Individual")],
        compute="_compute_target_type",
    )

    # Pre-computed allowed programs for domain filtering in popup dialogs
    # Dynamic domains with field references don't work reliably in Odoo 19 popups
    allowed_program_ids = fields.Many2many(
        "spp.program",
        compute="_compute_allowed_programs",
    )

    program_id = fields.Many2one(
        "spp.program",
        string="Program",
        required=True,
        domain="[('id', 'in', allowed_program_ids)]",
    )

    # Show existing enrollments to avoid duplicates
    existing_program_ids = fields.Many2many(
        "spp.program",
        compute="_compute_existing_programs",
    )

    is_already_enrolled = fields.Boolean(
        compute="_compute_is_already_enrolled",
    )

    @api.depends("partner_id")
    def _compute_target_type(self):
        for wizard in self:
            if wizard.partner_id:
                wizard.target_type = "group" if wizard.partner_id.is_group else "individual"
            else:
                wizard.target_type = False

    @api.depends("target_type")
    def _compute_allowed_programs(self):
        for wizard in self:
            if wizard.target_type:
                wizard.allowed_program_ids = self.env["spp.program"].search(
                    [("target_type", "=", wizard.target_type), ("state", "=", "active")]
                )
            else:
                wizard.allowed_program_ids = False

    @api.depends("partner_id")
    def _compute_existing_programs(self):
        for wizard in self:
            if wizard.partner_id:
                wizard.existing_program_ids = wizard.partner_id.program_membership_ids.mapped("program_id")
            else:
                wizard.existing_program_ids = False

    @api.depends("program_id", "existing_program_ids")
    def _compute_is_already_enrolled(self):
        for wizard in self:
            wizard.is_already_enrolled = wizard.program_id in wizard.existing_program_ids

    def action_enroll(self):
        """Create enrollment and trigger eligibility verification."""
        self.ensure_one()

        if self.is_already_enrolled:
            raise UserError(_("Registrant is already enrolled in this program."))

        # Create membership in draft state (pending verification)
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": self.partner_id.id,
                "program_id": self.program_id.id,
                "state": "draft",
            }
        )

        _logger.info(
            "Created program enrollment: partner_id=%s, program_id=%s, membership_id=%s",
            self.partner_id.id,
            self.program_id.id,
            membership.id,
        )

        # Trigger eligibility verification if configured
        if hasattr(membership, "check_eligibility"):
            membership.check_eligibility()

        # Close wizard and show notification - stay on registrant form
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Enrollment Successful"),
                "message": _("Registrant has been enrolled in %s. Eligibility verification is pending.")
                % self.program_id.name,
                "sticky": False,
                "type": "success",
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }
