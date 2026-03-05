# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Extension for Session Integration.

Links cases to session attendance for tracking compliance
with required training or group sessions.
"""

from odoo import api, fields, models


class Case(models.Model):
    """Extension of spp.case to include session tracking."""

    _inherit = "spp.case"

    session_ids = fields.Many2many(
        comodel_name="spp.session",
        relation="case_session_rel",
        column1="case_id",
        column2="session_id",
        string="Required Sessions",
        help="Sessions the client is expected to attend as part of this case",
    )

    session_attendance_ids = fields.One2many(
        comodel_name="spp.session.attendance",
        compute="_compute_session_attendance",
        string="Session Attendance",
    )

    session_count = fields.Integer(
        compute="_compute_session_stats",
        string="Session Count",
    )

    session_attendance_rate = fields.Float(
        compute="_compute_session_stats",
        string="Attendance Rate (%)",
        help="Percentage of expected sessions attended",
    )

    session_compliance = fields.Selection(
        selection=[
            ("compliant", "Compliant"),
            ("partial", "Partial"),
            ("non_compliant", "Non-Compliant"),
            ("not_applicable", "N/A"),
        ],
        compute="_compute_session_stats",
        string="Session Compliance",
    )

    @api.depends("partner_id", "session_ids")
    def _compute_session_attendance(self):
        """Get attendance records for the case client in linked sessions."""
        Attendance = self.env["spp.session.attendance"]
        for case in self:
            if case.partner_id and case.session_ids:
                case.session_attendance_ids = Attendance.search(
                    [
                        ("participant_id", "=", case.partner_id.id),
                        ("session_id", "in", case.session_ids.ids),
                    ]
                )
            else:
                case.session_attendance_ids = Attendance

    @api.depends("session_ids", "partner_id")
    def _compute_session_stats(self):
        """Compute session attendance statistics."""
        Attendance = self.env["spp.session.attendance"]
        for case in self:
            if not case.session_ids:
                case.session_count = 0
                case.session_attendance_rate = 0.0
                case.session_compliance = "not_applicable"
                continue

            case.session_count = len(case.session_ids)

            # Get attendance for this client in required sessions
            attendance = Attendance.search(
                [
                    ("participant_id", "=", case.partner_id.id),
                    ("session_id", "in", case.session_ids.ids),
                ]
            )

            attended = len(attendance.filtered(lambda a: a.is_attended))
            total = len(case.session_ids)

            if total > 0:
                rate = (attended / total) * 100
                case.session_attendance_rate = rate

                if rate >= 80:
                    case.session_compliance = "compliant"
                elif rate >= 50:
                    case.session_compliance = "partial"
                else:
                    case.session_compliance = "non_compliant"
            else:
                case.session_attendance_rate = 0.0
                case.session_compliance = "not_applicable"

    def action_view_sessions(self):
        """Open sessions linked to this case."""
        self.ensure_one()
        return {
            "name": "Case Sessions",
            "type": "ir.actions.act_window",
            "res_model": "spp.session",
            "view_mode": "list,form",
            "domain": [("id", "in", self.session_ids.ids)],
            "context": {
                "default_case_ids": [fields.Command.link(self.id)],
                "default_expected_participant_ids": [fields.Command.link(self.partner_id.id)],
            },
        }
