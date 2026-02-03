"""Extend approval definition with CEL expression support."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ApprovalDefinitionCEL(models.Model):
    """Extend approval definition to support CEL expressions."""

    _inherit = "spp.approval.definition"

    # CEL condition expression
    cel_condition = fields.Text(
        string="CEL Condition",
        help="""CEL expression that determines when this approval applies.

Available variables:
- record: The record being approved (with all fields)
- user: Current user submitting for approval
- company: Current company
- today: Current date
- now: Current datetime

Examples:
- record.amount > 10000
- record.state == "draft" && record.partner_id.id != 0
- record.total_amount > 5000 || record.category == "high_risk"
- size(record.line_ids.ids) > 10
        """,
    )

    is_cel_condition_valid = fields.Boolean(
        compute="_compute_cel_valid",
        store=False,
    )

    cel_condition_error = fields.Char(
        compute="_compute_cel_valid",
        store=False,
    )

    # CEL expression for dynamic reviewer assignment
    cel_reviewer_expression = fields.Text(
        string="CEL Reviewer Expression",
        help="""CEL expression that returns user ID(s) for dynamic reviewer assignment.

Available variables: Same as CEL Condition

Examples:
- record.manager_id.id
- record.department_id.manager_id.user_id.id
- [record.user_id.id, record.manager_id.id]

The expression should return:
- A single user ID (integer)
- A list of user IDs
        """,
    )

    is_cel_reviewer_valid = fields.Boolean(
        compute="_compute_cel_reviewer_valid",
        store=False,
    )

    cel_reviewer_error = fields.Char(
        compute="_compute_cel_reviewer_valid",
        store=False,
    )

    # Use CEL for conditions instead of domain
    use_cel_condition = fields.Boolean(
        string="Use CEL Condition",
        default=False,
        help="Use CEL expression instead of domain for condition evaluation",
    )

    # Use CEL for reviewer assignment
    use_cel_reviewer = fields.Boolean(
        string="Use CEL for Reviewers",
        default=False,
        help="Use CEL expression for dynamic reviewer assignment",
    )

    @api.depends("cel_condition")
    def _compute_cel_valid(self):
        evaluator = self.env["spp.cel.evaluator"]
        for record in self:
            if not record.cel_condition:
                record.is_cel_condition_valid = True
                record.cel_condition_error = False
            else:
                result = evaluator.validate(record.cel_condition)
                record.is_cel_condition_valid = result["valid"]
                record.cel_condition_error = result.get("error")

    @api.depends("cel_reviewer_expression")
    def _compute_cel_reviewer_valid(self):
        evaluator = self.env["spp.cel.evaluator"]
        for record in self:
            if not record.cel_reviewer_expression:
                record.is_cel_reviewer_valid = True
                record.cel_reviewer_error = False
            else:
                result = evaluator.validate(record.cel_reviewer_expression)
                record.is_cel_reviewer_valid = result["valid"]
                record.cel_reviewer_error = result.get("error")

    @api.constrains("cel_condition", "use_cel_condition")
    def _check_cel_condition(self):
        """Validate CEL condition expression."""
        evaluator = self.env["spp.cel.evaluator"]
        for record in self:
            if record.use_cel_condition and record.cel_condition:
                result = evaluator.validate(record.cel_condition)
                if not result["valid"]:
                    raise ValidationError(_("Invalid CEL condition: %(error)s") % {"error": result["error"]})

    @api.constrains("cel_reviewer_expression", "use_cel_reviewer")
    def _check_cel_reviewer(self):
        """Validate CEL reviewer expression."""
        evaluator = self.env["spp.cel.evaluator"]
        for record in self:
            if record.use_cel_reviewer and record.cel_reviewer_expression:
                result = evaluator.validate(record.cel_reviewer_expression)
                if not result["valid"]:
                    raise ValidationError(_("Invalid CEL reviewer expression: %(error)s") % {"error": result["error"]})

    def matches_record(self, record):
        """Check if this definition applies to a record.

        Extended to support CEL condition evaluation.

        FIX: Improved error handling - log errors and fail closed (return False)
        instead of silently returning True which could bypass approval.

        Args:
            record: The record to check

        Returns:
            bool: True if definition applies
        """
        self.ensure_one()

        # Use CEL condition if enabled
        if self.use_cel_condition and self.cel_condition:
            evaluator = self.env["spp.cel.evaluator"]
            try:
                return bool(evaluator.evaluate(self.cel_condition, record))
            except ValidationError:
                # Re-raise validation errors (invalid expression syntax)
                raise
            except Exception as e:
                # FIX: Log the error with context for debugging
                _logger.error(
                    "CEL condition evaluation failed for definition '%s' (ID: %s) " "on record %s (ID: %s): %s",
                    self.name,
                    self.id,
                    record._name,
                    record.id,
                    str(e),
                    exc_info=True,
                )
                # FIX: Fail closed - don't apply this definition on error
                # This prevents bypassing approval when CEL has bugs
                return False

        # Fall back to standard domain-based matching
        return super().matches_record(record)

    def get_approvers(self, record):
        """Get approvers for a record.

        Extended to support CEL-based dynamic reviewer assignment.

        FIX: Improved error handling - log errors instead of silently falling back.

        Args:
            record: The record being approved

        Returns:
            res.users recordset
        """
        self.ensure_one()

        # Use CEL reviewer expression if enabled
        if self.use_cel_reviewer and self.cel_reviewer_expression:
            evaluator = self.env["spp.cel.evaluator"]
            try:
                users = evaluator.evaluate_user_expression(self.cel_reviewer_expression, record)
                if users:
                    return users
                # If expression returns empty, fall back to standard approvers
                _logger.warning(
                    "CEL reviewer expression returned no users for definition '%s' "
                    "(ID: %s) on record %s (ID: %s). Falling back to standard approvers.",
                    self.name,
                    self.id,
                    record._name,
                    record.id,
                )
            except ValidationError:
                # Re-raise validation errors
                raise
            except Exception as e:
                # FIX: Log the error with context for debugging
                _logger.error(
                    "CEL reviewer expression failed for definition '%s' (ID: %s) "
                    "on record %s (ID: %s): %s. Falling back to standard approvers.",
                    self.name,
                    self.id,
                    record._name,
                    record.id,
                    str(e),
                    exc_info=True,
                )
                # Fall back to standard approvers on error

        # Fall back to standard approval type-based assignment
        return super().get_approvers(record)

    def action_test_cel_condition(self):
        """Action to test CEL condition (opens wizard)."""
        self.ensure_one()
        return {
            "name": _("Test CEL Condition"),
            "type": "ir.actions.act_window",
            "res_model": "spp.cel.test.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_definition_id": self.id,
                "default_expression": self.cel_condition,
                "default_expression_type": "condition",
            },
        }

    def action_test_cel_reviewer(self):
        """Action to test CEL reviewer expression (opens wizard)."""
        self.ensure_one()
        return {
            "name": _("Test CEL Reviewer Expression"),
            "type": "ir.actions.act_window",
            "res_model": "spp.cel.test.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_definition_id": self.id,
                "default_expression": self.cel_reviewer_expression,
                "default_expression_type": "reviewer",
            },
        }
