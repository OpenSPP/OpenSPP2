# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Session Extension for Case Integration.

Links sessions back to cases for reference.
"""

from odoo import fields, models


class Session(models.Model):
    """Extension of spp.session to link back to cases."""

    _inherit = "spp.session"

    case_ids = fields.Many2many(
        comodel_name="spp.case",
        relation="case_session_rel",
        column1="session_id",
        column2="case_id",
        string="Related Cases",
        help="Cases that require attendance at this session",
    )

    case_count = fields.Integer(
        compute="_compute_case_count",
        string="Case Count",
    )

    def _compute_case_count(self):
        """Count related cases."""
        for session in self:
            session.case_count = len(session.case_ids)

    def action_view_cases(self):
        """Open cases linked to this session."""
        self.ensure_one()
        return {
            "name": "Related Cases",
            "type": "ir.actions.act_window",
            "res_model": "spp.case",
            "view_mode": "list,form",
            "domain": [("id", "in", self.case_ids.ids)],
        }
