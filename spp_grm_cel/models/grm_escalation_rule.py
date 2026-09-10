import logging

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Import CEL parser from spp_cel_domain
try:
    from odoo.addons.spp_cel_domain.services import cel_parser as P
except ImportError:
    P = None


class GRMEscalationRule(models.Model):
    """GRM Escalation Rule using CEL expressions.

    Escalation rules automatically escalate tickets based on CEL conditions
    that evaluate ticket properties and time-based criteria.
    """

    _name = "spp.grm.escalation.rule"
    _description = "GRM Escalation Rule"
    _order = "sequence, id"

    name = fields.Char(
        string="Rule Name",
        required=True,
        help="Descriptive name for this escalation rule",
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
        "  - sla_status: ticket.sla_status\n"
        "  - days_open: ticket.days_open\n"
        "  - is_escalated: ticket.is_escalated\n"
        "\n"
        "Available helper functions:\n"
        "  - days_since(date): Number of days since a date\n"
        "  - hours_since(datetime): Number of hours since a datetime\n"
        "  - is_business_day(date): True if date is Monday-Friday\n"
        "\n"
        "Example: sla_status == 'breached' or (severity == 'critical' and days_open > 3)\n"
        "Example: hours_since(ticket.create_date) > 48 and not is_business_day(ticket.create_date)",
    )

    # Time-based triggers
    trigger_after_hours = fields.Integer(
        default=0,
        help="Automatically trigger this rule after ticket is open for this many hours (0 = no time trigger)",
    )

    # Escalation Actions
    escalate_to_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Escalate to User",
        help="User to escalate the ticket to when this rule matches",
    )
    escalate_to_team_id = fields.Many2one(
        comodel_name="spp.grm.team",
        string="Escalate to Team",
        help="Team to escalate the ticket to when this rule matches",
    )
    escalate_severity = fields.Selection(
        selection=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Escalate Severity To",
        help="Increase ticket severity to this level when escalating",
    )
    escalate_priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        string="Escalate Priority To",
        help="Increase ticket priority to this level when escalating",
    )

    # Notification settings
    should_send_notification = fields.Boolean(
        string="Send Notification",
        default=True,
        help="Send notification email when escalating",
    )
    notification_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Notification Template",
        help="Email template to use for escalation notifications",
    )

    # Case Management Integration
    create_case = fields.Boolean(
        default=False,
        help="Automatically create a case management record when escalating",
    )
    case_type_id = fields.Many2one(
        comodel_name="spp.case.type",
        string="Case Type",
        help="Type of case to create when escalating (requires spp_case_management module)",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        help="Company this rule applies to",
    )

    # Statistics
    escalation_count = fields.Integer(
        string="Escalations Triggered",
        default=0,
        help="Number of times this rule has triggered an escalation",
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
        "escalate_to_user_id",
        "escalate_to_team_id",
        "escalate_severity",
        "escalate_priority",
        "trigger_after_hours",
        "should_send_notification",
        "notification_template_id",
        "create_case",
        "case_type_id",
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

        Any other explicit value raises rather than being dropped: a silent
        no-op returning True let a data fix or migration script report success
        while the rules kept evaluating as their old owner. UserError, not
        AccessError — the write itself is allowed, the field is simply not the
        caller's to set.
        """
        if "eval_as_user_id" in vals and vals["eval_as_user_id"] != self.env.uid:
            raise UserError(
                _(
                    "A rule's evaluation identity is managed by the system and cannot be "
                    'assigned to another user. Open the rule and use "Take Ownership" to '
                    "bind it to yourself."
                )
            )
        if any(f in vals for f in self._EVAL_TARGETING_FIELDS) or "eval_as_user_id" in vals:
            vals = dict(vals, eval_as_user_id=self.env.uid)
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
                except (SyntaxError, RecursionError) as e:
                    # What the parser raises for an expression the user must
                    # fix (bad syntax, or nesting past its depth limit).
                    raise ValidationError(
                        _(
                            "Invalid CEL expression in rule '%(rule_name)s': %(error)s",
                            rule_name=rule.name,
                            error=str(e),
                        )
                    ) from e
                except Exception as e:
                    # Anything else is a defect in the parser, not bad input:
                    # keep the traceback in the log instead of discarding it
                    # and blaming the user's expression.
                    _logger.exception(
                        "Validating the CEL expression of rule '%s' failed unexpectedly",
                        rule.name,
                    )
                    raise ValidationError(
                        _(
                            "Could not validate the CEL expression in rule '%(rule_name)s': "
                            "%(error)s. This is an internal error, not a problem with the "
                            "expression; see the server log.",
                            rule_name=rule.name,
                            error=str(e),
                        )
                    ) from e

    @api.constrains("trigger_after_hours")
    def _check_trigger_after_hours(self):
        """Validate trigger_after_hours is non-negative."""
        for rule in self:
            if rule.trigger_after_hours < 0:
                raise ValidationError(_("Trigger after hours must be non-negative"))

    def evaluate(self, ticket):
        """Evaluate if this rule applies to the given ticket.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if the rule condition matches, False otherwise
        """
        self.ensure_one()

        # Check time-based trigger first
        if self.trigger_after_hours > 0:
            if not self._check_time_trigger(ticket):
                return False

        # If no condition, rule matches (time trigger passed)
        if not self.condition_cel:
            return True

        # Build evaluation context
        context = self._build_evaluation_context(ticket)

        try:
            # Use simple Python expression evaluation
            result = self._evaluate_expression(self.condition_cel, context)
            _logger.debug(
                "Escalation rule '%s' evaluation for ticket %s: %s",
                self.name,
                ticket.number,
                result,
            )
            return bool(result)
        except Exception as e:
            _logger.warning(
                "Error evaluating escalation rule '%s' for ticket %s: %s",
                self.name,
                ticket.number,
                str(e),
            )
            return False

    def _check_time_trigger(self, ticket):
        """Check if the time-based trigger condition is met.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if trigger time has passed, False otherwise
        """
        if not self.trigger_after_hours:
            return True

        if not ticket.create_date:
            return False

        # Calculate hours since ticket creation
        now = fields.Datetime.now()
        delta = now - ticket.create_date
        hours_open = delta.total_seconds() / 3600

        return hours_open >= self.trigger_after_hours

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
            "sla_status": ticket.sla_status,
            "days_open": ticket.days_open,
            "is_escalated": ticket.is_escalated,
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
    def apply_escalation(self, ticket):
        """Apply this escalation rule to a ticket.

        Private: not RPC-dispatchable. Callers must evaluate the rule with its
        owner identity first (see apply_escalations); the ticket writes below
        run in whatever context ``self``/``ticket`` carry.

        Args:
            ticket: spp.grm.ticket record

        Returns:
            bool: True if escalation was applied, False otherwise
        """
        self.ensure_one()

        vals = {
            "is_escalated": True,
            "escalation_date": fields.Datetime.now(),
        }

        if self.escalate_to_user_id:
            vals["escalated_to_id"] = self.escalate_to_user_id.id
            vals["user_id"] = self.escalate_to_user_id.id

        if self.escalate_to_team_id:
            vals["team_id"] = self.escalate_to_team_id.id

        if self.escalate_severity:
            vals["severity"] = self.escalate_severity

        if self.escalate_priority:
            vals["priority"] = self.escalate_priority

        # Set escalation reason
        vals["escalation_reason"] = _(
            "Automatically escalated by rule: %(rule_name)s",
            rule_name=self.name,
        )

        # Track which escalation rule was applied (many2many)
        vals["escalation_rule_ids"] = [Command.link(self.id)]

        # One write: write() checks the owner's access against the ticket's
        # current state, so a single call succeeds whenever the owner may edit
        # the ticket (the UI semantics). A second write would re-check against
        # the reassigned state and be denied for nothing.
        ticket.write(vals)

        _logger.info(
            "Applied escalation rule '%s' to ticket %s: %s",
            self.name,
            ticket.number,
            vals,
        )

        # Post to chatter before the notification goes out. spp.grm.ticket sets
        # _mail_post_access = "read", so posting needs read access on the
        # ticket, which the rule owner may have just lost by reassigning it out
        # of their own scope. When that happens the caller's savepoint rolls
        # everything back — and because nothing external has fired yet, no
        # ghost notification announces a rolled-back escalation.
        ticket.message_post(
            body=_(
                "Ticket escalated by rule: <b>%(rule_name)s</b>",
                rule_name=self.name,
            ),
            subject=_("Ticket Escalated"),
        )

        # Create case if configured
        if self.create_case and self.case_type_id:
            self._create_case_from_ticket(ticket)

        # Atomic increment: a read-modify-write here would raise a serialization
        # failure under concurrent cron/UI escalation (cursors run REPEATABLE
        # READ), and the only auto-retry is the whole dispatch — re-running the
        # entire cron pass and re-firing notifications. A single UPDATE avoids
        # the conflict entirely, and needs no sudo (raw SQL bypasses ACL).
        # Invisible to spp_audit ORM write-hooks, acceptable for a stats counter.
        self.flush_recordset(["escalation_count"])
        self.env.cr.execute(
            "UPDATE spp_grm_escalation_rule SET escalation_count = escalation_count + 1 WHERE id = %s",
            (self.id,),
        )
        self.invalidate_recordset(["escalation_count"])

        # Sent last, once every effect that can still be denied has succeeded:
        # delivery is the one step no rollback takes back. A mail sent for an
        # escalation the caller then rolls back is a ghost that also repeats —
        # the rolled-back escalation_rule_ids link no longer suppresses the
        # rule, so the next hourly pass sends it again.
        if self.should_send_notification and self.notification_template_id:
            self._send_escalation_notification(ticket)

        return True

    def _send_escalation_notification(self, ticket):
        """Send escalation notification email.

        Delivery problems are logged and skipped (best effort), but a denied
        template or ticket read re-raises so the caller's savepoint rolls the
        whole escalation back: the rule owner must be entitled to every effect
        the rule produces. The inner savepoint keeps a failed send from leaving
        the transaction in an aborted state for the steps that follow.

        Args:
            ticket: spp.grm.ticket record
        """
        try:
            with self.env.cr.savepoint():
                self.notification_template_id.send_mail(
                    ticket.id,
                    force_send=True,
                )
        except AccessError:
            raise
        except Exception as e:
            _logger.error(
                "Failed to send escalation notification for ticket %s: %s",
                ticket.number,
                str(e),
            )
            return
        _logger.info(
            "Sent escalation notification for ticket %s using template %s",
            ticket.number,
            self.notification_template_id.name,
        )

    def _create_case_from_ticket(self, ticket):
        """Create a case management record from an escalated ticket.

        A denied create (the rule owner is not allowed to create cases)
        re-raises so the caller's savepoint rolls the whole escalation back
        rather than reporting an escalation whose case silently never existed.
        Other failures are logged and skipped; the inner savepoint keeps them
        from leaving the transaction in an aborted state.

        Args:
            ticket: spp.grm.ticket record
        """
        # Check if spp_case_management module is installed
        if "spp.case" not in self.env:
            _logger.warning(
                "Cannot create case for ticket %s: spp_case_management module not installed",
                ticket.number,
            )
            return

        # spp.case requires a case worker, and it has to be a real person who
        # is answerable for the case. The candidates are the ticket assignee
        # and, failing that, whoever the rule evaluates as — but a superuser
        # owner (a rule created from a shell, import or data load) resolves to
        # __system__, an inactive non-human account, and an archived assignee
        # is no better. Raised before the savepoint below so the caller rolls
        # the escalation back rather than reporting it applied with the case
        # filed under OdooBot.
        case_worker = ticket.user_id or self.env.user
        if case_worker.id == SUPERUSER_ID or not case_worker.active:
            raise UserError(
                _(
                    "Escalation rule '%(rule_name)s' creates a case but has no one to assign "
                    "it to: ticket %(ticket_number)s resolves to %(worker)s, which is not a "
                    'real active user. Assign the ticket, or use "Take Ownership" on the rule '
                    "as the user who should own it.",
                    rule_name=self.name,
                    ticket_number=ticket.number,
                    worker=case_worker.display_name,
                )
            )

        try:
            with self.env.cr.savepoint():
                case = self.env["spp.case"].create(
                    {
                        "name": _("Escalated from ticket: %s") % ticket.number,
                        "case_type_id": self.case_type_id.id,
                        "partner_id": ticket.partner_id.id,
                        "presenting_issue": ticket.description,
                        # Required on spp.case; resolved and vetted above.
                        "case_worker_id": case_worker.id,
                    }
                )

                # Link case to ticket if spp_grm_case_link is installed
                if hasattr(ticket, "case_id"):
                    ticket.write({"case_id": case.id})

                # Post message to ticket
                ticket.message_post(
                    body=_("Case created: <a href='/web#id=%(case_id)s&model=spp.case'>%(case_name)s</a>")
                    % {"case_id": case.id, "case_name": case.name},
                    subject=_("Case Created"),
                )
        except AccessError:
            raise
        except Exception as e:
            _logger.error(
                "Failed to create case for ticket %s: %s",
                ticket.number,
                str(e),
            )
            return
        _logger.info(
            "Created case %s from escalated ticket %s",
            case.id,
            ticket.number,
        )

    @api.model
    @api.private
    def check_escalations(self):
        """Cron job to check and apply escalation rules to open tickets.

        This should be called periodically (e.g., hourly) by a scheduled action.
        Private: invoked server-side by ir.cron, never via RPC.
        """
        # Find all open tickets
        tickets = self.env["spp.grm.ticket"].search(
            [
                ("is_closed", "=", False),
            ]
        )

        _logger.info("Checking escalation rules for %d open tickets", len(tickets))

        # Hoisted out of the per-ticket loop: the active-rule set (and each
        # rule's evaluation owner, with its warnings) is identical for every
        # ticket in this pass, so resolve it once, not once per ticket.
        rules = self._active_rules_with_owners()

        escalated_count = 0
        for ticket in tickets:
            if self.apply_escalations(ticket, rules=rules):
                escalated_count += 1

        _logger.info("Escalated %d tickets", escalated_count)
        return escalated_count

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
                "Escalation rule %s (id %s) has no evaluation identity (owner and "
                "create_uid both unset); skipping until someone takes ownership of it.",
                self.name,
                self.id,
            )
            return self.env["res.users"]
        if owner.id == SUPERUSER_ID:
            _logger.warning(
                "Escalation rule %s (id %s) is owned by the superuser and evaluates "
                "without record-rule bounds; take ownership of it as a real user to scope it.",
                self.name,
                self.id,
            )
            return owner
        if not owner.active:
            _logger.warning(
                "Escalation rule %s (id %s) is owned by archived user %s; skipping until "
                "someone takes ownership of it.",
                self.name,
                self.id,
                owner.login,
            )
            return self.env["res.users"]
        return owner

    @api.model
    def _active_rules_with_owners(self):
        """Active rules paired with their evaluation owner, in sequence order.

        Searched with sudo(): the acting user (the cron, the sudo'd SLA path,
        an officer pressing "Check Escalation") never needs read access on the
        rules, because every effect is bounded by the owner identity each rule
        is applied with. Rules without a usable owner are dropped here, so the
        cron logs each warning once per pass rather than once per ticket.
        """
        # nosemgrep: semgrep.odoo-sudo-without-context -- reads the rule set only; effects run with_user(owner)
        rules = self.sudo().search([("active", "=", True)], order="sequence, id")
        return [(rule, owner) for rule in rules if (owner := rule._evaluation_owner())]

    @api.model
    @api.private
    def apply_escalations(self, ticket, rules=None):
        """Apply all matching escalation rules to a ticket.

        Each rule is evaluated and applied with the identity of whoever defined
        it (``eval_as_user_id``), so an elevated caller (the hourly cron, the
        sudo'd SLA-breach path) can never make a rule act beyond its author's
        ticket scope. A rule applies at most once per ticket. Private: not
        RPC-dispatchable.

        Args:
            ticket: spp.grm.ticket record
            rules: optional pre-resolved ``[(rule, owner), ...]`` from
                ``_active_rules_with_owners``; a caller looping many tickets
                (the cron) resolves them once instead of once per ticket

        Returns:
            bool: True if any rule was applied, False otherwise
        """
        if rules is None:
            rules = self._active_rules_with_owners()

        already_applied = set(ticket.escalation_rule_ids.ids)
        applied = False
        for rule, owner in rules:
            if rule.id in already_applied:
                # Without this the hourly cron re-escalated every still-open
                # matching ticket each pass: counter, chatter post and
                # notification repeated every hour.
                continue
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
                    "Escalation rule %s: owner %s cannot read ticket %s; rule does not apply.",
                    rule.name,
                    owner.login,
                    ticket.id,
                )
                continue
            if not matched:
                continue
            try:
                # Savepoint: apply_escalation has side effects after its ticket
                # write (chatter post, notification, case creation, counter),
                # any of which can be denied once the write itself has
                # reassigned the ticket out of the owner's own scope. Roll all
                # of it back rather than leave a half-applied escalation.
                with self.env.cr.savepoint():
                    rule_as_owner.apply_escalation(ticket_as_owner)
            except AccessError:
                # Owner matched but is not allowed to perform every effect on
                # this ticket -> skip rather than apply with elevated rights.
                _logger.info(
                    "Escalation rule %s: owner %s was denied on ticket %s; escalation rolled back and skipped.",
                    rule.name,
                    owner.login,
                    ticket.id,
                )
                continue
            except Exception:
                # Per-ticket isolation: the savepoint has already rolled this
                # escalation back. A constraint or database error on one ticket
                # must not abort the whole cron pass.
                _logger.exception(
                    "Escalation rule %s failed on ticket %s; rolled back and skipped.",
                    rule.name,
                    ticket.id,
                )
                continue
            applied = True
            # Continue checking other rules (unlike routing, multiple escalations can apply)

        return applied
