# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class SPPCycleMembership(models.Model):
    _name = "spp.cycle.membership"
    _description = "Cycle Membership"
    _order = "partner_id asc,id desc"

    _unique_partner_cycle = models.Constraint(
        "UNIQUE(partner_id, cycle_id)",
        "Beneficiary must be unique per cycle.",
    )

    partner_id = fields.Many2one("res.partner", "Registrant", help="A beneficiary", required=True, index=True)
    cycle_id = fields.Many2one("spp.cycle", "Cycle", help="A cycle", required=True, index=True)
    program_id = fields.Many2one(
        related="cycle_id.program_id",
        string="Program",
        store=True,
        index=True,
    )
    enrollment_date = fields.Date(default=lambda self: fields.Datetime.now())

    compliance_criteria = fields.Char(
        string="Compliance Criteria",
        compute="_compute_compliance_criteria",
        help="The compliance CEL expression from the program that this registrant failed to meet",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("enrolled", "Enrolled"),
            ("paused", "Paused"),
            ("exited", "Exited"),
            ("not_eligible", "Not Eligible"),
            ("non_compliant", "Non-Compliant"),
        ],
        default="draft",
        copy=False,
    )

    def _compute_compliance_criteria(self):
        """Show the compliance CEL expression from the program when non-compliant."""
        for rec in self:
            if rec.state == "non_compliant" and rec.cycle_id and rec.cycle_id.program_id:
                program = rec.cycle_id.program_id
                for wrapper in program.compliance_manager_ids:
                    concrete = wrapper.manager_ref_id
                    if hasattr(concrete, "compliance_cel_expression") and concrete.compliance_cel_expression:
                        rec.compliance_criteria = concrete.compliance_cel_expression
                        break
                else:
                    rec.compliance_criteria = False
            else:
                rec.compliance_criteria = False

    def _compute_display_name(self):
        res = super()._compute_display_name()
        # Prefetch cycle_id and partner_id to avoid N+1 queries in loop
        self.mapped("cycle_id.name")
        self.mapped("partner_id.name")

        for rec in self:
            name = ""
            if rec.cycle_id:
                name += "[" + rec.cycle_id.name + "] "
            if rec.partner_id:
                name += rec.partner_id.name
            rec.display_name = name
        return res

    def open_cycle_membership_form(self):
        return {
            "name": "Cycle Membership",
            "view_mode": "form",
            "res_model": "spp.cycle.membership",
            "res_id": self.id,
            "view_id": self.env.ref("spp_programs.view_cycle_membership_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    def open_registrant_form(self):
        if self.partner_id.is_group:
            return {
                "name": "Group Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": True,
                    "create": False,
                    "edit": False,
                },
            }
        else:
            return {
                "name": "Individual Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": False,
                    "create": False,
                    "edit": False,
                },
            }

    def unlink(self):
        if not self:
            return
        draft_records = self.filtered(lambda x: x.cycle_id.state == "draft")
        if not draft_records:
            raise ValidationError(
                _("Beneficiaries can only be deleted when both the cycle and entitlement are unapproved.")
            )

        # Prefetch partner_id and cycle_id.entitlement_ids to avoid N+1 queries in loop
        draft_records.mapped("partner_id")
        draft_records.mapped("cycle_id.entitlement_ids.partner_id")
        draft_records.mapped("cycle_id.entitlement_ids.state")

        for record in draft_records:
            partner_id = record.partner_id.id
            entitlement = record.cycle_id.entitlement_ids.filtered(lambda x, pid=partner_id: x.partner_id.id == pid)

            if entitlement:
                if entitlement.state == "approved":
                    raise ValidationError(
                        _("Beneficiaries can only be deleted when both the cycle andentitlement are unapproved.")
                    )
                entitlement.unlink()

        return super().unlink()
