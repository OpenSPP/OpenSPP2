from odoo import api, fields, models

ACTION_LABELS = {
    "created": "Created",
    "submitted": "Submitted for Approval",
    "approved": "Approved",
    "rejected": "Rejected",
    "revision_requested": "Revision Requested",
    "reset_to_draft": "Reset to Draft",
    "applied": "Changes Applied",
    "resubmitted": "Resubmitted for Review",
}


class SPPChangeRequestLog(models.Model):
    _name = "spp.change.request.log"
    _description = "Change Request Log"
    _order = "id desc"

    change_request_id = fields.Many2one(
        "spp.change.request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    action = fields.Selection(
        [
            ("created", "Created"),
            ("submitted", "Submitted for Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("revision_requested", "Revision Requested"),
            ("reset_to_draft", "Reset to Draft"),
            ("applied", "Changes Applied"),
            ("resubmitted", "Resubmitted for Review"),
        ],
        required=True,
    )
    action_label = fields.Char(
        compute="_compute_action_label",
        string="Action",
    )
    user_id = fields.Many2one(
        "res.users",
        string="By",
        default=lambda self: self.env.user,
        required=True,
    )
    notes = fields.Text()

    @api.depends("action")
    def _compute_action_label(self):
        for rec in self:
            rec.action_label = ACTION_LABELS.get(rec.action, rec.action)
