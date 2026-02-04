# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Expression - Core expression model for business rules.

This module provides the core expression model for defining business logic.
All expressions are stored as CEL strings (no simple mode).

UI extensions (versioning, testing, governance) are provided by spp_studio.
"""

import logging
import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CELExpression(models.Model):
    """CEL Expression - Core business rule definitions.

    Expressions define business logic as CEL strings:
    - Eligibility: "r.age >= 18 && r.income < poverty_line"
    - Benefit: "base_amount + (r.child_count * child_bonus)"
    - Compliance: "r.has_id_document && r.bank_verified"
    - Scoring: "r.pmt_score + (r.elderly_count * 0.1)"

    Following ADR-008, expressions use standardized prefixes:
    - r. for current record fields/variables
    - m. for member fields (inside aggregations)
    - No prefix for constants

    Note: Simple mode / conditions have been removed. All rules
    are expressed as CEL expressions. The Studio UI can provide
    wizards to help build expressions, but storage is always CEL.
    """

    _name = "spp.cel.expression"
    _description = "CEL Business Expression"
    _order = "sequence, name"

    # ═══════════════════════════════════════════════════════════════════════
    # IDENTITY
    # ═══════════════════════════════════════════════════════════════════════

    name = fields.Char(
        string="Name",
        required=True,
        index=True,
        help="Name of the expression definition",
    )
    code = fields.Char(
        string="Code",
        index=True,
        copy=False,
        help="Technical reference for API access (auto-generated if empty)",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CLASSIFICATION
    # ═══════════════════════════════════════════════════════════════════════

    expression_type = fields.Selection(
        selection=[
            ("filter", "Filter"),
            ("formula", "Formula"),
            ("scoring", "Scoring"),
            ("validation", "Data Validation"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
        default="filter",
        help="Primary purpose of this expression:\n"
        "- Filter: Boolean expressions for eligibility, conditions, compliance\n"
        "- Formula: Calculations for amounts, quantities, scores\n"
        "- Scoring: Ranking and prioritization\n"
        "- Validation: Data quality checks\n"
        "- Other: General purpose expressions",
    )
    category_id = fields.Many2one(
        comodel_name="spp.cel.variable.category",
        string="Category",
        index=True,
        help="Category for organizing templates (shared with variables)",
    )
    context_type = fields.Selection(
        selection=[
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Shared"),
        ],
        string="Context",
        default="group",
        help="Primary evaluation context for this expression",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order for display in lists",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # EXPRESSION
    # ═══════════════════════════════════════════════════════════════════════

    cel_expression = fields.Text(
        string="CEL Expression",
        required=False,
        help="The CEL expression defining this business rule",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # OUTPUT CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════

    output_type = fields.Selection(
        selection=[
            ("boolean", "Yes/No (Boolean)"),
            ("number", "Number"),
            ("string", "Text"),
            ("money", "Money Amount"),
        ],
        string="Output Type",
        default="boolean",
        required=True,
        help="Type of value this expression returns",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
        ],
        string="Status",
        default="draft",
        required=True,
        help="Current lifecycle state of the expression",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Inactive expressions are hidden",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # TEMPLATE CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════

    is_template = fields.Boolean(
        string="Available as Template",
        default=False,
        help="Show this expression in template selection lists (e.g., program wizard)",
    )
    is_locked = fields.Boolean(
        string="Locked When Used",
        default=False,
        help="When selected as a template, prevent modification in the target context",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # VARIABLES
    # ═══════════════════════════════════════════════════════════════════════

    variable_ids = fields.Many2many(
        comodel_name="spp.cel.variable",
        relation="spp_cel_expression_variable_rel",
        column1="expression_id",
        column2="variable_id",
        string="Variables Used",
        compute="_compute_variable_ids",
        store=True,
        help="Variables referenced in this expression",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("cel_expression")
    def _compute_variable_ids(self):
        """Find variables used in the expression."""
        Variable = self.env["spp.cel.variable"]
        for record in self:
            if not record.cel_expression:
                record.variable_ids = [Command.clear()]
                continue

            potential_vars = record._extract_potential_variables()
            if not potential_vars:
                record.variable_ids = [Command.clear()]
                continue

            found_vars = []
            for var_name in potential_vars:
                var = Variable.search(
                    ["|", ("cel_accessor", "=", var_name), ("name", "=", var_name)],
                    limit=1,
                )
                if var:
                    found_vars.append(var.id)

            record.variable_ids = [Command.set(found_vars)]

    def _extract_potential_variables(self):
        """Extract potential variable names from the CEL expression.

        Uses lexer-based tokenization when available, with regex fallback.

        Returns:
            set: Potential variable names
        """
        self.ensure_one()

        if not self.cel_expression:
            return set()

        try:
            from ..services.cel_parser import (
                CEL_CONTEXT_IDENTIFIERS,
                CEL_RESERVED_WORDS,
                PYTHON_BUILTINS,
                Lexer,
            )

            lexer = Lexer(self.cel_expression)
            tokens = lexer.tokens()
            potential_vars = {tok.value for tok in tokens if tok.kind == "IDENT"}

            # Filter out reserved words
            reserved = set()
            reserved.update(CEL_RESERVED_WORDS)
            reserved.update(PYTHON_BUILTINS)
            reserved.update(CEL_CONTEXT_IDENTIFIERS)

            return potential_vars - reserved

        except (ImportError, SyntaxError):
            # Fallback to regex
            _logger.debug("Lexer unavailable, using regex for variable extraction")
            var_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
            return set(re.findall(var_pattern, self.cel_expression))

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure expression code is unique."""
        for rec in self:
            if rec.code:
                duplicate = self.search_count(
                    [
                        ("code", "=", rec.code),
                        ("id", "!=", rec.id),
                    ]
                )
                if duplicate:
                    raise ValidationError(_("Expression code '%s' already exists.") % rec.code)

    @api.constrains("cel_expression")
    def _check_cel_expression_not_empty(self):
        """Ensure CEL expression is not empty for non-draft expressions."""
        for rec in self:
            if rec.state != "draft" and not rec.cel_expression:
                raise ValidationError(_("CEL expression is required for active expressions."))

    # ═══════════════════════════════════════════════════════════════════════
    # CRUD OVERRIDES
    # ═══════════════════════════════════════════════════════════════════════

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate code if not provided."""
        for vals in vals_list:
            if not vals.get("code") and vals.get("name"):
                # Generate code from name
                base_code = re.sub(r"[^a-z0-9]+", "_", vals["name"].lower())
                base_code = base_code.strip("_")

                # Ensure uniqueness
                code = base_code
                counter = 1
                while self.search_count([("code", "=", code)]) > 0:
                    code = f"{base_code}_{counter}"
                    counter += 1

                vals["code"] = code

        return super().create(vals_list)

    # ═══════════════════════════════════════════════════════════════════════
    # ACTION METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def action_activate(self):
        """Activate the expression."""
        for rec in self:
            if rec.state != "active":
                rec._validate_before_activation()
                rec.state = "active"

    def action_deactivate(self):
        """Deactivate the expression."""
        for rec in self:
            if rec.state != "inactive":
                rec.state = "inactive"

    def _validate_before_activation(self):
        """Validate expression before activation.

        Checks:
        - CEL expression is not empty
        - All referenced variables exist

        Raises:
            ValidationError: If validation fails
        """
        self.ensure_one()
        errors = []

        if not self.cel_expression:
            errors.append(_("CEL expression is required"))

        # Check for missing variables
        potential_vars = self._extract_potential_variables()
        Variable = self.env["spp.cel.variable"]

        missing = []
        for var_name in potential_vars:
            var = Variable.search(
                ["|", ("cel_accessor", "=", var_name), ("name", "=", var_name)],
                limit=1,
            )
            if not var:
                missing.append(var_name)

        if missing:
            errors.append(_("Missing variables: %s") % ", ".join(sorted(missing)))

        if errors:
            raise ValidationError("\n".join(errors))

    # ═══════════════════════════════════════════════════════════════════════
    # EVALUATION
    # ═══════════════════════════════════════════════════════════════════════

    def get_resolved_expression(self, program_id=None):
        """Get the expression with variables resolved.

        Uses the variable resolver to expand variable references
        into their actual CEL expressions.

        Args:
            program_id: Optional program ID for constant overrides

        Returns:
            str: Resolved CEL expression ready for evaluation
        """
        self.ensure_one()

        if not self.cel_expression:
            return ""

        try:
            resolver = self.env["spp.cel.variable.resolver"]
            result = resolver.resolve_for_evaluation(
                self.cel_expression,
                program_id=program_id,
                context_type=self.context_type or "group",
            )
            return result.get("expression", self.cel_expression)
        except Exception as e:
            _logger.warning("Failed to resolve expression ID %s: %s", self.id, str(e))
            return self.cel_expression
