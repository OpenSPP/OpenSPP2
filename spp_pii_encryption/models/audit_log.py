import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PIIAuditLog(models.Model):
    """Audit log for PII field access and modifications."""

    _name = "spp.pii.audit.log"
    _description = "PII Audit Log"
    _order = "create_date desc"
    _rec_name = "display_name"

    model_name = fields.Char(
        string="Model",
        required=True,
        readonly=True,
        index=True,
    )
    record_id = fields.Integer(
        string="Record ID",
        required=True,
        readonly=True,
        index=True,
    )
    field_name = fields.Char(
        string="Field",
        required=True,
        readonly=True,
        index=True,
    )
    action = fields.Selection(
        selection=[
            ("reveal", "Revealed"),
            ("export", "Exported"),
            ("decrypt", "Decrypted"),
            ("modify", "Modified"),
            ("delete", "Deleted"),
        ],
        string="Action",
        required=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        required=True,
        readonly=True,
        default=lambda self: self.env.user.id,
        index=True,
    )
    ip_address = fields.Char(
        string="IP Address",
        readonly=True,
    )
    user_agent = fields.Char(
        string="User Agent",
        readonly=True,
    )
    reason = fields.Text(
        string="Reason",
        readonly=True,
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("model_name", "field_name", "action")
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.action} {record.model_name}.{record.field_name}"

    @api.model
    def log_field_access(self, model_name, record_id, field_name, action, reason=None):
        """Log a PII field access event.

        Args:
            model_name: The model being accessed
            record_id: The record ID being accessed
            field_name: The field being accessed
            action: The type of access (reveal, export, decrypt, modify, delete)
            reason: Optional reason for the access

        Returns:
            The created audit log record
        """
        # Get IP and user agent from request if available
        ip_address = None
        user_agent = None

        try:
            from odoo.http import request

            if request:
                ip_address = request.httprequest.remote_addr
                user_agent = request.httprequest.user_agent.string[:500] if request.httprequest.user_agent else None
        except Exception:
            pass

        # Always log with sudo() so PII access audit trails are recorded
        # even if the caller has limited write access on the audit model.
        return self.sudo().create(  # nosemgrep: odoo-sudo-without-context - System-level PII access audit log creation.
            {
                "model_name": model_name,
                "record_id": record_id,
                "field_name": field_name,
                "action": action,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "reason": reason,
            }
        )

    @api.model
    def get_access_history(self, model_name, record_id, limit=100):
        """Get access history for a specific record.

        Args:
            model_name: The model name
            record_id: The record ID
            limit: Maximum number of records to return

        Returns:
            Recordset of audit log entries
        """
        return self.search(
            [
                ("model_name", "=", model_name),
                ("record_id", "=", record_id),
            ],
            limit=limit,
        )

    @api.model
    def get_user_access_history(self, user_id=None, days=30, limit=1000):
        """Get access history for a user.

        Args:
            user_id: The user ID (defaults to current user)
            days: Number of days to look back
            limit: Maximum number of records to return

        Returns:
            Recordset of audit log entries
        """
        from datetime import datetime, timedelta

        if user_id is None:
            user_id = self.env.user.id

        cutoff = datetime.now() - timedelta(days=days)

        return self.search(
            [
                ("user_id", "=", user_id),
                ("create_date", ">=", cutoff.strftime("%Y-%m-%d %H:%M:%S")),
            ],
            limit=limit,
        )
