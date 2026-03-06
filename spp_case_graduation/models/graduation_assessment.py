# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Graduation Assessment Extension for Case Integration.

Links graduation assessments back to cases.
"""

from odoo import fields, models


class GraduationAssessment(models.Model):
    """Extension of spp.graduation.assessment to link to cases."""

    _inherit = "spp.graduation.assessment"

    case_id = fields.Many2one(
        comodel_name="spp.case",
        string="Case",
        tracking=True,
        help="The case this graduation assessment is associated with",
    )
