# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class Alert(models.Model):
    """Generic alert model for monitoring thresholds, expiries, and deadlines.

    This base alert model provides a flexible framework for creating and managing
    alerts across OpenSPP modules. Consumer modules (like spp_drims) extend this
    model to add domain-specific fields and behaviors.

    Key features:
    - Type-based alert classification via vocabulary
    - Priority-based escalation (low/medium/high/critical)
    - State machine (active/acknowledged/resolved)
    - Threshold and deadline tracking
    - Resolution workflow with audit trail
    """

    _name = "spp.alert"
    _description = "Alert"
    _inherit = ["mail.thread"]
    _order = "priority desc, create_date desc"
    _rec_name = "reference"

    reference = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        help="Unique alert reference number, auto-generated from sequence",
    )

    alert_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Alert Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:alerts')]",
        required=True,
        tracking=True,
        index=True,
        help="Type of alert from alert types vocabulary",
    )

    alert_type = fields.Char(
        related="alert_type_id.code",
        store=True,
        string="Alert Type Code",
        help="Code of the alert type for easy filtering",
    )

    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Priority",
        default="medium",
        required=True,
        tracking=True,
        index=True,
        help="Priority level of the alert",
    )

    state = fields.Selection(
        [
            ("active", "Active"),
            ("acknowledged", "Acknowledged"),
            ("resolved", "Resolved"),
        ],
        string="State",
        default="active",
        required=True,
        tracking=True,
        index=True,
        help="Current state of the alert in the workflow",
    )

    # Core fields
    title = fields.Char(
        string="Title",
        required=True,
        help="Brief summary of what triggered the alert",
    )

    description = fields.Text(
        string="Description",
        help="Detailed description of the alert condition",
    )

    # Metrics for threshold and deadline tracking
    current_value = fields.Float(
        string="Current Value",
        help="Current value that triggered the alert (for threshold alerts)",
    )

    threshold_value = fields.Float(
        string="Threshold",
        help="Threshold value that was exceeded (for threshold alerts)",
    )

    days_until = fields.Integer(
        string="Days Until",
        help="Days until expiry or deadline (positive = future, negative = overdue)",
    )

    # Resolution tracking
    resolved_by_id = fields.Many2one(
        "res.users",
        string="Resolved By",
        readonly=True,
        help="User who resolved this alert",
    )

    resolved_at = fields.Datetime(
        string="Resolved At",
        readonly=True,
        help="Timestamp when the alert was resolved",
    )

    resolution_notes = fields.Text(
        string="Resolution Notes",
        help="Notes about how the alert was resolved",
    )

    # Multi-company support
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
        help="Company this alert belongs to",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate reference from sequence."""
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                # Use sudo to access sequence (users may not have ir.sequence access)
                vals["reference"] = self.env["ir.sequence"].sudo().next_by_code("spp.alert") or _("New")
        return super().create(vals_list)

    def action_acknowledge(self):
        """Mark the alert as acknowledged.

        This is typically the first step in addressing an alert - acknowledging
        that it has been seen and is being investigated.
        """
        self.write({"state": "acknowledged"})
        return True

    def action_resolve(self, notes=None):
        """Mark the alert as resolved.

        Args:
            notes (str, optional): Resolution notes describing how the alert was addressed.

        Returns:
            bool: True on success
        """
        vals = {
            "state": "resolved",
            "resolved_by_id": self.env.user.id,
            "resolved_at": fields.Datetime.now(),
        }
        if notes:
            vals["resolution_notes"] = notes
        self.write(vals)
        return True
