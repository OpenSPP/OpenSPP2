# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class Session(models.Model):
    _name = "spp.session"
    _description = "Session"
    _inherit = ["mail.thread"]
    _order = "date desc"

    name = fields.Char(required=True, tracking=True)
    session_type_id = fields.Many2one(
        "spp.session.type",
        required=True,
        ondelete="restrict",
        string="Session Type",
        tracking=True,
    )

    date = fields.Date(required=True, default=fields.Date.today, tracking=True)
    start_time = fields.Float()
    end_time = fields.Float()
    duration_hours = fields.Float(compute="_compute_duration", store=True, string="Duration (Hours)")

    facilitator_id = fields.Many2one(
        "res.users",
        required=True,
        ondelete="restrict",
        string="Facilitator",
        tracking=True,
    )
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
    track_topics = fields.Boolean(related="session_type_id.track_topics")
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
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, ondelete="restrict")

    @api.depends("start_time", "end_time")
    def _compute_duration(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                rec.duration_hours = max(0.0, rec.end_time - rec.start_time)
            else:
                rec.duration_hours = 0.0

    @api.constrains("start_time", "end_time")
    def _check_time_range(self):
        for rec in self:
            if rec.start_time and rec.end_time and rec.end_time < rec.start_time:
                raise ValidationError(_("End time must be after start time."))

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

    _VALID_TRANSITIONS = {
        "scheduled": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }

    def write(self, vals):
        if "state" in vals:
            new_state = vals["state"]
            for rec in self:
                valid = self._VALID_TRANSITIONS.get(rec.state, set())
                if new_state not in valid:
                    raise UserError(
                        _(
                            "Cannot transition session from '%(current)s' to '%(target)s'.",
                            current=rec.state,
                            target=new_state,
                        )
                    )
        return super().write(vals)

    def action_start(self):
        for rec in self:
            if rec.state != "scheduled":
                raise UserError(_("Only scheduled sessions can be started."))
            _logger.info("Session id=%s transitioning from scheduled to in_progress.", rec.id)
            rec.state = "in_progress"

    def action_complete(self):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only sessions in progress can be completed."))
            _logger.info("Session id=%s transitioning from in_progress to completed.", rec.id)
            rec.state = "completed"

    def action_cancel(self):
        for rec in self:
            if rec.state not in ("scheduled", "in_progress"):
                raise UserError(_("Only scheduled or in-progress sessions can be cancelled."))
            _logger.info("Session id=%s transitioning from %s to cancelled.", rec.id, rec.state)
            rec.state = "cancelled"
