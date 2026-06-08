# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SessionAttendance(models.Model):
    _name = "spp.session.attendance"
    _description = "Session Attendance"
    _rec_name = "participant_id"

    session_id = fields.Many2one("spp.session", required=True, ondelete="cascade", string="Session")
    participant_id = fields.Many2one("res.partner", required=True, ondelete="restrict", string="Participant")

    is_attended = fields.Boolean()
    attendance_time = fields.Datetime(string="Time of Attendance")

    is_excused = fields.Boolean()
    excuse_reason = fields.Char()

    notes = fields.Text()

    # Computed from session
    session_date = fields.Date(related="session_id.date", store=True, string="Session Date")
    session_type_id = fields.Many2one(related="session_id.session_type_id", store=True, string="Session Type")

    _unique_participant_session = models.Constraint(
        "unique(session_id, participant_id)",
        "A participant can only have one attendance record per session.",
    )
