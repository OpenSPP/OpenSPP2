from odoo import api, fields, models


class GraduationPathway(models.Model):
    _name = "spp.graduation.pathway"
    _description = "Graduation Pathway"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    is_positive_exit = fields.Boolean(
        default=True,
        help="Positive exit (graduation) vs negative exit (removed)",
    )

    is_requires_assessment = fields.Boolean(default=True)
    is_requires_approval = fields.Boolean(default=True)

    criteria_ids = fields.One2many("spp.graduation.criteria", "pathway_id", string="Criteria")

    post_graduation_monitoring_months = fields.Integer(
        default=12,
        help="Months of monitoring after graduation",
    )

    criteria_count = fields.Integer(
        string="Criteria Count",
        compute="_compute_criteria_count",
        store=True,
        default=0,
    )

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("criteria_ids")
    def _compute_criteria_count(self):
        for pathway in self:
            pathway.criteria_count = len(pathway.criteria_ids)
