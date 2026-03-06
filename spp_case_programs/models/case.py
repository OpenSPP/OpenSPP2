"""Extend Case model with program integration."""

from odoo import api, fields, models


class CasePrograms(models.Model):
    """Extend spp.case with program enrollment tracking and compliance."""

    _inherit = "spp.case"

    # Program Relations
    program_membership_ids = fields.Many2many(
        "spp.program.membership",
        "spp_case_program_membership_rel",
        "case_id",
        "membership_id",
        string="Program Enrollments",
        help="Program enrollments related to this case",
    )

    triggered_by_program_id = fields.Many2one(
        "spp.program",
        string="Triggered By Program",
        help="Program that triggered case creation (e.g., non-compliance)",
        tracking=True,
    )

    # Computed Program Info
    has_active_enrollment = fields.Boolean(
        compute="_compute_program_info",
        store=True,
        help="Whether the client has any active program enrollments",
    )

    active_program_count = fields.Integer(
        string="Active Programs",
        compute="_compute_program_info",
        store=True,
        help="Number of active program enrollments",
    )

    enrolled_program_names = fields.Char(
        string="Enrolled Programs",
        compute="_compute_program_info",
        store=False,
        help="Names of programs the client is enrolled in",
    )

    @api.depends("program_membership_ids", "program_membership_ids.state")
    def _compute_program_info(self):
        """Compute program enrollment information."""
        for case in self:
            # Filter for active enrollments
            active_memberships = case.program_membership_ids.filtered(lambda m: m.state in ["enrolled", "paused"])

            case.has_active_enrollment = bool(active_memberships)
            case.active_program_count = len(active_memberships)

            # Build list of program names
            if active_memberships:
                program_names = active_memberships.mapped("program_id.name")
                case.enrolled_program_names = ", ".join(program_names)
            else:
                case.enrolled_program_names = ""

    @api.onchange("partner_id")
    def _onchange_partner_programs(self):
        """Load program memberships when client/partner is selected."""
        if self.partner_id:
            # Search for all program memberships for this partner
            memberships = self.env["spp.program.membership"].search([("partner_id", "=", self.partner_id.id)])
            self.program_membership_ids = memberships
        else:
            self.program_membership_ids = False

    def action_view_program_enrollments(self):
        """Open program enrollments in a new window."""
        self.ensure_one()

        return {
            "name": "Program Enrollments",
            "type": "ir.actions.act_window",
            "res_model": "spp.program.membership",
            "view_mode": "list,form",
            "domain": [("id", "in", self.program_membership_ids.ids)],
            "context": {
                "create": False,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_triggered_program(self):
        """Open the program that triggered this case."""
        self.ensure_one()

        if not self.triggered_by_program_id:
            return False

        return {
            "name": "Program",
            "type": "ir.actions.act_window",
            "res_model": "spp.program",
            "res_id": self.triggered_by_program_id.id,
            "view_mode": "form",
            "target": "current",
        }
