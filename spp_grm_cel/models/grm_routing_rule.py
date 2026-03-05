import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Import CEL parser from spp_cel_domain
try:
    from odoo.addons.spp_cel_domain.services import cel_parser as P
except ImportError:
    P = None


class GRMRoutingRule(models.Model):
    """GRM Routing Rule using CEL expressions.

    Routing rules automatically assign tickets to teams and users based on
    CEL conditions that evaluate ticket properties.
    """

    _name = "spp.grm.routing.rule"
    _description = "GRM Routing Rule"
    _order = "sequence, id"

    name = fields.Char(
        string="Rule Name",
        required=True,
        help="Descriptive name for this routing rule",
    )
    sequence = fields.Integer(
        default=10,
        help="Rules are evaluated in sequence order (lower number = higher priority)",
    )
    active = fields.Boolean(
        default=True,
        help="Set to inactive to disable this rule without deleting it",
    )

    # Condition (CEL expression)
    condition_cel = fields.Text(
        string="Condition (CEL)",
        help="CEL expression that must evaluate to true for this rule to apply.\n"
        "Available context variables:\n"
        "  - ticket: The GRM ticket record\n"
        "  - category: ticket.category_id\n"
        "  - channel: ticket.channel_id\n"
        "  - stage: ticket.stage_id\n"
        "  - severity: ticket.severity\n"
        "  - priority: ticket.priority\n"
        "  - partner: ticket.partner_id\n"
        "  - team: ticket.team_id\n"
        "  - user: ticket.user_id\n"
        "\n"
        "Available helper functions:\n"
        "  - days_since(date): Number of days since a date\n"
        "  - hours_since(datetime): Number of hours since a datetime\n"
        "  - is_business_day(date): True if date is Monday-Friday\n"
        "\n"
        "Example: severity == 'critical' or category.name == 'Fraud'\n"
        "Example: days_since(ticket.create_date) > 5 and is_business_day(ticket.create_date)",
    )

    # Actions to perform when rule matches
    assign_team_id = fields.Many2one(
        comodel_name="spp.grm.team",
        string="Assign to Team",
        help="Team to assign the ticket to when this rule matches",
    )
    assign_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Assign to User",
        help="User to assign the ticket to when this rule matches",
    )
    set_severity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        help="Override ticket severity when this rule matches",
    )
    set_priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        help="Override ticket priority when this rule matches",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company this rule applies to",
    )

    # Statistics
    match_count = fields.Integer(
        string="Matched Tickets",
        default=0,
        help="Number of tickets this rule has matched",
    )

    @api.constrains("condition_cel")
    def _check_condition_cel(self):
        """Validate CEL expression syntax using CEL parser."""
        for rule in self:
            if rule.condition_cel:
                try:
                    if P:
                        # Use proper CEL parser for validation
                        P.parse(rule.condition_cel)
                    # If parser not available, skip validation
                except SyntaxError as e:
                    raise ValidationError(
                        _(
                            "Invalid CEL expression in rule '%(rule_name)s': %(error)s",
                            rule_name=rule.name,
                            error=str(e),
                        )
                    ) from e

    def evaluate(self, ticket):
        """Evaluate if this rule applies to the given ticket.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if the rule condition matches, False otherwise
        """
        self.ensure_one()

        # If no condition, rule always matches
        if not self.condition_cel:
            return True

        # Build evaluation context
        context = self._build_evaluation_context(ticket)

        try:
            # Use simple Python expression evaluation
            # In a production environment, you'd use the full CEL parser
            result = self._evaluate_expression(self.condition_cel, context)
            _logger.debug(
                "Routing rule '%s' evaluation for ticket %s: %s",
                self.name,
                ticket.number,
                result,
            )
            return bool(result)
        except Exception as e:
            _logger.warning(
                "Error evaluating routing rule '%s' for ticket %s: %s",
                self.name,
                ticket.number,
                str(e),
            )
            return False

    def _build_evaluation_context(self, ticket):
        """Build the context dictionary for CEL evaluation.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            dict: Context with available variables and helper functions
        """
        # Import helper functions from cel_parser
        if P:
            context_funcs = P.get_default_functions()
        else:
            context_funcs = {}

        # Build context with ticket properties and helper functions
        context = {
            "ticket": ticket,
            "category": ticket.category_id,
            "channel": ticket.channel_id,
            "stage": ticket.stage_id,
            "severity": ticket.severity,
            "priority": ticket.priority,
            "partner": ticket.partner_id,
            "team": ticket.team_id,
            "user": ticket.user_id,
        }

        # Add helper functions to context
        context.update(context_funcs)

        return context

    def _evaluate_expression(self, expression, context):
        """Evaluate a CEL expression using the CEL parser.

        Parses the expression into an AST and evaluates it against the context
        using the centralized evaluate() function from cel_parser.

        Args:
            expression: str, the CEL expression
            context: dict, variables available to the expression

        Returns:
            bool or any: Result of the expression
        """
        if not P:
            raise RuntimeError("CEL parser not available")

        try:
            ast = P.parse(expression)
            return P.evaluate(ast, context)
        except Exception as e:
            _logger.warning("Expression evaluation error: %s", str(e))
            raise

    @api.model
    def apply_routing(self, ticket):
        """Apply the first matching routing rule to a ticket.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if a rule was applied, False otherwise
        """
        # Search for active rules in sequence order
        rules = self.search([("active", "=", True)], order="sequence, id")

        for rule in rules:
            if rule.evaluate(ticket):
                # Apply the rule's actions
                vals = {
                    "routing_rule_id": rule.id,  # Track which rule was applied
                }

                if rule.assign_team_id:
                    vals["team_id"] = rule.assign_team_id.id

                if rule.assign_user_id:
                    vals["user_id"] = rule.assign_user_id.id

                if rule.set_severity:
                    vals["severity"] = rule.set_severity

                if rule.set_priority:
                    vals["priority"] = rule.set_priority

                ticket.write(vals)
                _logger.info(
                    "Applied routing rule '%s' to ticket %s: %s",
                    rule.name,
                    ticket.number,
                    vals,
                )

                # Update match count
                # nosemgrep: semgrep.odoo-sudo-without-context -- counter update needs sudo
                rule.sudo().write({"match_count": rule.match_count + 1})

                # Only apply the first matching rule
                return True

        _logger.debug("No routing rules matched for ticket %s", ticket.number)
        return False
