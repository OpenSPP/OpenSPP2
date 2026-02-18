"""Wizard for scheduling version activation with conflict detection."""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ScheduleVersionWizard(models.TransientModel):
    """Wizard for scheduling version activation.

    Provides a user-friendly interface for:
    - Choosing between immediate activation and scheduled activation
    - Selecting an activation date
    - Detecting conflicts with other scheduled versions
    - Adding change summary for audit trail
    """

    _name = "spp.artifact.version.schedule.wizard"
    _description = "Schedule Version Activation"

    # Version reference
    version_id = fields.Many2one(
        comodel_name="spp.artifact.version",
        string="Version",
        required=True,
        ondelete="cascade",
    )
    artifact_name = fields.Char(
        related="version_id.artifact_name",
        string="Artifact",
        readonly=True,
    )
    version_number = fields.Integer(
        related="version_id.version",
        string="Version",
        readonly=True,
    )

    # Timing selection
    activation_mode = fields.Selection(
        selection=[
            ("immediate", "Activate Immediately"),
            ("scheduled", "Schedule for a specific date"),
        ],
        string="Activation Mode",
        default="scheduled",
        required=True,
        help="Choose when to activate this version",
    )
    effective_date = fields.Date(
        string="Activation Date",
        default=lambda self: fields.Date.today() + timedelta(days=1),
        help="Date when this version becomes active",
    )

    # Change summary
    change_summary = fields.Text(
        related="version_id.change_summary",
        string="Change Summary",
        readonly=False,
        required=True,
        help="Description of what changed in this version (for audit trail)",
    )

    # Conflict detection (computed)
    has_conflict = fields.Boolean(
        compute="_compute_conflict_info",
        string="Has Conflict",
    )
    conflict_severity = fields.Selection(
        selection=[
            ("warning", "Warning"),
            ("error", "Error"),
        ],
        compute="_compute_conflict_info",
        string="Conflict Severity",
    )
    conflict_message = fields.Text(
        compute="_compute_conflict_info",
        string="Conflict Message",
    )

    @api.depends("effective_date", "version_id")
    def _compute_conflict_info(self):
        """Detect conflicts with other scheduled versions."""
        for record in self:
            if not record.version_id or not record.effective_date:
                record.has_conflict = False
                record.conflict_severity = False
                record.conflict_message = ""
                continue

            # Find other scheduled versions for the same artifact
            scheduled = self.env["spp.artifact.version"].search(
                [
                    ("model", "=", record.version_id.model),
                    ("res_id", "=", record.version_id.res_id),
                    ("state", "=", "scheduled"),
                    ("id", "!=", record.version_id.id),
                ]
            )

            if not scheduled:
                record.has_conflict = False
                record.conflict_severity = False
                record.conflict_message = ""
            elif any(s.effective_date == record.effective_date for s in scheduled):
                # Same date conflict - error
                record.has_conflict = True
                record.conflict_severity = "error"
                existing = scheduled.filtered(lambda s, _record=record: s.effective_date == _record.effective_date)[0]
                record.conflict_message = _(
                    "Version v%(version)s is already scheduled for %(date)s. "
                    "Only one version can be scheduled per date."
                ) % {
                    "version": existing.version,
                    "date": record.effective_date,
                }
            else:
                # Other scheduled versions exist - warning
                record.has_conflict = True
                record.conflict_severity = "warning"
                record.conflict_message = _(
                    "Other versions are scheduled: %(versions)s. Your version will activate in sequence."
                ) % {
                    "versions": ", ".join(
                        f"v{s.version} ({s.effective_date})" for s in scheduled.sorted("effective_date")
                    ),
                }

    def action_schedule(self):
        """Schedule the version for the selected date.

        Returns:
            dict: Window close action
        """
        self.ensure_one()

        if self.conflict_severity == "error":
            raise ValidationError(self.conflict_message)

        # Update change summary if modified
        if self.change_summary != self.version_id.change_summary:
            self.version_id.change_summary = self.change_summary

        self.version_id.action_schedule(self.effective_date)
        return {"type": "ir.actions.act_window_close"}

    def action_activate_now(self):
        """Activate the version immediately.

        Returns:
            dict: Window close action
        """
        self.ensure_one()

        # Update change summary if modified
        if self.change_summary != self.version_id.change_summary:
            self.version_id.change_summary = self.change_summary

        self.version_id.action_activate_now()
        return {"type": "ir.actions.act_window_close"}
