import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_cel_domain.services.cel_parser import Lexer

_logger = logging.getLogger(__name__)

# System parameter key for governance mode (shared with Variable)
GOVERNANCE_PARAM = "spp_studio.governance_enabled"


class Logic(models.Model):
    """Business Logic Definition for OpenSPP.

    This model extends spp.cel.expression by reusing the same table (_name)
    and adding Studio-specific features:
    - Governance workflow (draft → pending → published → archived)
    - Versioning and version history
    - Test cases and test execution
    - Usage tracking
    - Approval workflow integration

    By using _name = "spp.cel.expression", this model shares the same database
    table as the parent model, avoiding duplication. All base CEL expression
    functionality (variables, expression parsing, etc.) is inherited directly.

    When governance is enabled (via system parameter), logic definitions
    require approval before publishing and cannot be edited once published.
    """

    _name = "spp.cel.expression"
    _inherit = ["spp.cel.expression", "mail.thread", "mail.activity.mixin"]
    _description = "Business Logic"
    _order = "sequence, name"

    @api.model
    def _is_governance_enabled(self):
        """Check if governance mode is enabled via system parameter."""
        # nosemgrep: odoo-sudo-without-context
        return self.env["ir.config_parameter"].sudo().get_param(GOVERNANCE_PARAM, "False").lower() == "true"

    def _check_governance_edit(self, vals):
        """Check if edit is allowed based on governance settings.

        When governance is enabled, published logic cannot be edited
        (except for state changes).
        """
        if not self._is_governance_enabled():
            return  # Governance disabled, allow all edits

        # Allow state changes
        allowed_fields = {"state", "expression_type"}
        for record in self:
            if record.state == "published" and not self.env.context.get("force_write"):
                if set(vals.keys()) - allowed_fields:
                    raise UserError(
                        _(
                            "Cannot modify published logic '%(name)s'. Create a new draft version to make changes.",
                            name=record.name,
                        )
                    )

    def write(self, vals):
        """Override write to enforce governance and update compiled expression.

        This method handles two concerns:
        1. Governance: Prevent edits to published logic when governance is enabled
        2. Expression updates: Regenerate compiled_expression when CEL expression changes
        """
        # Check governance first
        self._check_governance_edit(vals)

        # If CEL expression changes, update compiled expression after write
        if "cel_expression" in vals:
            result = super().write(vals)
            self._update_compiled_expression()
            return result

        return super().write(vals)

    # ═══════════════════════════════════════════════════════════════════════
    # IDENTITY (inherited from spp.cel.expression, with extensions)
    # ═══════════════════════════════════════════════════════════════════════

    # Override name to add tracking
    name = fields.Char(tracking=True)

    # Studio-specific field
    description = fields.Text(
        string="Description",
        help="What this logic does and its purpose",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CLASSIFICATION (inherited from spp.cel.expression, with extensions)
    # ═══════════════════════════════════════════════════════════════════════

    # expression_type is inherited from parent
    # Override to add tracking
    expression_type = fields.Selection(tracking=True)

    # Studio-specific field
    tag_ids = fields.Many2many(
        comodel_name="spp.vocabulary.code",
        relation="spp_studio_logic_tag_rel",
        column1="logic_id",
        column2="tag_id",
        string="Tags",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:logic-tags')]",
        help="Tags for organizing and filtering logic",
    )

    # Override context_type default to "individual" (parent defaults to "group")
    context_type = fields.Selection(
        default="individual",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # EXPRESSION (inherited from spp.cel.expression, with extensions)
    # ═══════════════════════════════════════════════════════════════════════

    # cel_expression is inherited from parent
    # Override: not required (draft logic can exist without expression),
    # add tracking, validation happens via _check_expression_required constraint
    cel_expression = fields.Text(required=False, tracking=True)

    # Studio-specific: compiled/published expression for versioning
    compiled_expression = fields.Text(
        string="Compiled Expression",
        readonly=True,
        help="The actual CEL expression used for evaluation (frozen on publish)",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT CONFIGURATION (inherited from spp.cel.expression, with extensions)
    # ═══════════════════════════════════════════════════════════════════════

    # output_type is inherited from parent
    # Override to add tracking
    output_type = fields.Selection(tracking=True)

    # Studio-specific field
    output_unit = fields.Char(
        string="Output Unit",
        help="Unit of measurement (e.g., USD, %, years)",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE (override state from parent for Studio governance workflow)
    # ═══════════════════════════════════════════════════════════════════════

    # Extend the shared spp.cel.expression.state with Studio's governance
    # states. Parent (spp_cel_domain) has: draft, active, inactive.
    # Studio adds: pending, published, archived.
    #
    # Use selection_add (NOT a full selection= override) so the base
    # lifecycle values are preserved. Replacing the selection drops "active"
    # /"inactive", which then breaks dependent modules whose data relies on
    # them (e.g. spp_programs eligibility templates created with
    # state="active") depending on module load order. selection_add unions
    # the two sets, so the result is load-order independent. Studio's own
    # views restrict the visible workflow states via statusbar_visible.
    state = fields.Selection(
        selection_add=[
            ("pending", "Pending Approval"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        ondelete={
            "pending": "set default",
            "published": "set default",
            "archived": "set default",
        },
        tracking=True,
        help="Current lifecycle state of the logic (Studio governance workflow)",
    )

    # Studio-specific field
    is_inline = fields.Boolean(
        string="Inline",
        default=False,
        help="Inline logic is embedded in a program/cycle, not reusable",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # VERSIONING (reusable logic only)
    # ═══════════════════════════════════════════════════════════════════════

    version = fields.Integer(
        string="Version",
        default=1,
        readonly=True,
        help="Current version number (incremented on each publish)",
    )
    version_ids = fields.One2many(
        comodel_name="spp.studio.version",
        inverse_name="logic_id",
        string="Version History",
        help="Historical versions of this logic",
    )
    published_expression = fields.Text(
        string="Published Expression",
        readonly=True,
        help="Frozen CEL expression from last publish",
    )
    published_date = fields.Datetime(
        string="Published Date",
        readonly=True,
        help="When this version was published",
    )
    published_by = fields.Many2one(
        comodel_name="res.users",
        string="Published By",
        readonly=True,
        ondelete="set null",
        help="User who published this version",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # TESTING
    # ═══════════════════════════════════════════════════════════════════════

    test_ids = fields.One2many(
        comodel_name="spp.studio.test",
        inverse_name="logic_id",
        string="Tests",
        help="Test cases for this logic",
    )
    test_pass_count = fields.Integer(
        string="Tests Passing",
        compute="_compute_test_results",
        store=True,
        help="Number of tests passing",
    )
    test_fail_count = fields.Integer(
        string="Tests Failing",
        compute="_compute_test_results",
        store=True,
        help="Number of tests failing",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLES
    # ═══════════════════════════════════════════════════════════════════════

    # Note: variable_ids removed - the CEL expression is the source of truth.
    # Use _get_potential_variables() to find variable references on-demand.

    missing_variables = fields.Text(
        string="Missing Variables",
        compute="_compute_missing_variables",
        store=False,
        help="Variable names used but not found in dictionary",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # USAGE TRACKING
    # ═══════════════════════════════════════════════════════════════════════

    usage_count = fields.Integer(
        string="Usage Count",
        compute="_compute_usage",
        store=False,
        help="Number of places where this logic is used",
    )
    usage_ids = fields.One2many(
        comodel_name="spp.studio.usage",
        inverse_name="logic_id",
        string="Usage References",
        help="Where this logic is being used",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    # Note: _check_code_unique is inherited from spp.cel.expression (no need to duplicate)

    @api.constrains("version")
    def _check_version_positive(self):
        """Ensure version is positive."""
        for rec in self:
            if rec.version <= 0:
                raise ValidationError(_("Version must be positive."))

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("test_ids.passed", "test_ids.error_message")
    def _compute_test_results(self):
        """Count passing and failing tests."""
        for record in self:
            if record.test_ids:
                passing = record.test_ids.filtered(lambda t: t.passed and not t.error_message)
                failing = record.test_ids.filtered(lambda t: not t.passed or t.error_message)
                record.test_pass_count = len(passing)
                record.test_fail_count = len(failing)
            else:
                record.test_pass_count = 0
                record.test_fail_count = 0

    def _get_potential_variables(self):
        """Extract potential variable names from CEL expression.

        Uses the CEL lexer to properly tokenize the expression, which correctly
        handles string literals, numbers, and other tokens. Only IDENT tokens
        are returned as potential variable names.

        Excludes:
        - Reserved words (CEL keywords, builtins, context identifiers)
        - Function calls (identifiers followed by parentheses)
        - Property accesses (identifiers preceded by a dot, e.g., r.birthdate)

        Returns:
            set: Potential variable names
        """
        self.ensure_one()

        # Get the expression to analyze
        cel_expr = self.cel_expression or self.compiled_expression or ""

        if not cel_expr:
            return set()

        # Use the variable resolver service to get reserved words dynamically
        resolver = self.env["spp.cel.variable.resolver"]
        reserved_words = resolver._get_reserved_words()

        try:
            lexer = Lexer(cel_expr)
            tokens = lexer.tokens()
            # Extract only IDENT tokens - these are the potential variable names
            # STRING, NUMBER, BOOL tokens are literals, not variables
            potential_vars = {tok.value for tok in tokens if tok.kind == "IDENT"}
        except SyntaxError:
            # Fall back to regex if lexer fails on malformed expressions
            _logger.debug("Lexer failed on expression, falling back to regex: %s", cel_expr)
            var_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
            potential_vars = set(re.findall(var_pattern, cel_expr))

        # Filter out reserved words, function calls, and property accesses
        filtered_vars = set()
        for var_name in potential_vars:
            # Skip reserved words
            if var_name in reserved_words or var_name.lower() in reserved_words:
                continue

            # Skip function calls (identifier followed by opening parenthesis)
            func_call_pattern = rf"\b{re.escape(var_name)}\s*\("
            if re.search(func_call_pattern, cel_expr):
                continue

            # Skip property accesses (identifier preceded by a dot, e.g., r.birthdate)
            # These are field accesses on objects, not standalone variables
            property_access_pattern = rf"\.{re.escape(var_name)}\b"
            if re.search(property_access_pattern, cel_expr):
                continue

            filtered_vars.add(var_name)

        return filtered_vars

    def _get_property_accesses(self):
        """Extract property accesses from CEL expression (e.g., r.birthdate, m.income).

        Returns:
            list: List of tuples (context_object, field_name) for property accesses
        """
        self.ensure_one()
        cel_expr = self.cel_expression or self.compiled_expression or ""
        if not cel_expr:
            return []

        # Pattern matches context.field (e.g., r.birthdate, m.income, hh.size)
        # Context objects: r (registrant), m (member), g/hh (group/household)
        property_pattern = r"\b([rgm]|hh)\.([a-zA-Z_][a-zA-Z0-9_]*)\b"
        return re.findall(property_pattern, cel_expr)

    def _validate_field_accesses(self):
        """Validate that field accesses refer to existing fields.

        Returns:
            list: List of invalid field access strings (e.g., "r.invalid_field")
        """
        self.ensure_one()
        property_accesses = self._get_property_accesses()
        if not property_accesses:
            return []

        # All context objects (r, m, g, hh) refer to res.partner
        partner_fields = set(self.env["res.partner"]._fields.keys())

        invalid_fields = []
        for context_obj, field_name in property_accesses:
            if field_name not in partner_fields:
                invalid_fields.append(f"{context_obj}.{field_name}")

        return invalid_fields

    @api.depends(
        "cel_expression",
        "compiled_expression",
        "context_type",
    )
    def _compute_missing_variables(self):
        """Find missing variables and invalid field accesses in the expression.

        Reports:
        1. Variables that don't exist in the variable registry
        2. Variables with incompatible context
        3. Field accesses that refer to non-existent fields (e.g., r.invalid_field)
        """
        Variable = self.env["spp.cel.variable"]
        for record in self:
            missing_items = []

            # Check for missing CEL variables
            potential_vars = record._get_potential_variables()
            for var_name in potential_vars:
                var = Variable.search(
                    ["|", ("cel_accessor", "=", var_name), ("name", "=", var_name)],
                    limit=1,
                )
                if not var:
                    missing_items.append(var_name)
                elif not record._is_variable_context_compatible(var):
                    missing_items.append(f"{var_name} (wrong context)")

            # Check for invalid field accesses (e.g., r.invalid_field)
            invalid_fields = record._validate_field_accesses()
            for invalid_field in invalid_fields:
                missing_items.append(f"{invalid_field} (field not found)")

            record.missing_variables = ", ".join(sorted(missing_items)) if missing_items else ""

    def _is_variable_context_compatible(self, variable):
        """Check if a variable is compatible with this logic's context.

        Args:
            variable: spp.cel.variable record

        Returns:
            bool: True if compatible, False otherwise
        """
        self.ensure_one()

        # If either is 'both', they're compatible
        if self.context_type == "both" or variable.applies_to == "both":
            return True

        # Otherwise must match exactly
        return self.context_type == variable.applies_to

    @api.depends("usage_ids")
    def _compute_usage(self):
        """Count where this logic is used."""
        for record in self:
            record.usage_count = len(record.usage_ids)

    # ═══════════════════════════════════════════════════════════════════════
    # COMPILATION METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _update_compiled_expression(self):
        """Update the compiled_expression field from cel_expression.

        This copies the current cel_expression to compiled_expression,
        which is used for versioning and freezing the expression on publish.
        """
        for record in self:
            record.compiled_expression = record.cel_expression

    # ═══════════════════════════════════════════════════════════════════════
    # VALIDATION METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _check_can_publish(self):
        """Validate logic before publishing.

        Raises:
            ValidationError: If logic cannot be published
        """
        self.ensure_one()

        errors = []

        # Must have a CEL expression
        if not self.cel_expression:
            errors.append(_("Logic must have a CEL expression"))

        # All tests must pass
        if self.test_fail_count > 0:
            errors.append(
                _(
                    "Cannot publish logic with failing tests (%s failing)",
                    self.test_fail_count,
                )
            )

        # No missing variables
        if self.missing_variables:
            errors.append(
                _(
                    "Cannot publish logic with missing variables: %s",
                    self.missing_variables,
                )
            )

        if errors:
            raise ValidationError("\n".join(errors))

    @api.constrains("cel_expression", "state")
    def _check_expression_required(self):
        """Ensure non-draft logic has a CEL expression."""
        for record in self:
            if record.state != "draft" and not record.cel_expression:
                raise ValidationError(_("Published logic must have a CEL expression"))

    # ═══════════════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def action_publish(self):
        """Publish the logic (freeze expression, create version).

        For reusable logic, this increments the version.
        For inline logic, this just marks as published.
        """
        for record in self:
            # Validate before publish
            record._check_can_publish()

            # Update compiled expression
            record._update_compiled_expression()

            if not record.is_inline:
                # Create version snapshot
                version_vals = {
                    "logic_id": record.id,
                    "version": record.version,
                    "cel_expression": record.compiled_expression,
                    "published_date": fields.Datetime.now(),
                    "published_by": self.env.user.id,
                    "state": "published",
                }

                self.env["spp.studio.version"].create(version_vals)

                # Update published fields
                record.write(
                    {
                        "published_expression": record.compiled_expression,
                        "published_date": fields.Datetime.now(),
                        "published_by": self.env.user.id,
                        "version": record.version + 1,
                        "state": "published",
                    }
                )
            else:
                # Inline logic - just publish without versioning
                record.write(
                    {
                        "published_expression": record.compiled_expression,
                        "published_date": fields.Datetime.now(),
                        "published_by": self.env.user.id,
                        "state": "published",
                    }
                )

            _logger.info(
                "Published logic %s (version %s) by user %s",
                record.name,
                record.version,
                self.env.user.name,
            )

    def action_archive(self):
        """Archive the logic (mark as no longer active)."""
        for record in self:
            if record.usage_count > 0:
                raise UserError(
                    _(
                        "Cannot archive logic '%s' because it is used in %s place(s). Remove all usages first.",
                        record.name,
                        record.usage_count,
                    )
                )
            record.state = "archived"
            _logger.info("Archived logic ID %s", record.id)

    def action_draft(self):
        """Create a new draft version from published logic.

        This allows editing a published logic by creating a new draft.
        """
        for record in self:
            if record.state != "published":
                raise UserError(_("Only published logic can be copied to draft"))

            # For reusable logic, we edit in place (new version on next publish)
            # For inline logic, we just set back to draft
            record.state = "draft"
            _logger.info("Created new draft from published logic ID %s", record.id)

    # Note: action_submit_for_approval, action_approve, action_reject are implemented
    # in LogicApproval which integrates with spp.approval.mixin for standardized workflow

    def action_test_all(self):
        """Run all tests for this logic and show results notification.

        Returns:
            dict: Notification action with test summary
        """
        self.ensure_one()

        if not self.test_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Tests"),
                    "message": _("This logic has no test cases defined."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Run all tests via test runner
        runner = self.env["spp.studio.test.runner"]
        results = runner.run_all_tests(self.id)

        # Build notification message
        total = results.get("total", 0)
        passed = results.get("passed", 0)
        failed = results.get("failed", 0)
        errors = results.get("errors", 0)

        if failed == 0 and errors == 0:
            message = _("All %s tests passed!", total)
            msg_type = "success"
        elif errors > 0:
            message = _(
                "%(passed)s/%(total)s passed, %(errors)s errors",
                passed=passed,
                total=total,
                errors=errors,
            )
            msg_type = "danger"
        else:
            message = _(
                "%(passed)s/%(total)s passed, %(failed)s failed",
                passed=passed,
                total=total,
                failed=failed,
            )
            msg_type = "warning"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Test Results"),
                "message": message,
                "type": msg_type,
                "sticky": failed > 0 or errors > 0,
            },
        }

    def action_view_tests(self):
        """Open the tests list for this logic."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Tests"),
            "res_model": "spp.studio.test",
            "view_mode": "list,form",
            "domain": [("logic_id", "=", self.id)],
            "context": {"default_logic_id": self.id},
        }

    def action_view_usage(self):
        """Open the usage list for this logic."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Usage"),
            "res_model": "spp.studio.usage",
            "view_mode": "list,form",
            "domain": [("logic_id", "=", self.id)],
        }

    def action_view_versions(self):
        """Open the version history for this logic."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Version History"),
            "res_model": "spp.studio.version",
            "view_mode": "list,form",
            "domain": [("logic_id", "=", self.id)],
        }

    def action_add_test(self):
        """Add a new test to this logic."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Test"),
            "res_model": "spp.studio.test",
            "view_mode": "form",
            "target": "new",
            "context": {"default_logic_id": self.id},
        }

    def action_install_missing_variables(self):
        """Open wizard to install missing variables.

        This action opens a wizard that shows all missing variables
        referenced in the logic expression and allows batch installation.
        """
        self.ensure_one()

        if not self.missing_variables:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Missing Variables"),
                    "message": _("All variables in this logic are already defined."),
                    "type": "info",
                    "sticky": False,
                },
            }

        return {
            "type": "ir.actions.act_window",
            "name": _("Install Missing Variables"),
            "res_model": "spp.studio.variable.install.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_logic_id": self.id},
        }

    # ═══════════════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════════════

    # Note: create() with auto-code generation is inherited from spp.cel.expression

    def unlink(self):
        """Prevent deletion of logic that is in use."""
        for record in self:
            if record.usage_count > 0:
                raise UserError(
                    _(
                        "Cannot delete logic '%s' because it is used in %s place(s). "
                        "Remove all usages first or archive the logic.",
                        record.name,
                        record.usage_count,
                    )
                )
        return super().unlink()

    # ═══════════════════════════════════════════════════════════════════════
    # UI HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def name_get(self):
        """Display name with version for published logic."""
        result = []
        for record in self:
            if record.state == "published" and not record.is_inline:
                name = f"{record.name} (v{record.version})"
            else:
                name = record.name
            result.append((record.id, name))
        return result
