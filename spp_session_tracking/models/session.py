# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class Session(models.Model):
    _name = "spp.session"
    _description = "Session"
    _inherit = ["mail.thread"]
    _order = "date desc"

    name = fields.Char(required=True, tracking=True)
    session_type_id = fields.Many2one("spp.session.type", required=True, string="Session Type", tracking=True)

    date = fields.Date(required=True, default=fields.Date.today, tracking=True)
    start_time = fields.Float()
    end_time = fields.Float()
    duration_hours = fields.Float(compute="_compute_duration", store=True, string="Duration (Hours)")

    facilitator_id = fields.Many2one("res.users", required=True, string="Facilitator", tracking=True)
    co_facilitator_ids = fields.Many2many(
        "res.users",
        "session_co_facilitator_rel",
        "session_id",
        "user_id",
        string="Co-Facilitators",
    )

    location = fields.Char()
    area_id = fields.Many2one("spp.area", string="Area")

    # Topics covered (if tracking enabled)
    topic_ids = fields.Many2many(
        "spp.session.topic",
        "session_topic_rel",
        "session_id",
        "topic_id",
        string="Topics Covered",
    )

    # Participants
    expected_participant_ids = fields.Many2many(
        "res.partner",
        "session_expected_participant_rel",
        "session_id",
        "partner_id",
        string="Expected Participants",
    )
    max_participants = fields.Integer()

    # Attendance
    attendance_ids = fields.One2many("spp.session.attendance", "session_id", string="Attendance Records")
    attendance_count = fields.Integer(compute="_compute_attendance")
    attendance_rate = fields.Float(compute="_compute_attendance", string="Attendance Rate (%)")

    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
        tracking=True,
    )

    notes = fields.Text()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("start_time", "end_time")
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration_hours = rec.end_time - rec.start_time
            else:
                rec.duration_hours = 0.0

    @api.depends("attendance_ids", "attendance_ids.is_attended", "expected_participant_ids")
    def _compute_attendance(self):
        for rec in self:
            attended = len(rec.attendance_ids.filtered(lambda a: a.is_attended))
            rec.attendance_count = attended

            expected = len(rec.expected_participant_ids)
            if expected > 0:
                rec.attendance_rate = (attended / expected) * 100.0
            else:
                rec.attendance_rate = 0.0

    def action_start(self):
        self.state = "in_progress"

    def action_complete(self):
        self.state = "completed"

    def action_cancel(self):
        self.state = "cancelled"
