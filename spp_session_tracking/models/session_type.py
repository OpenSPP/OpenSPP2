# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SessionType(models.Model):
    _name = "spp.session.type"
    _description = "Session Type"

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()
    active = fields.Boolean(default=True)

    frequency = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("biweekly", "Bi-weekly"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("one_time", "One-time"),
        ],
        default="monthly",
    )

    required_attendance_pct = fields.Float(
        default=80.0,
        help="Minimum attendance percentage required for compliance",
    )
    duration_hours = fields.Float(default=2.0)

    track_topics = fields.Boolean(
        default=False,
        help="Track which topics are covered in each session",
    )
    topic_ids = fields.One2many("spp.session.topic", "session_type_id", string="Topics")

    session_count = fields.Integer(compute="_compute_counts", string="Number of Sessions")

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("topic_ids")
    def _compute_counts(self):
        for rec in self:
            rec.session_count = self.env["spp.session"].search_count([("session_type_id", "=", rec.id)])

    def action_view_sessions(self):
        """Open view with sessions of this type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Sessions - {self.name}",
            "res_model": "spp.session",
            "view_mode": "tree,form,calendar,kanban",
            "domain": [("session_type_id", "=", self.id)],
            "context": {"default_session_type_id": self.id},
        }
