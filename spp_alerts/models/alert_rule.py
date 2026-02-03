# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AlertRule(models.Model):
    """Alert rule configuration for defining monitoring criteria.

    Alert rules define the conditions and thresholds for automatically creating
    alerts. Consumer modules extend this model with domain-specific logic for
    checking conditions and creating alerts.

    Example usage in spp_drims:
    - Low stock rule: threshold_value = minimum stock level
    - Expiry rule: days_before = days before expiry to alert
    - SLA rule: days_before = days before deadline to warn

    The rule model provides the configuration; consumer modules implement the
    checking logic in their cron jobs or event handlers.
    """

    _name = "spp.alert.rule"
    _description = "Alert Rule"
    _order = "sequence, name"

    name = fields.Char(
        string="Rule Name",
        required=True,
        help="Descriptive name for this alert rule",
    )

    alert_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Alert Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:alerts')]",
        required=True,
        help="Type of alert this rule will create",
    )

    model_id = fields.Many2one(
        "ir.model",
        string="Model to Monitor",
        help="Odoo model this rule monitors (optional, used by consumer modules)",
    )

    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Default Priority",
        default="medium",
        required=True,
        help="Default priority for alerts created by this rule",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive rules will not create alerts",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of rule evaluation (lower = higher priority)",
    )

    # Threshold configuration
    threshold_value = fields.Float(
        string="Threshold Value",
        help="Threshold value for comparison (e.g., minimum stock level, maximum days)",
    )

    days_before = fields.Integer(
        string="Days Before",
        default=0,
        help="Days before expiry/deadline to trigger alert (0 = at deadline)",
    )

    description = fields.Text(
        string="Description",
        help="Description of when this rule triggers and what it monitors",
    )

    # Multi-company support
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company this rule applies to (empty = all companies)",
    )
