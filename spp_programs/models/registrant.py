# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPRegistrant(models.Model):
    _inherit = "res.partner"

    # Custom Fields
    program_membership_ids = fields.One2many("spp.program.membership", "partner_id", "Program Memberships")
    cycle_ids = fields.One2many("spp.cycle.membership", "partner_id", "Cycle Memberships")
    entitlement_ids = fields.One2many("spp.entitlement", "partner_id", "Entitlements")
    inkind_entitlement_ids = fields.One2many("spp.entitlement.inkind", "partner_id", "In-kind Entitlements")

    # Statistics
    program_membership_count = fields.Integer(
        string="# Program Memberships",
        compute="_compute_program_membership_count",
        store=True,
    )
    entitlements_count = fields.Integer(string="# Cash Entitlements", compute="_compute_entitlements_count", store=True)
    cycles_count = fields.Integer(string="# Cycles", compute="_compute_cycle_count", store=True)
    inkind_entitlements_count = fields.Integer(
        string="# In-kind Entitlements",
        compute="_compute_inkind_entitlements_count",
        store=True,
    )
    total_entitlements_count = fields.Integer(
        string="Total Entitlements",
        compute="_compute_total_entitlements_count",
    )

    @api.depends("entitlements_count", "inkind_entitlements_count")
    def _compute_total_entitlements_count(self):
        """Compute combined count of cash and in-kind entitlements."""
        for rec in self:
            rec.total_entitlements_count = rec.entitlements_count + rec.inkind_entitlements_count

    @api.depends("program_membership_ids")
    def _compute_program_membership_count(self):
        """Batch-efficient program membership count using read_group."""
        if not self:
            return

        registrants = self.filtered("is_registrant")
        for partner in self - registrants:
            partner.program_membership_count = 0

        if not registrants:
            return

        data = self.env["spp.program.membership"]._read_group(
            domain=[("partner_id", "in", registrants.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        counts = {partner.id: count for partner, count in data}

        for partner in registrants:
            partner.program_membership_count = counts.get(partner.id, 0)

    @api.depends("entitlement_ids")
    def _compute_entitlements_count(self):
        """Batch-efficient entitlements count using _read_group."""
        if not self:
            return

        registrants = self.filtered("is_registrant")
        for partner in self - registrants:
            partner.entitlements_count = 0

        if not registrants:
            return

        data = self.env["spp.entitlement"]._read_group(
            domain=[("partner_id", "in", registrants.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        counts = {partner.id: count for partner, count in data}

        for partner in registrants:
            partner.entitlements_count = counts.get(partner.id, 0)

    @api.depends("cycle_ids")
    def _compute_cycle_count(self):
        """Batch-efficient cycle membership count using _read_group."""
        if not self:
            return

        registrants = self.filtered("is_registrant")
        for partner in self - registrants:
            partner.cycles_count = 0

        if not registrants:
            return

        data = self.env["spp.cycle.membership"]._read_group(
            domain=[("partner_id", "in", registrants.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        counts = {partner.id: count for partner, count in data}

        for partner in registrants:
            partner.cycles_count = counts.get(partner.id, 0)

    @api.depends("inkind_entitlement_ids")
    def _compute_inkind_entitlements_count(self):
        """Batch-efficient in-kind entitlements count using _read_group."""
        if not self:
            return

        registrants = self.filtered("is_registrant")
        for partner in self - registrants:
            partner.inkind_entitlements_count = 0

        if not registrants:
            return

        data = self.env["spp.entitlement.inkind"]._read_group(
            domain=[("partner_id", "in", registrants.ids)],
            groupby=["partner_id"],
            aggregates=["__count"],
        )
        counts = {partner.id: count for partner, count in data}

        for partner in registrants:
            partner.inkind_entitlements_count = counts.get(partner.id, 0)

    def action_view_program_memberships(self):
        """Open program memberships for this registrant."""
        self.ensure_one()
        return {
            "name": _("Program Enrollments - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.program.membership",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_all_entitlements(self):
        """Open all entitlements (cash + in-kind) for this registrant."""
        self.ensure_one()
        return {
            "name": _("Entitlements - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.entitlement",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_enroll_in_program(self):
        """Open wizard to enroll registrant in a program."""
        self.ensure_one()
        return {
            "name": _("Enroll in Program"),
            "type": "ir.actions.act_window",
            "res_model": "spp.program.enrollment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.id,
                "default_partner_name": self.name,
            },
        }

    @api.constrains("email")
    def _check_valid_email(self):
        for record in self:
            if record.email and not tools.single_email_re.match(record.email):
                raise ValidationError(_("Invalid Email! Please enter a valid email address."))
