from odoo import api, fields, models


class CaseRegistry(models.Model):
    _inherit = "spp.case"

    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        tracking=True,
        help="Primary individual registrant for this case",
    )
    household_id = fields.Many2one(
        "res.partner",
        string="Household",
        domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
        tracking=True,
        help="Household related to this case",
    )
    household_member_ids = fields.Many2many(
        "res.partner",
        "spp_case_household_member_rel",
        "case_id",
        "partner_id",
        string="Involved Household Members",
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        help="Other household members involved in this case",
    )
    area_id = fields.Many2one(
        "spp.area",
        string="Geographic Area",
        help="Area of the client for geographic assignment",
    )

    # Previous cases detection
    previous_case_ids = fields.Many2many(
        "spp.case",
        "spp_case_previous_rel",
        "case_id",
        "previous_case_id",
        string="Previous Cases",
        compute="_compute_previous_cases",
    )
    previous_case_count = fields.Integer(
        compute="_compute_previous_cases",
    )

    @api.depends("registrant_id", "household_id")
    def _compute_previous_cases(self):
        """Find previous cases for same registrant/household."""
        for case in self:
            domain = [("id", "!=", case.id)]
            if case.registrant_id:
                domain.append(("registrant_id", "=", case.registrant_id.id))
            elif case.household_id:
                domain.append(("household_id", "=", case.household_id.id))
            else:
                case.previous_case_ids = False
                case.previous_case_count = 0
                continue

            previous = self.search(domain)
            case.previous_case_ids = previous
            case.previous_case_count = len(previous)

    @api.onchange("registrant_id")
    def _onchange_registrant_id(self):
        """Auto-fill from registrant."""
        if self.registrant_id:
            self.partner_id = self.registrant_id.id
            # Get household membership
            membership = self.env["spp.group.membership"].search(
                [
                    ("individual", "=", self.registrant_id.id),
                ],
                limit=1,
            )
            if membership:
                self.household_id = membership.group.id
            # Get area
            if hasattr(self.registrant_id, "area_id") and self.registrant_id.area_id:
                self.area_id = self.registrant_id.area_id.id

    @api.onchange("household_id")
    def _onchange_household_id(self):
        """Get household members when household selected."""
        if self.household_id:
            members = self.env["spp.group.membership"].search(
                [
                    ("group", "=", self.household_id.id),
                ]
            )
            self.household_member_ids = members.mapped("individual")

    def action_view_previous_cases(self):
        """View previous cases for this registrant/household."""
        self.ensure_one()
        domain = [("id", "in", self.previous_case_ids.ids)]
        return {
            "type": "ir.actions.act_window",
            "name": "Previous Cases",
            "res_model": "spp.case",
            "view_mode": "tree,form,kanban",
            "domain": domain,
            "context": {"create": False},
        }
