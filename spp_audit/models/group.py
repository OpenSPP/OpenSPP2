from odoo import api, fields, models


class OpenSPPGroup(models.Model):
    _inherit = "res.partner"

    group_member_names = fields.Text("Group Member Names", compute="_compute_group_member_names")

    @api.depends("group_membership_ids")
    def _compute_group_member_names(self):
        for rec in self:
            member_names = []
            for membership in rec.group_membership_ids:
                member_names.append(membership.individual.name)

            rec.group_member_names = ", ".join(member_names)
