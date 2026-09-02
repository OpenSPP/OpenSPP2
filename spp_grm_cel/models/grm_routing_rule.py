import logging

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

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

    eval_as_user_id = fields.Many2one(
        "res.users",
        string="Evaluated As",
        readonly=True,
        ondelete="restrict",
        help="User whose record-rule visibility bounds this rule's evaluation and "
        "the ticket writes it performs. Set to whoever last defined what the rule "
        "targets, so an elevated cron can never apply a rule beyond its author's "
        "reach. System-managed; not editable.",
    )
    # No Python `default` on purpose (see PR #364, spp_alerts): a default makes
    # _init_column backfill existing rows with the UPGRADE user before the
    # migration runs, and lets a client forge the value via a
    # default_eval_as_user_id context key. The identity is set explicitly in
    # create(); the migration backfills existing rows from create_uid.

    # Fields that decide what a rule matches or does. Changing any re-binds the
    # evaluation identity to the editor (see write), so a rule can never be
    # repointed to act beyond its editor's ticket scope. Deliberately excludes
    # operational toggles (sequence, active): reordering or archiving/unarchiving
    # a rule must not silently transfer ownership to the person doing that
    # routine action (a manager cleaning up an officer's rule would otherwise
    # re-bind it to the manager's broad scope).
    _EVAL_TARGETING_FIELDS = (
        "condition_cel",
        "assign_user_id",
        "assign_team_id",
        "set_severity",
        "set_priority",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Force the evaluation identity to the creator; never client-supplied.

        Setting the key explicitly (rather than popping it) keeps the field
        present in vals so default_get — which honours a client
        default_eval_as_user_id context key — is never consulted for it.
        """
        vals_list = [dict(vals, eval_as_user_id=self.env.uid) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        """Re-bind the evaluation identity to the editor when targeting changes.

        eval_as_user_id tracks whoever last defined what the rule targets. A
        client can never point it at a third party; the only accepted explicit
        value is the acting user's own id (see action_take_ownership), which is
        the same re-bind the targeting-field path performs. self.env.uid is the
        acting user, preserved even under sudo() (only an explicit
        with_user(<elevated>) write re-widens).
        """
        if any(f in vals for f in self._EVAL_TARGETING_FIELDS) or vals.get("eval_as_user_id") == self.env.uid:
            vals = dict(vals, eval_as_user_id=self.env.uid)
        elif "eval_as_user_id" in vals:
            vals = {k: v for k, v in vals.items() if k != "eval_as_user_id"}
        return super().write(vals)

    def action_take_ownership(self):
        """Re-bind these rules' evaluation identity to the acting user.

        The remediation path for a rule owned by the superuser (created from a
        shell, import or data load), by an archived user, or by someone whose
        ticket scope no longer fits: from now on the rule evaluates within the
        acting user's own record-rule scope. Saving the form without changing a
        targeting field does not re-bind (the client only sends dirty fields).
        """
        self.write({"eval_as_user_id": self.env.uid})
        return True

    def _evaluation_owner(self):
        """Return the user this rule evaluates as, or an empty recordset.

        Empty means the rule must not fire: it has no identity at all, or its
        owner is archived (an offboarded user's scope must not keep driving
        automation). A superuser owner is kept but called out: with_user(1)
        always runs in superuser mode, so such a rule evaluates unbounded until
        someone takes ownership (checked before the archive test, since Odoo's
        ``__system__`` user is itself inactive). Logs once per call.
        """
        self.ensure_one()
        owner = self.eval_as_user_id or self.create_uid
        if not owner:
            _logger.warning(
                "Routing rule %s (id %s) has no evaluation identity (owner and "
                "create_uid both unset); skipping until someone takes ownership of it.",
                self.name,
                self.id,
            )
            return self.env["res.users"]
        if owner.id == SUPERUSER_ID:
            _logger.warning(
                "Routing rule %s (id %s) is owned by the superuser and evaluates "
                "without record-rule bounds; take ownership of it as a real user to scope it.",
                self.name,
                self.id,
            )
            return owner
        if not owner.active:
            _logger.warning(
                "Routing rule %s (id %s) is owned by archived user %s; skipping until someone takes ownership of it.",
                self.name,
                self.id,
                owner.login,
            )
            return self.env["res.users"]
        return owner

    @api.model
    def _active_rules_with_owners(self):
        """Active rules paired with their evaluation owner, in sequence order.

        Searched with sudo(): the acting user (the sudo'd portal controller, an
        officer creating a ticket) never needs read access on the rules,
        because every effect is bounded by the owner identity each rule is
        applied with. Rules without a usable owner are dropped here.
        """
        # nosemgrep: semgrep.odoo-sudo-without-context -- reads only the rule set; every effect below runs with_user(owner), never elevated
        rules = self.sudo().search([("active", "=", True)], order="sequence, id")
        return [(rule, owner) for rule in rules if (owner := rule._evaluation_owner())]

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
                except Exception as e:
                    # Any parser failure (not only SyntaxError) is a bad
                    # expression the user must fix, surfaced as a ValidationError.
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

    @api.private
    def apply_routing(self, ticket):
        """Apply the first matching routing rule to a ticket.

        Each rule is evaluated and applied with the identity of whoever defined
        it (``eval_as_user_id``), so an elevated caller (the sudo'd portal
        controller, an admin) can never make a rule act beyond its author's
        ticket scope. Private: not RPC-dispatchable; call from trusted server
        code only.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if a rule was applied, False otherwise
        """
        for rule, owner in self._active_rules_with_owners():
            # nosemgrep: semgrep.odoo-with-user-unvalidated -- owner is system-set in create()/write(), not client input
            rule_as_owner = rule.with_user(owner.id)
            # nosemgrep: semgrep.odoo-with-user-unvalidated -- owner is system-set; scopes ticket writes
            ticket_as_owner = ticket.with_user(owner.id)
            try:
                matched = rule_as_owner.evaluate(ticket_as_owner)
            except AccessError:
                # The rule owner cannot see this ticket -> the rule does not
                # apply to it. Correct behaviour, not an error.
                _logger.debug(
                    "Routing rule %s: owner %s cannot read ticket %s; rule does not apply.",
                    rule.name,
                    owner.login,
                    ticket.id,
                )
                continue
            if matched:
                # Apply the rule's actions as the owner: the ticket.write is
                # bounded by the owner's record rules.
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

                try:
                    ticket_as_owner.write(vals)
                except AccessError:
                    # Owner may match the ticket but not be allowed to write it
                    # (e.g. read-only scope). Skip rather than apply elevated.
                    _logger.info(
                        "Routing rule %s: owner %s lacks write access on ticket %s; skipped.",
                        rule.name,
                        owner.login,
                        ticket.id,
                    )
                    continue
                _logger.info(
                    "Applied routing rule '%s' to ticket %s: %s",
                    rule.name,
                    ticket.number,
                    vals,
                )

                # Atomic increment: a read-modify-write here would raise a
                # serialization failure under concurrent routing (cursors run
                # REPEATABLE READ), retried only at whole-dispatch granularity.
                # A single UPDATE avoids the conflict entirely, and needs no
                # sudo (raw SQL bypasses ACL). Invisible to spp_audit ORM
                # write-hooks, which is acceptable for a statistics counter.
                rule.flush_recordset(["match_count"])
                self.env.cr.execute(
                    "UPDATE spp_grm_routing_rule SET match_count = match_count + 1 WHERE id = %s",
                    (rule.id,),
                )
                rule.invalidate_recordset(["match_count"])

                # Only apply the first matching rule
                return True

        _logger.debug("No routing rules matched for ticket %s", ticket.number)
        return False
