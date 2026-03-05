from odoo import fields, models


class GraduationCriteria(models.Model):
    _name = "spp.graduation.criteria"
    _description = "Graduation Criteria"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char()
    pathway_id = fields.Many2one("spp.graduation.pathway", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)

    description = fields.Text()

    weight = fields.Float(
        default=1.0,
        help="Weight in overall score calculation",
    )

    assessment_method = fields.Selection(
        [
            ("self_report", "Self Report"),
            ("verification", "Verification Required"),
            ("computed", "Computed from Data"),
            ("observation", "Field Observation"),
        ],
        default="verification",
    )

    is_required = fields.Boolean(
        default=False,
        help="If required, must be met regardless of overall score",
    )

    active = fields.Boolean(default=True)
