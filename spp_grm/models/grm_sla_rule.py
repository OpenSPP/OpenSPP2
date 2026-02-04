import ast
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPGRMSLARule(models.Model):
    """SLA Rule model for defining service level agreements.

    SLA Rules define time-based targets for ticket response and resolution
    with conditions for when they apply and escalation procedures.
    """

    _name = "spp.grm.sla.rule"
    _description = "GRM SLA Rule"
    _order = "sequence, id"

    name = fields.Char(
        string="Rule Name",
        required=True,
        translate=True,
        help="Name of this SLA rule",
    )
    sequence = fields.Integer(
        default=10,
        help="Order of evaluation - lower sequence rules are checked first",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to disable this rule without deleting it",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of when this rule applies and what it does",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company this SLA rule applies to",
    )

    # Condition Fields
    condition_domain = fields.Char(
        string="Condition Domain",
        help="Domain filter to determine which tickets this rule applies to. "
        "Example: [('severity','=','critical'),('category_id.code','=','ABUSE')]",
        default="[]",
    )

    # SLA Time Targets
    response_hours = fields.Integer(
        string="Response Time (Hours)",
        help="Maximum hours for initial response to the ticket",
    )
    resolution_hours = fields.Integer(
        string="Resolution Time (Hours)",
        help="Maximum hours for complete resolution of the ticket",
    )

    # Escalation Configuration
    escalate_after_hours = fields.Integer(
        string="Escalate After (Hours)",
        help="Automatically escalate ticket after this many hours if not resolved",
    )
    escalate_to_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Escalate To User",
        help="User to escalate tickets to when escalation time is reached",
    )
    escalate_to_team_id = fields.Many2one(
        comodel_name="spp.grm.team",
        string="Escalate To Team",
        help="Team to escalate tickets to when escalation time is reached",
    )

    # Rule Applicability
    category_ids = fields.Many2many(
        comodel_name="spp.grm.ticket.category",
        relation="grm_sla_rule_category_rel",
        column1="sla_rule_id",
        column2="category_id",
        string="Categories",
        help="If specified, this rule only applies to tickets in these categories",
    )
    team_ids = fields.Many2many(
        comodel_name="spp.grm.team",
        relation="grm_sla_rule_team_rel",
        column1="sla_rule_id",
        column2="team_id",
        string="Teams",
        help="If specified, this rule only applies to tickets assigned to these teams",
    )

    @api.constrains("response_hours", "resolution_hours", "escalate_after_hours")
    def _check_hours_positive(self):
        """Ensure all hour values are positive if set."""
        for rule in self:
            if rule.response_hours and rule.response_hours < 0:
                raise ValidationError("Response hours must be positive.")
            if rule.resolution_hours and rule.resolution_hours < 0:
                raise ValidationError("Resolution hours must be positive.")
            if rule.escalate_after_hours and rule.escalate_after_hours < 0:
                raise ValidationError("Escalation hours must be positive.")

    @api.constrains("response_hours", "resolution_hours")
    def _check_response_resolution_logic(self):
        """Ensure response time is less than resolution time if both are set."""
        for rule in self:
            if rule.response_hours and rule.resolution_hours:
                if rule.response_hours > rule.resolution_hours:
                    raise ValidationError(
                        "Response time cannot be greater than resolution time. "
                        f"Response: {rule.response_hours}h, Resolution: {rule.resolution_hours}h"
                    )

    def evaluate_ticket(self, ticket):
        """Evaluate if this SLA rule applies to a given ticket.

        Args:
            ticket: spp.grm.ticket record to evaluate

        Returns:
            bool: True if rule applies to the ticket, False otherwise
        """
        self.ensure_one()

        # Check category filter
        if self.category_ids and ticket.category_id not in self.category_ids:
            return False

        # Check team filter
        if self.team_ids and ticket.team_id not in self.team_ids:
            return False

        # Evaluate domain condition from stored literal domain expression
        if self.condition_domain and self.condition_domain != "[]":
            try:
                domain = ast.literal_eval(self.condition_domain)
                matching = self.env["spp.grm.ticket"].search([("id", "=", ticket.id)] + domain)
                if not matching:
                    return False
            except Exception as e:
                # Log error but don't fail - treat invalid domain as not matching
                _logger.warning("Error evaluating SLA rule ID %s domain: %s", self.id, e)
                return False

        return True

    def get_sla_for_ticket(self, ticket):
        """Get the applicable SLA rule for a ticket.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            spp.grm.sla.rule record or empty recordset if no rule applies
        """
        # Search active rules ordered by sequence
        rules = self.search([("active", "=", True), ("company_id", "=", ticket.company_id.id)])

        # Return first matching rule
        for rule in rules:
            if rule.evaluate_ticket(ticket):
                return rule

        return self.browse()
