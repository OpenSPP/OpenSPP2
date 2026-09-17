# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import operator as op
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)

COMPARISON_OPERATORS = {
    "lt": op.lt,
    "lte": op.le,
    "gt": op.gt,
    "gte": op.ge,
    "eq": op.eq,
}


class AlertRule(models.Model):
    """Alert rule configuration for defining monitoring criteria.

    Alert rules define the conditions and thresholds for automatically creating
    alerts. Rules can be evaluated automatically via cron or manually via the
    "Run Now" button.

    Supports two rule types:
    - Threshold: Compare a numeric field against a threshold value
    - Date: Check if a date field is within N days of today

    Consumer modules (like spp_drims) can extend this model or implement their
    own alert creation logic independently.
    """

    _name = "spp.alert.rule"
    _description = "Alert Rule"
    _inherit = ["mail.thread"]
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
        help="Odoo model this rule monitors",
        tracking=True,
    )

    model_name = fields.Char(
        related="model_id.model",
        string="Model Name",
        readonly=True,
        help="Technical model name, used by the domain filter widget",
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
        tracking=True,
    )

    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive rules will not create alerts",
        tracking=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of rule evaluation (lower = higher priority)",
    )

    # Rule evaluation configuration
    rule_type = fields.Selection(
        [
            ("threshold", "Threshold"),
            ("date", "Date / Deadline"),
        ],
        string="Rule Type",
        help="Determines evaluation logic:\n"
        "- Threshold: Compare a numeric field against threshold_value\n"
        "- Date: Check if a date field is within days_before of today",
        tracking=True,
    )

    domain_filter = fields.Text(
        string="Domain Filter",
        default="[]",
        help="Odoo domain expression to filter records on the monitored model. "
        'Uses standard Odoo domain syntax, e.g. [("active", "=", True)]',
    )

    monitored_field_id = fields.Many2one(
        "ir.model.fields",
        string="Monitored Field",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('float', 'integer', 'monetary'))]",
        help="Numeric field to compare against threshold value (for threshold rules)",
    )

    date_field_id = fields.Many2one(
        "ir.model.fields",
        string="Date Field",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('date', 'datetime'))]",
        help="Date/datetime field to check against days before (for date rules)",
    )

    comparison = fields.Selection(
        [
            ("lt", "Less Than (<)"),
            ("lte", "Less Than or Equal (<=)"),
            ("gt", "Greater Than (>)"),
            ("gte", "Greater Than or Equal (>=)"),
            ("eq", "Equal (=)"),
        ],
        string="Comparison",
        default="lt",
        help="How to compare the monitored field value against the threshold",
    )

    # Threshold configuration
    threshold_value = fields.Float(
        string="Threshold Value",
        help="Threshold value for comparison (e.g., minimum stock level, maximum days)",
        tracking=True,
    )

    days_before = fields.Integer(
        string="Days Before",
        default=0,
        help="Days before expiry/deadline to trigger alert (0 = at deadline)",
        tracking=True,
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

    alert_count = fields.Integer(
        string="Alert Count",
        compute="_compute_alert_count",
        help="Number of alerts created by this rule",
    )

    eval_as_user_id = fields.Many2one(
        "res.users",
        string="Evaluated As",
        readonly=True,
        help="User whose record-rule visibility bounds this rule's monitored search. "
        "Set to whoever last defined what the rule targets, so evaluation can never "
        "surface records the configurer cannot see. System-managed; not editable.",
    )
    # No Python `default` on purpose: a default would make Odoo's _init_column
    # backfill existing rows with the *upgrade* user on module update (before the
    # migration runs), and would let a client forge the value through a
    # `default_eval_as_user_id` context key via default_get. The identity is set
    # explicitly in create() instead, and the migration backfills existing rows.

    # Fields that define what a rule reads or which records it surfaces. Changing
    # any of them re-binds the evaluation identity to the editor (see write), so a
    # rule can never be repointed — by model, domain, field, type, threshold, or by
    # (re)activation — to surface records its editor is not allowed to see.
    _EVAL_TARGETING_FIELDS = (
        "model_id",
        "domain_filter",
        "monitored_field_id",
        "date_field_id",
        "rule_type",
        "comparison",
        "threshold_value",
        "days_before",
        "active",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Force the evaluation identity to the creator; it is never client-supplied.

        Setting the key explicitly (rather than popping it) keeps the field present
        in vals so Odoo's default_get — which honours a client `default_eval_as_user_id`
        context key — is never consulted for it.
        """
        vals_list = [dict(vals, eval_as_user_id=self.env.uid) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        """Re-bind the evaluation identity to the editor when targeting changes.

        eval_as_user_id is never client-writable directly; it tracks whoever last
        defined what the rule targets, so record rules bound the monitored search
        to that user's visibility regardless of the elevated cron that runs it. Note
        the identity is `self.env.uid` (the acting user, preserved even under
        `sudo()`); an explicit `with_user(<elevated>)` write would re-widen scope,
        which is why only trusted internal callers should do that.
        """
        if "eval_as_user_id" in vals or any(field in vals for field in self._EVAL_TARGETING_FIELDS):
            vals = dict(vals)
            vals.pop("eval_as_user_id", None)
            if any(field in vals for field in self._EVAL_TARGETING_FIELDS):
                vals["eval_as_user_id"] = self.env.uid
        return super().write(vals)

    def _compute_alert_count(self):
        """Compute the number of alerts associated with each rule."""
        alert_data = self.env["spp.alert"].read_group(
            [("rule_id", "in", self.ids)],
            ["rule_id"],
            ["rule_id"],
        )
        count_map = {d["rule_id"][0]: d["rule_id_count"] for d in alert_data}
        for rule in self:
            rule.alert_count = count_map.get(rule.id, 0)

    def action_view_alerts(self):
        """Open list view of alerts created by this rule."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Alerts"),
            "res_model": "spp.alert",
            "view_mode": "list,form",
            "domain": [("rule_id", "=", self.id)],
            "context": {"default_rule_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains("rule_type", "model_id", "monitored_field_id", "date_field_id")
    def _check_rule_configuration(self):
        """Validate that rule has required fields based on rule_type."""
        for rule in self:
            if not rule.rule_type:
                continue
            if not rule.model_id:
                raise ValidationError(_("A monitored model is required when rule type is set."))
            if rule.rule_type == "threshold" and not rule.monitored_field_id:
                raise ValidationError(_("A monitored field is required for threshold rules."))
            if rule.rule_type == "date" and not rule.date_field_id:
                raise ValidationError(_("A date field is required for date rules."))

    def _domain_eval_context(self):
        """Return the safe_eval context used when parsing domain filter expressions."""
        return {
            "datetime": safe_eval.datetime,
            "dateutil": safe_eval.dateutil,
            "time": safe_eval.time,
            "uid": self.env.uid,
        }

    @api.constrains("domain_filter")
    def _check_domain_filter(self):
        """Validate that domain_filter is a parseable Odoo domain expression."""
        for rule in self:
            if not rule.domain_filter or rule.domain_filter.strip() == "[]":
                continue
            try:
                result = safe_eval.safe_eval(  # nosemgrep: odoo-unsafe-safe-eval
                    rule.domain_filter, self._domain_eval_context()
                )
                if not isinstance(result, list):
                    raise ValidationError(_("Domain filter must be a list, got %s.", type(result).__name__))
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError(_("Invalid domain filter: %s", e)) from e

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_evaluate(self):
        """Evaluate this rule immediately (Run Now button handler)."""
        self.ensure_one()
        if not self.rule_type:
            raise UserError(_("Cannot evaluate rule '%s': no rule type is configured.", self.name))
        if not self.model_id:
            raise UserError(_("Cannot evaluate rule '%s': no model to monitor is configured.", self.name))

        try:
            count = self._evaluate_rule()
        except Exception as e:
            raise UserError(_("Error evaluating rule '%(rule)s': %(error)s", rule=self.name, error=e)) from e

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Rule Evaluated"),
                "message": _(
                    "%(count)d alert(s) created by rule '%(rule)s'.",
                    count=count,
                    rule=self.name,
                ),
                "type": "success" if count > 0 else "info",
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # Rule Evaluation Engine
    # -------------------------------------------------------------------------

    def _evaluate_rule(self):
        """Evaluate a single rule and create alerts for matching records.

        Returns:
            int: Number of alerts created
        """
        self.ensure_one()

        if not self.rule_type or not self.model_id or not self.active:
            return 0

        model_name = self.model_id.model

        try:
            Model = self.env[model_name]
        except KeyError:
            _logger.warning("Alert rule '%s' (ID: %d): model '%s' not found, skipping.", self.name, self.id, model_name)
            return 0

        # Evaluate the monitored search as the user who configured what the rule
        # targets (eval_as_user_id), not the elevated cron/superuser identity that
        # may be triggering the run. Record rules are then enforced against the
        # configurer, so a non-admin cannot surface — and leak, via alerts readable
        # by all managers — records they are not allowed to see. eval_as_user_id is
        # system-managed (re-bound to the editor on any targeting change) and never
        # client-writable, so it cannot be forged to escalate. create_uid is the
        # fallback for rows predating this field.
        eval_user = self.eval_as_user_id or self.create_uid
        if not eval_user:
            # Fail closed: without a resolvable configurer we must not fall back to
            # the elevated cron identity, which would search with record rules bypassed.
            _logger.warning(
                "Alert rule '%s' (ID: %d): no evaluation user resolved; skipping to avoid an elevated search.",
                self.name,
                self.id,
            )
            return 0
        # Bind to the configurer AND their own company scope, so multi-company record
        # rules apply as they would for that user — not as the triggering cron's
        # default company. eval_user is a system-managed field, not client input.
        Model = Model.with_user(eval_user.id).with_context(  # nosemgrep: odoo-with-user-unvalidated
            allowed_company_ids=eval_user.company_ids.ids or eval_user.company_id.ids
        )

        # Parse domain filter
        try:
            domain = safe_eval.safe_eval(  # nosemgrep: odoo-unsafe-safe-eval
                self.domain_filter or "[]", self._domain_eval_context()
            )
        except Exception as e:
            _logger.error("Alert rule '%s' (ID: %d): invalid domain filter: %s", self.name, self.id, e)
            return 0

        records = Model.search(domain)
        if not records:
            return 0

        if self.rule_type == "threshold":
            return self._evaluate_threshold(records, model_name)
        if self.rule_type == "date":
            return self._evaluate_date(records, model_name)

        return 0

    def _evaluate_threshold(self, records, model_name):
        """Evaluate threshold rule against records.

        Args:
            records: Recordset of records to check
            model_name: Technical model name string

        Returns:
            int: Number of alerts created
        """
        field_name = self.monitored_field_id.name
        compare = COMPARISON_OPERATORS.get(self.comparison, op.lt)

        # Batch-fetch existing alerts to avoid N+1 queries
        existing = self._get_existing_alert_keys(model_name, records.ids)

        alerts_to_create = []
        # Performance note: iterates records in Python. For very large recordsets (10k+),
        # consider batch-reading field values via mapped() or read().
        for record in records:
            if record.id in existing:
                continue

            current_value = record[field_name]
            if compare(current_value, self.threshold_value):
                existing.add(record.id)
                alerts_to_create.append(self._prepare_alert_vals(record, model_name, current_value=current_value))

        if alerts_to_create:
            self.env["spp.alert"].create(alerts_to_create)

        return len(alerts_to_create)

    def _evaluate_date(self, records, model_name):
        """Evaluate date rule against records.

        Args:
            records: Recordset of records to check
            model_name: Technical model name string

        Returns:
            int: Number of alerts created
        """
        field_name = self.date_field_id.name
        today = fields.Date.today()

        # Batch-fetch existing alerts to avoid N+1 queries
        existing = self._get_existing_alert_keys(model_name, records.ids)

        alerts_to_create = []
        # Performance note: iterates records in Python. For very large recordsets (10k+),
        # consider batch-reading field values via mapped() or read().
        for record in records:
            if record.id in existing:
                continue

            date_value = record[field_name]
            if not date_value:
                continue

            # Handle datetime fields by converting to date
            if isinstance(date_value, datetime):
                date_value = date_value.date()

            days_until = (date_value - today).days

            if days_until <= self.days_before:
                existing.add(record.id)
                alerts_to_create.append(self._prepare_alert_vals(record, model_name, days_until=days_until))

        if alerts_to_create:
            self.env["spp.alert"].create(alerts_to_create)

        return len(alerts_to_create)

    def _get_existing_alert_keys(self, res_model, record_ids):
        """Batch-fetch existing active/acknowledged alerts for this rule.

        Args:
            res_model: Technical model name
            record_ids: List of record IDs to check

        Returns:
            set: Set of res_id values that already have alerts
        """
        if not record_ids:
            return set()

        existing_alerts = self.env["spp.alert"].search(
            [
                ("rule_id", "=", self.id),
                ("res_model", "=", res_model),
                ("res_id", "in", record_ids),
                ("state", "in", ("active", "acknowledged")),
            ]
        )
        return set(existing_alerts.mapped("res_id"))

    def _prepare_alert_vals(self, record, model_name, current_value=None, days_until=None):
        """Prepare values dict for creating an alert from this rule.

        Args:
            record: The source record that triggered the alert
            model_name: Technical model name
            current_value: Current numeric value (for threshold alerts)
            days_until: Days until date (for date alerts)

        Returns:
            dict: Values for spp.alert.create()
        """
        record_name = record.display_name or str(record.id)
        title = _("%(rule)s: %(record)s", rule=self.name, record=record_name)

        vals = {
            "rule_id": self.id,
            "alert_type_id": self.alert_type_id.id,
            "priority": self.priority,
            "title": title,
            "description": self.description or "",
            "res_model": model_name,
            "res_id": record.id,
        }

        if self.company_id:
            vals["company_id"] = self.company_id.id

        if current_value is not None:
            vals["current_value"] = current_value
            vals["threshold_value"] = self.threshold_value

        if days_until is not None:
            vals["days_until"] = days_until

        return vals

    # -------------------------------------------------------------------------
    # Cron
    # -------------------------------------------------------------------------

    # Cron runs as superuser (OdooBot), but each rule's monitored search is evaluated as
    # the rule's owner (see _evaluate_rule), so record rules still bound what a rule can
    # surface to whoever configured it — the elevated cron identity does not widen scope.
    @api.model
    def _cron_evaluate_rules(self):
        """Scheduled action to evaluate all active, configured rules."""
        _logger.info("Alert Rule Engine: Starting rule evaluation...")

        rules = self.search(
            [
                ("active", "=", True),
                ("rule_type", "!=", False),
                ("model_id", "!=", False),
            ]
        )

        total_alerts = 0
        for rule in rules:
            try:
                count = rule._evaluate_rule()
                if count:
                    _logger.info("Alert Rule Engine: Rule '%s' created %d alert(s).", rule.name, count)
                total_alerts += count
            except Exception:
                _logger.exception("Alert Rule Engine: Error evaluating rule '%s' (ID: %d).", rule.name, rule.id)

        _logger.info(
            "Alert Rule Engine: Evaluation complete. %d rule(s) checked, %d alert(s) created.",
            len(rules),
            total_alerts,
        )
