# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # DRIMS Organization Fields
    is_drims_organization = fields.Boolean(
        string="DRIMS Organization",
        default=False,
        help="Flag to identify organizations participating in disaster response and DRIMS coordination",
    )
    drims_organization_role_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Organization Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:organization-roles')]",
        help="Role this organization plays in disaster response coordination (4W reporting: Who, What, Where, When)",
    )

    # DRIMS Personnel (deployed from this organization)
    drims_personnel_ids = fields.One2many(
        "spp.drims.personnel",
        "organization_id",
        string="Deployed Personnel",
    )
    drims_personnel_count = fields.Integer(
        string="Personnel Count",
        compute="_compute_drims_personnel_count",
        search="_search_drims_personnel_count",
    )

    def _compute_drims_personnel_count(self):
        for partner in self:
            partner.drims_personnel_count = len(partner.drims_personnel_ids)

    def _search_drims_personnel_count(self, operator, value):
        """Search method to filter by personnel count."""
        personnel_data = self.env["spp.drims.personnel"].read_group(
            domain=[],
            fields=["organization_id"],
            groupby=["organization_id"],
        )
        org_counts = {
            d["organization_id"][0]: d["organization_id_count"] for d in personnel_data if d["organization_id"]
        }

        if operator == ">" and value == 0:
            return [("id", "in", list(org_counts.keys()))]
        elif operator == "=" and value == 0:
            return [("id", "not in", list(org_counts.keys()))]
        else:
            matching_ids = [org_id for org_id, count in org_counts.items() if self._compare(count, operator, value)]
            return [("id", "in", matching_ids)]

    def _compare(self, count, operator, value):
        """Helper for search comparison."""
        import operator as op

        ops = {
            ">": op.gt,
            "<": op.lt,
            ">=": op.ge,
            "<=": op.le,
            "=": op.eq,
            "!=": op.ne,
        }
        return ops.get(operator, op.eq)(count, value)

    def action_view_drims_personnel(self):
        """Open personnel deployed from this organization."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Deployed Personnel",
            "res_model": "spp.drims.personnel",
            "view_mode": "list,form",
            "domain": [("organization_id", "=", self.id)],
            "context": {"default_organization_id": self.id},
        }
