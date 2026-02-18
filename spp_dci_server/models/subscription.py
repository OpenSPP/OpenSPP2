# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Subscription model for event notifications with job_worker."""

import logging
import uuid
from datetime import UTC, datetime

import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..utils.url_validator import validate_callback_url

_logger = logging.getLogger(__name__)

# Default subscription limits
DEFAULT_MAX_SUBSCRIPTIONS_PER_SENDER = 100


class DCISubscription(models.Model):
    """Manage DCI event subscriptions with job_worker notifications.

    External systems can subscribe to events (registration, update, delete)
    for specific registry types. When events occur, notifications are
    queued and delivered via callback URLs.
    """

    _name = "spp.dci.subscription"
    _description = "DCI Event Subscription"
    _rec_name = "subscription_code"
    _order = "create_date desc"

    _subscription_code_uniq = models.Constraint(
        "UNIQUE(subscription_code)",
        "Subscription code must be unique",
    )

    # Subscription Identity
    subscription_code = fields.Char(
        required=True,
        index=True,
        default=lambda self: f"SUB-{uuid.uuid4().hex[:12].upper()}",
        string="Subscription Code",
        help="Unique identifier for this subscription",
    )
    name = fields.Char(
        compute="_compute_name",
        store=True,
        string="Name",
    )

    # Subscriber Information
    sender_id = fields.Many2one(
        "spp.dci.sender.registry",
        required=True,
        ondelete="cascade",
        string="Subscriber",
        help="DCI sender who created the subscription",
    )
    callback_uri = fields.Char(
        string="Callback URI",
        help="URL for notification delivery. If not provided, no callbacks will be sent.",
    )

    # Event Configuration - per SPDCI RegistryEventType
    event_type = fields.Selection(
        [
            ("registration", "Registration"),
            ("update", "Record Update"),
            ("delete", "Record Deletion"),
            ("birth", "Birth"),
            ("death", "Death"),
            ("marriage", "Marriage"),
            ("divorce", "Divorce"),
            ("adoption", "Adoption"),
            ("correction", "Correction"),
        ],
        required=True,
        string="Event Type",
        help="Type of events to receive notifications for (per SPDCI RegistryEventType)",
    )
    reg_type = fields.Selection(
        [
            ("SOCIAL_REGISTRY", "Social Registry"),
            ("DR", "Disability Registry"),
            ("FR", "Farmer Registry"),
            ("IBR", "Integrated Beneficiary Registry"),
        ],
        required=True,
        string="Registry Type",
    )

    # Filtering
    filter_expression = fields.Text(
        string="Filter Expression",
        help="Optional DCI expression to filter which events trigger notifications",
    )

    # Subscription State
    active = fields.Boolean(
        default=True,
        string="Active",
    )
    expires = fields.Datetime(
        string="Expires",
        help="When this subscription expires (empty = no expiry)",
    )
    state = fields.Selection(
        [
            ("pending", "Pending Confirmation"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
            ("error", "Error"),
        ],
        default="pending",
        string="State",
    )

    # Statistics
    notification_count = fields.Integer(
        compute="_compute_stats",
        string="Notifications Sent",
    )
    last_notification = fields.Datetime(
        string="Last Notification",
    )
    failed_count = fields.Integer(
        default=0,
        string="Failed Notifications",
    )

    # Original Request
    original_message_id = fields.Char(
        string="Original Message ID",
        help="DCI message_id from subscribe request",
    )
    original_transaction_id = fields.Char(
        string="Original Transaction ID",
        help="DCI transaction_id from subscribe request",
    )

    @api.depends("subscription_code", "sender_id", "event_type")
    def _compute_name(self):
        for record in self:
            sender_name = record.sender_id.name if record.sender_id else "Unknown"
            record.name = f"{record.subscription_code} - {sender_name} ({record.event_type})"

    def _compute_stats(self):
        """Compute notification statistics using batch query.

        Uses read_group for O(1) query instead of O(n) N+1 pattern.
        """
        # Check if notification log model exists
        if "spp.dci.notification.log" not in self.env:
            for record in self:
                record.notification_count = 0
            return

        # Batch query: single SQL query for all records
        data = self.env["spp.dci.notification.log"].read_group(
            domain=[("subscription_id", "in", self.ids)],
            fields=["subscription_id"],
            groupby=["subscription_id"],
        )
        counts = {d["subscription_id"][0]: d["subscription_id_count"] for d in data}

        for record in self:
            record.notification_count = counts.get(record.id, 0)

    def action_view_notifications(self):
        """Open list of notification logs for this subscription."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Notifications"),
            "res_model": "spp.dci.notification.log",
            "view_mode": "list,form",
            "domain": [("subscription_id", "=", self.id)],
            "context": {"default_subscription_id": self.id},
        }

    @api.model
    def check_expired_subscriptions(self):
        """Cron job to deactivate expired subscriptions."""
        expired = self.search(
            [
                ("expires", "!=", False),
                ("expires", "<", fields.Datetime.now()),
                ("state", "=", "active"),
            ]
        )
        expired.write({"state": "expired", "active": False})
        _logger.info("Deactivated %d expired subscriptions", len(expired))
        return True

    def notify_event(self, event_type: str, records: list, reg_type: str):
        """Queue notifications for matching subscriptions.

        Called when a registry event occurs (registration, update, delete).

        Args:
            event_type: Type of event (registration, update, delete)
            records: List of affected record data dicts
            reg_type: Registry type (SOCIAL_REGISTRY, DR, etc.)
        """
        # Find matching active subscriptions
        domain = [
            ("event_type", "=", event_type),
            ("reg_type", "=", reg_type),
            ("active", "=", True),
            ("state", "=", "active"),
            "|",
            ("expires", "=", False),
            ("expires", ">", fields.Datetime.now()),
        ]
        subscriptions = self.search(domain)

        _logger.info(
            "Found %d subscriptions for event %s/%s",
            len(subscriptions),
            reg_type,
            event_type,
        )

        for sub in subscriptions:
            # Queue notification job for each subscription
            sub.with_delay(
                channel="dci",
                timeout=60,
                description=f"DCI Notify {sub.subscription_code}",
            )._send_notification(event_type, records)

    def _send_notification(self, event_type: str, records: list):
        """Send notification to subscriber. Called by job_worker.

        Args:
            event_type: Event type
            records: List of record data dicts
        """
        self.ensure_one()

        # Skip if no callback URI configured
        if not self.callback_uri:
            _logger.info(
                "Skipping notification for subscription %s - no callback URI configured",
                self.subscription_code,
            )
            return

        # SECURITY: Validate callback URL to prevent SSRF
        try:
            config = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
            allow_http = config.get_param("dci.allow_http_callbacks", "false").lower() == "true"
            skip_ip_check = config.get_param("dci.allow_internal_callback_ips", "false").lower() == "true"
            validate_callback_url(
                self.callback_uri,
                require_https=not allow_http,
                skip_ip_check=skip_ip_check,
            )
        except ValidationError as e:
            _logger.error(
                "Notification URL validation failed for subscription %s: %s",
                self.subscription_code,
                str(e),
            )
            self.failed_count += 1
            if self.failed_count >= 10:
                self.state = "error"
                self.active = False
            return

        # Create notification log entry first to get notification_id
        NotificationLog = self.env["spp.dci.notification.log"]
        log_entry = NotificationLog.create(
            {
                "subscription_id": self.id,
                "event_type": event_type,
                "record_count": len(records),
                "status": "sent",  # Will be updated on failure
            }
        )

        try:
            # Build notification message with notification_id
            notification_data = self._build_notification(event_type, records, log_entry.notification_id)

            # Send with timeout (reduced to 10s per security review)
            resp = requests.post(
                self.callback_uri,
                json=notification_data,
                timeout=10,
                headers={
                    "Content-Type": "application/json",
                    "X-DCI-Subscription-Code": self.subscription_code,
                    "X-DCI-Event-Type": event_type,
                    "X-DCI-Notification-ID": log_entry.notification_id,
                },
            )
            resp.raise_for_status()

            self.last_notification = fields.Datetime.now()
            log_entry.status = "sent"
            _logger.info(
                "Notification %s sent for subscription %s, event %s",
                log_entry.notification_id,
                self.subscription_code,
                event_type,
            )

        except requests.exceptions.RequestException as e:
            self.failed_count += 1
            log_entry.write(
                {
                    "status": "failed",
                    "error_message": str(e),
                }
            )
            _logger.error(
                "Notification %s failed for subscription %s: %s",
                log_entry.notification_id,
                self.subscription_code,
                str(e),
            )

            # Deactivate subscription after too many failures
            if self.failed_count >= 10:
                self.state = "error"
                self.active = False
                _logger.warning(
                    "Subscription %s deactivated after %d failures",
                    self.subscription_code,
                    self.failed_count,
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to enforce subscription limits and validate URLs.

        SECURITY: Prevents DoS via unlimited subscription creation.
        """
        for vals in vals_list:
            sender_id = vals.get("sender_id")
            if sender_id:
                # Check subscription limit for this sender
                max_subscriptions = int(
                    self.env["ir.config_parameter"]  # nosemgrep: odoo-sudo-without-context
                    .sudo()
                    .get_param(
                        "dci.max_subscriptions_per_sender",
                        DEFAULT_MAX_SUBSCRIPTIONS_PER_SENDER,
                    )
                )
                current_count = self.search_count(
                    [
                        ("sender_id", "=", sender_id),
                        ("state", "in", ("pending", "active")),
                    ]
                )
                if current_count >= max_subscriptions:
                    raise ValidationError(
                        _("Subscription limit reached. Maximum %d active subscriptions per sender.") % max_subscriptions
                    )

            # Validate callback URL before storing
            callback_uri = vals.get("callback_uri")
            if callback_uri:
                config = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
                allow_http = config.get_param("dci.allow_http_callbacks", "false").lower() == "true"
                skip_ip_check = config.get_param("dci.allow_internal_callback_ips", "false").lower() == "true"
                validate_callback_url(
                    callback_uri,
                    require_https=not allow_http,
                    skip_ip_check=skip_ip_check,
                )

        return super().create(vals_list)

    def _build_notification(self, event_type: str, records: list, notification_id: str = None) -> dict:
        """Build DCI notification envelope.

        Args:
            event_type: Event type
            records: List of record data dicts
            notification_id: Optional notification ID for receipt tracking

        Returns:
            DCI notification envelope
        """
        from ..services.response_signer import DCIResponseSigner

        # nosemgrep: odoo-sudo-without-context
        sender_id = self.env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")
        sender_uri = self.sender_id.sender_id if self.sender_id else "unknown"

        header = {
            "version": "1.0.0",
            "message_id": str(uuid.uuid4()),
            "message_ts": datetime.now(UTC).isoformat(),
            "action": "notify",
            "sender_id": sender_id,
            "receiver_id": sender_uri,
            "total_count": len(records),
        }

        # Include notification_id in header if provided (for receipt tracking)
        if notification_id:
            header["notification_id"] = notification_id

        message = {
            "subscription_code": self.subscription_code,
            "notify_event": [
                {
                    "event_id": str(uuid.uuid4()),
                    "event_ts": datetime.now(UTC).isoformat(),
                    "event_type": event_type.upper(),
                    "reg_type": self.reg_type,
                    "event_data": records,
                }
            ],
        }

        # Include notification_id in message as well for easier access
        if notification_id:
            message["notification_id"] = notification_id

        # Sign the envelope
        try:
            signer = DCIResponseSigner(self.env)
            signature = signer.sign_envelope(header, message)
        except Exception as e:
            _logger.warning("Failed to sign notification envelope: %s. Sending unsigned.", str(e))
            signature = ""

        return {
            "signature": signature,
            "header": header,
            "message": message,
        }

    def action_confirm(self):
        """Confirm pending subscription."""
        for record in self:
            if record.state == "pending":
                record.state = "active"

    def action_cancel(self):
        """Cancel subscription."""
        for record in self:
            record.state = "cancelled"
            record.active = False

    def action_reactivate(self):
        """Reactivate cancelled or expired subscription."""
        for record in self:
            if record.state in ("cancelled", "expired", "error"):
                record.state = "active"
                record.active = True
                record.failed_count = 0


class DCINotificationLog(models.Model):
    """Log of sent notifications for audit trail and receipt tracking."""

    _name = "spp.dci.notification.log"
    _description = "DCI Notification Log"
    _order = "create_date desc"

    _notification_id_uniq = models.Constraint(
        "UNIQUE(notification_id)",
        "Notification ID must be unique",
    )

    # Notification Identity
    notification_id = fields.Char(
        index=True,
        default=lambda self: f"NOTIF-{uuid.uuid4().hex[:12].upper()}",
        string="Notification ID",
        help="Unique identifier for this notification (used for receipt matching)",
    )

    subscription_id = fields.Many2one(
        "spp.dci.subscription",
        required=True,
        ondelete="cascade",
        string="Subscription",
    )
    event_type = fields.Char(string="Event Type")
    record_count = fields.Integer(string="Record Count")
    status = fields.Selection(
        [
            ("sent", "Sent"),
            ("failed", "Failed"),
            ("received", "Receipt Received"),
        ],
        string="Status",
    )
    error_message = fields.Text(string="Error Message")
    sent_at = fields.Datetime(
        default=fields.Datetime.now,
        string="Sent At",
    )

    # Receipt tracking fields
    receipt_received = fields.Boolean(
        default=False,
        string="Receipt Received",
        help="Whether the external system confirmed receipt of this notification",
    )
    receipt_timestamp = fields.Datetime(
        string="Receipt Timestamp",
        help="When the receipt was received",
    )
    receipt_transaction_id = fields.Char(
        string="Receipt Transaction ID",
        help="Transaction ID from the receipt request",
    )
    receipt_processed_at = fields.Datetime(
        string="Receipt Processed At",
        help="When the external system processed the notification",
    )
    receipt_error = fields.Text(
        string="Receipt Error",
        help="Error message from receipt if processing failed",
    )
