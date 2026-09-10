import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SPPGRMTicket(models.Model):
    """Extend GRM Ticket to apply CEL-based routing and escalation rules."""

    _inherit = "spp.grm.ticket"

    # Add fields to track rule application
    routing_rule_id = fields.Many2one(
        comodel_name="spp.grm.routing.rule",
        string="Applied Routing Rule",
        readonly=True,
        help="The routing rule that was applied to this ticket",
    )
    escalation_rule_ids = fields.Many2many(
        comodel_name="spp.grm.escalation.rule",
        relation="grm_ticket_escalation_rule_rel",
        column1="ticket_id",
        column2="rule_id",
        string="Applied Escalation Rules",
        readonly=True,
        help="Escalation rules that have been applied to this ticket",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to apply routing rules to new tickets."""
        tickets = super().create(vals_list)

        # Hoisted out of the per-ticket loop: the active rule set (and each
        # rule's evaluation owner, with its warnings) is identical for every
        # ticket of this batch, so resolve it once — a misconfigured rule is
        # then warned about once per create, not once per ticket created.
        try:
            rules = self.env["spp.grm.routing.rule"]._active_rules_with_owners()
        except Exception:
            # Routing must never cost a ticket its creation; this is the same
            # guarantee _apply_routing_rules gives for a single ticket.
            _logger.exception("Could not resolve routing rules; tickets %s were not routed.", tickets.ids)
            return tickets

        # Apply routing rules to each new ticket
        for ticket in tickets:
            self._apply_routing_rules(ticket, rules=rules)

        return tickets

    def write(self, vals):
        """Override write to check for escalation triggers on stage change."""
        result = super().write(vals)

        # Check if stage changed
        if "stage_id" in vals:
            for ticket in self:
                self._check_escalation_rules(ticket)

        return result

    @api.model
    def _apply_routing_rules(self, ticket, rules=None):
        """Apply routing rules to a ticket.

        Args:
            ticket: spp.grm.ticket record
            rules: optional pre-resolved ``[(rule, owner), ...]`` shared by a
                batch (see ``spp.grm.routing.rule.apply_routing``)
        """
        try:
            _logger.debug("Applying routing rules to ticket %s", ticket.number)

            # Get routing rule model
            routing_model = self.env["spp.grm.routing.rule"]

            # Apply routing rules
            if routing_model.apply_routing(ticket, rules=rules):
                _logger.info("Routing rules applied to ticket %s", ticket.number)
            else:
                _logger.debug("No routing rules matched for ticket %s", ticket.number)

        except Exception as e:
            _logger.error(
                "Error applying routing rules to ticket %s: %s",
                ticket.number,
                str(e),
            )

    @api.model
    def _check_escalation_rules(self, ticket):
        """Check and apply escalation rules to a ticket.

        Args:
            ticket: spp.grm.ticket record
        """
        try:
            _logger.debug("Checking escalation rules for ticket %s", ticket.number)

            # Get escalation rule model
            escalation_model = self.env["spp.grm.escalation.rule"]

            # Apply escalation rules
            if escalation_model.apply_escalations(ticket):
                _logger.info("Escalation rules applied to ticket %s", ticket.number)
            else:
                _logger.debug("No escalation rules matched for ticket %s", ticket.number)

        except Exception as e:
            _logger.error(
                "Error checking escalation rules for ticket %s: %s",
                ticket.number,
                str(e),
            )

    def action_escalate(self):
        """Manual action to trigger escalation rule evaluation.

        Can be called from the UI to manually check if any escalation rules apply.

        The form button carries ``groups="spp_grm.group_grm_officer"``, but this
        method is dispatchable over RPC, where a view attribute guards nothing:
        base.group_user holds unscoped read on the tickets, so any internal user
        could otherwise force a full escalation pass — counters, chatter posts,
        notification mail, case creation — on any ticket in the database. The
        engine itself stays elevated (each rule is bounded by its own owner);
        what is checked here is entitlement to drive it. Write access is the
        button's audience — officers and above — and, unlike a group test, it
        also honours the caller's own ticket scope.
        """
        self.ensure_one()
        self.check_access("write")
        self._check_escalation_rules(self)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Escalation Check",
                "message": "Escalation rules have been evaluated for this ticket.",
                "type": "info",
                "sticky": False,
            },
        }
