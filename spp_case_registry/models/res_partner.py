from odoo import api, fields, models


class ResPartnerCase(models.Model):
    _inherit = "res.partner"

    case_registrant_ids = fields.One2many(
        "spp.case",
        "registrant_id",
        string="Cases (as Registrant)",
    )
    case_household_ids = fields.One2many(
        "spp.case",
        "household_id",
        string="Cases (as Household)",
    )
    case_count = fields.Integer(
        compute="_compute_case_counts",
    )
    case_active_count = fields.Integer(
        compute="_compute_case_counts",
    )

    @api.depends("case_registrant_ids", "case_household_ids")
    def _compute_case_counts(self):
        for partner in self:
            cases = partner.case_registrant_ids | partner.case_household_ids
            partner.case_count = len(cases)
            partner.case_active_count = len(cases.filtered("is_active"))

    def action_view_cases(self):
        """View cases for this registrant."""
        domain = [
            "|",
            ("registrant_id", "=", self.id),
            ("household_id", "=", self.id),
        ]
        return {
            "type": "ir.actions.act_window",
            "name": "Cases",
            "res_model": "spp.case",
            "view_mode": "tree,form,kanban",
            "domain": domain,
            "context": {
                "default_registrant_id": self.id if not self.is_group else False,
                "default_household_id": self.id if self.is_group else False,
            },
        }
