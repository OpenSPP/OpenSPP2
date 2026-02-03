# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Consent History for audit trail and accountability.

Tracks all changes to consent records for audit trail and accountability
(e.g., GDPR Article 7, Kenya DPA, POPIA, LGPD requirements).
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ConsentHistory(models.Model):
    """
    Track all modifications to consent records.

    Required for GDPR Article 7(1) accountability - organizations must be able
    to demonstrate that consent was obtained and track any changes over time.
    """

    _name = "spp.consent.history"
    _description = "Consent Version History"
    _order = "consent_id, version desc"

    consent_id = fields.Many2one(
        "spp.consent",
        required=True,
        ondelete="cascade",
        index=True,
    )

    version = fields.Integer(
        required=True,
        help="Sequential version number for this consent",
    )

    # What happened
    action = fields.Selection(
        [
            ("create", "Created"),
            ("request", "Requested"),
            ("give", "Given"),
            ("renew", "Renewed"),
            ("refuse", "Refused"),
            ("withdraw", "Withdrawn"),
            ("expire", "Expired"),
            ("invalidate", "Invalidated"),
            ("modify", "Modified"),
        ],
        required=True,
    )

    # Status transition
    previous_status = fields.Char(help="Status before this action")
    new_status = fields.Char(help="Status after this action")

    # What changed
    previous_values = fields.Json(
        help="JSON of field values before the change",
    )
    new_values = fields.Json(
        help="JSON of field values after the change",
    )
    changed_fields = fields.Char(
        help="Comma-separated list of changed field names",
    )

    # Who made the change
    changed_by_id = fields.Many2one(
        "res.users",
        string="Changed By",
        required=True,
        default=lambda self: self.env.user,
    )
    indicated_by_id = fields.Many2one(
        "res.partner",
        string="Indicated By",
        help="Data subject or delegate who indicated the action",
    )

    # When
    changed_date = fields.Datetime(
        required=True,
        default=fields.Datetime.now,
    )

    # For electronic consent - track origin
    ip_address = fields.Char(
        help="IP address if consent was given/modified electronically",
    )
    user_agent = fields.Char(
        help="Browser/client user agent if electronic",
    )
    channel = fields.Selection(
        [
            ("web", "Web Portal"),
            ("mobile", "Mobile App"),
            ("api", "API"),
            ("paper", "Paper Form"),
            ("verbal", "Verbal"),
            ("other", "Other"),
        ],
        help="Channel through which action was taken",
    )

    # Additional context
    reason = fields.Text(
        help="Reason for the change (especially for withdrawal)",
    )
    notes = fields.Text(
        help="Additional notes about this action",
    )

    # Evidence reference
    evidence_reference = fields.Char(
        help="Reference to evidence document if applicable",
    )

    _unique_consent_version = models.Constraint("UNIQUE(consent_id, version)", "Version must be unique per consent")

    @api.model
    def record_action(
        self,
        consent,
        action,
        previous_status=None,
        new_status=None,
        previous_values=None,
        new_values=None,
        reason=None,
        indicated_by=None,
        ip_address=None,
        user_agent=None,
        channel=None,
    ):
        """
        Record a consent action in the history.

        Args:
            consent: spp.consent record
            action: Type of action
            previous_status: Status before action
            new_status: Status after action
            previous_values: Dict of previous field values
            new_values: Dict of new field values
            reason: Optional reason for the action
            indicated_by: Partner who indicated the action
            ip_address: IP address for electronic actions
            user_agent: User agent for electronic actions
            channel: Channel through which action was taken

        Returns:
            spp.consent.history record
        """
        # Get next version number
        last_history = self.search(
            [("consent_id", "=", consent.id)],
            order="version desc",
            limit=1,
        )
        next_version = (last_history.version + 1) if last_history else 1

        # Determine changed fields
        changed_fields = []
        if previous_values and new_values:
            changed_fields = [k for k in new_values if previous_values.get(k) != new_values.get(k)]

        return self.create(
            {
                "consent_id": consent.id,
                "version": next_version,
                "action": action,
                "previous_status": previous_status,
                "new_status": new_status,
                "previous_values": previous_values,
                "new_values": new_values,
                "changed_fields": ",".join(changed_fields) if changed_fields else None,
                "changed_by_id": self.env.user.id,
                "indicated_by_id": indicated_by.id if indicated_by else None,
                "changed_date": fields.Datetime.now(),
                "reason": reason,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "channel": channel,
            }
        )

    def name_get(self):
        """Display as 'Action @ Date'"""
        result = []
        for rec in self:
            action_label = dict(rec._fields["action"].selection).get(rec.action, rec.action)
            date_str = rec.changed_date.strftime("%Y-%m-%d %H:%M") if rec.changed_date else ""
            result.append((rec.id, f"{action_label} @ {date_str}"))
        return result
