# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import ast
import logging
import operator
import types

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SafeBeneficiaryProxy:
    """Safe proxy for beneficiary access in CEL quantity formulas.

    Only exposes specific fields needed for entitlement calculations.
    Prevents access to env, sudo(), write(), and other dangerous methods.
    """

    def __init__(self, partner):
        self._partner = partner

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(f"Access to private attributes not allowed: {name}")

        if name in ("env", "sudo", "write", "create", "unlink", "search", "browse"):
            raise AttributeError(f"Access to '{name}' not allowed in quantity formulas")

        # Get the actual field value
        value = getattr(self._partner, name, None)

        # Don't allow accessing recordsets or methods
        if callable(value):
            raise AttributeError(f"Method calls not allowed: {name}")

        # Allow numeric and string values
        if isinstance(value, int | float | str | bool | types.NoneType):
            return value

        # For many2one fields, return the ID or a safe value
        if hasattr(value, "id"):
            return value.id

        return None


class _CelExpressionEvaluator(ast.NodeVisitor):
    """Restricted evaluator for CEL-style quantity/condition expressions.

    Supports:
    - arithmetic: +, -, *, /, //, %, **
    - boolean ops: and, or, not
    - comparisons: ==, !=, <, <=, >, >=
    - conditional expression: a if cond else b
    - names from provided context (e.g., me, base_quantity)
    - attribute access (delegated to SafeBeneficiaryProxy)
    - calls to allowed math/utility functions (min, max, abs, round, int, float)
    """

    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    _UNARY_OPS = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
        ast.Not: operator.not_,
    }

    _BOOL_OPS = {
        ast.And: all,
        ast.Or: any,
    }

    _CMP_OPS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    _ALLOWED_FUNCS = {"min", "max", "abs", "round", "int", "float"}

    def __init__(self, context):
        self.context = context

    def visit(self, node):
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_Constant(self, node):  # Python 3.8+
        return node.value

    def visit_Name(self, node):
        if node.id not in self.context:
            raise ValueError(f"Unknown variable '{node.id}' in CEL expression")
        return self.context[node.id]

    def visit_Attribute(self, node):
        value = self.visit(node.value)
        return getattr(value, node.attr)

    def visit_BinOp(self, node):
        op_type = type(node.op)
        if op_type not in self._BIN_OPS:
            raise ValueError(f"Operator '{op_type.__name__}' not allowed in CEL expression")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return self._BIN_OPS[op_type](left, right)

    def visit_UnaryOp(self, node):
        op_type = type(node.op)
        if op_type not in self._UNARY_OPS:
            raise ValueError(f"Unary operator '{op_type.__name__}' not allowed in CEL expression")
        operand = self.visit(node.operand)
        return self._UNARY_OPS[op_type](operand)

    def visit_BoolOp(self, node):
        op_type = type(node.op)
        if op_type not in self._BOOL_OPS:
            raise ValueError(f"Boolean operator '{op_type.__name__}' not allowed in CEL expression")
        values = [self.visit(v) for v in node.values]
        if op_type is ast.And:
            return all(values)
        if op_type is ast.Or:
            return any(values)
        return self._BOOL_OPS[op_type](values)

    def visit_Compare(self, node):
        left = self.visit(node.left)
        result = True
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            op_type = type(op)
            if op_type not in self._CMP_OPS:
                raise ValueError(f"Comparison operator '{op_type.__name__}' not allowed in CEL expression")
            right = self.visit(comparator)
            if not self._CMP_OPS[op_type](left, right):
                result = False
                break
            left = right
        return result

    def visit_IfExp(self, node):
        condition = self.visit(node.test)
        return self.visit(node.body if condition else node.orelse)

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed in CEL expressions")
        func_name = node.func.id
        if func_name not in self._ALLOWED_FUNCS:
            raise ValueError(f"Function '{func_name}' is not allowed in CEL expressions")
        func = self.context.get(func_name)
        if func is None:
            raise ValueError(f"Function '{func_name}' not found in evaluation context")
        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}
        return func(*args, **kwargs)

    def generic_visit(self, node):
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def _eval_cel_expression(expression, eval_context):
    """Safely evaluate a CEL-style expression using a restricted AST evaluator."""
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValidationError(_("Invalid CEL expression syntax: %s") % e) from e

    evaluator = _CelExpressionEvaluator(eval_context)
    return evaluator.visit(parsed)


class SPPInKindEntitlementItemCEL(models.Model):
    """Extend in-kind entitlement item to support CEL quantity expressions."""

    _inherit = "spp.program.entitlement.manager.inkind.item"

    # Mode selection: fixed quantity or CEL formula
    quantity_mode = fields.Selection(
        selection=[
            ("fixed", "Fixed Quantity"),
            ("cel", "CEL Formula"),
        ],
        string="Quantity Mode",
        default="fixed",
        required=True,
        help="Choose how to calculate the item quantity:\n"
        "- Fixed Quantity: Use a fixed quantity with optional multiplier\n"
        "- CEL Formula: Use a dynamic formula based on beneficiary data",
    )

    # CEL expression for quantity calculation
    quantity_cel_expression = fields.Text(
        string="Quantity Formula",
        default=False,
        help="Write a formula to calculate the item quantity.\n\n"
        "Available variables:\n"
        "- me: The beneficiary record (access fields like me.household_size)\n"
        "- base_quantity: The fixed quantity field value\n\n"
        "Examples:\n"
        "- 5  (fixed quantity)\n"
        "- me.household_size * 2  (2 items per household member)\n"
        "- base_quantity + me.children_count  (base + extra per child)\n"
        "- min(me.household_size * 3, 20)  (per-member with cap)\n"
        "- 10 if me.is_woman_headed else 8  (conditional quantity)",
    )

    # Condition mode: domain or CEL
    condition_mode = fields.Selection(
        selection=[
            ("domain", "Domain Filter"),
            ("cel", "CEL Expression"),
        ],
        string="Condition Mode",
        default="domain",
        help="Choose how to filter eligible beneficiaries:\n"
        "- Domain Filter: Use standard Odoo domain syntax\n"
        "- CEL Expression: Use CEL for more complex conditions",
    )

    # CEL expression for condition
    condition_cel_expression = fields.Text(
        string="Condition Expression",
        default=False,
        help="Write a CEL expression to determine eligibility for this item.\n\n"
        "Must return True or False.\n\n"
        "Examples:\n"
        "- me.household_size >= 4  (large households only)\n"
        "- me.children_count > 0  (households with children)\n"
        "- me.is_woman_headed or me.has_disabled_member",
    )

    # Preview fields
    quantity_cel_preview = fields.Char(
        string="Formula Preview",
        compute="_compute_quantity_cel_preview",
        help="Sample calculation to verify the formula",
    )

    quantity_cel_is_valid = fields.Boolean(
        string="Formula Valid",
        compute="_compute_quantity_cel_preview",
    )

    quantity_cel_error = fields.Text(
        string="Formula Error",
        compute="_compute_quantity_cel_preview",
    )

    @api.depends(
        "quantity_cel_expression",
        "quantity",
        "quantity_mode",
        "entitlement_id.program_id",
    )
    def _compute_quantity_cel_preview(self):
        """Compute a preview of the CEL formula with sample data."""
        for rec in self:
            rec.quantity_cel_preview = ""
            rec.quantity_cel_is_valid = rec.quantity_mode == "fixed"
            rec.quantity_cel_error = ""

            if rec.quantity_mode != "cel" or not rec.quantity_cel_expression:
                continue

            try:
                # Get a sample beneficiary from the program
                sample_beneficiary = None
                if rec.entitlement_id and rec.entitlement_id.program_id:
                    memberships = self.env["spp.program.membership"].search(
                        [
                            ("program_id", "=", rec.entitlement_id.program_id.id),
                            ("state", "=", "enrolled"),
                        ],
                        limit=1,
                    )
                    if memberships:
                        sample_beneficiary = memberships[0].partner_id

                if sample_beneficiary:
                    # Calculate with actual beneficiary
                    try:
                        result = rec._calculate_cel_quantity(sample_beneficiary)
                        rec.quantity_cel_preview = _("Sample calculation → %(qty)d units") % {
                            "qty": result,
                        }
                        rec.quantity_cel_is_valid = True
                    except Exception as e:
                        rec.quantity_cel_error = _("Calculation error: %s") % str(e)
                else:
                    # No sample beneficiary, just validate syntax
                    try:
                        rec._validate_cel_expression()
                        rec.quantity_cel_preview = _("Formula syntax is valid (no sample beneficiary available)")
                        rec.quantity_cel_is_valid = True
                    except Exception as e:
                        rec.quantity_cel_error = _("Syntax error: %s") % str(e)

            except Exception as e:
                rec.quantity_cel_error = _("Error: %s") % str(e)
                _logger.exception("Error computing CEL quantity preview")

    def _validate_cel_expression(self):
        """Validate the CEL expression syntax without executing it."""
        self.ensure_one()
        if not self.quantity_cel_expression:
            raise ValidationError(_("Quantity formula is required when using CEL mode"))

        # Try to compile the expression
        try:
            compile(self.quantity_cel_expression, "<string>", "eval")
        except SyntaxError as e:
            raise ValidationError(_("Invalid Python expression: %s") % str(e)) from e

    def _calculate_cel_quantity(self, beneficiary):
        """Calculate the item quantity using the CEL expression.

        Args:
            beneficiary: res.partner record (the beneficiary)

        Returns:
            int: The calculated quantity

        Raises:
            UserError: If the formula evaluation fails
        """
        self.ensure_one()

        if self.quantity_mode != "cel":
            raise UserError(_("This method should only be called when quantity_mode is 'cel'"))

        if not self.quantity_cel_expression:
            raise UserError(_("Quantity formula is required"))

        try:
            # Use safe proxy to prevent access to dangerous methods
            safe_beneficiary = SafeBeneficiaryProxy(beneficiary)

            # Build evaluation context
            eval_context = {
                "me": safe_beneficiary,
                "base_quantity": int(self.quantity or 1),
                # Safe math functions
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
            }

            # Evaluate the expression using a restricted AST evaluator
            result = _eval_cel_expression(self.quantity_cel_expression, eval_context)

            # Ensure result is integer
            try:
                quantity = int(result)
            except (TypeError, ValueError) as e:
                raise UserError(
                    _("Formula must return an integer. Got: %s (type: %s)") % (result, type(result).__name__)
                ) from e

            # Ensure quantity is positive
            if quantity < 0:
                _logger.warning(
                    "CEL formula returned negative quantity (%s) for beneficiary_id=%s. Setting to 0.",
                    quantity,
                    beneficiary.id,
                )
                quantity = 0

            return quantity

        except ValidationError:
            raise
        except UserError:
            raise
        except Exception as e:
            _logger.exception(
                "Error evaluating CEL quantity formula for beneficiary_id=%s: %s",
                beneficiary.id,
                self.quantity_cel_expression,
            )
            raise UserError(
                _("Error calculating quantity: %(error)s")
                % {
                    "error": str(e),
                }
            ) from e

    def _evaluate_cel_condition(self, beneficiary):
        """Evaluate the CEL condition expression.

        Args:
            beneficiary: res.partner record (the beneficiary)

        Returns:
            bool: True if condition is met, False otherwise
        """
        self.ensure_one()

        if self.condition_mode != "cel" or not self.condition_cel_expression:
            return True  # No CEL condition means always eligible

        try:
            # Use safe proxy to prevent access to dangerous methods
            safe_beneficiary = SafeBeneficiaryProxy(beneficiary)

            # Build evaluation context
            eval_context = {
                "me": safe_beneficiary,
                "True": True,
                "False": False,
            }

            # Evaluate the expression using a restricted AST evaluator
            result = _eval_cel_expression(self.condition_cel_expression, eval_context)

            return bool(result)

        except Exception:
            _logger.exception(
                "Error evaluating CEL condition for beneficiary_id=%s: %s",
                beneficiary.id,
                self.condition_cel_expression,
            )
            return False  # Fail closed - condition not met if evaluation fails

    @api.constrains("quantity_mode", "quantity_cel_expression")
    def _check_cel_expression(self):
        """Validate the CEL expression when in CEL mode."""
        for rec in self:
            if rec.quantity_mode == "cel":
                rec._validate_cel_expression()


class SPPInKindEntitlementManagerCEL(models.Model):
    """Extend in-kind entitlement manager to support CEL quantity calculations."""

    _inherit = "spp.program.entitlement.manager.inkind"

    def prepare_entitlements(self, cycle, beneficiaries):
        """Override to support CEL quantity calculations and conditions.

        This method extends the parent to handle both fixed quantities and CEL formulas.
        """
        if not self.entitlement_item_ids:
            raise UserError(_("There are no items entered for this entitlement manager."))

        all_beneficiaries_ids = beneficiaries.mapped("partner_id.id")
        all_beneficiaries = {b.id: b for b in beneficiaries.mapped("partner_id")}

        for rec in self.entitlement_item_ids:
            # Determine which beneficiaries qualify for this item
            if rec.condition_mode == "cel" and rec.condition_cel_expression:
                # Use CEL condition evaluation
                beneficiaries_ids = []
                for bid in all_beneficiaries_ids:
                    beneficiary = all_beneficiaries.get(bid)
                    if beneficiary and rec._evaluate_cel_condition(beneficiary):
                        beneficiaries_ids.append(bid)
            elif rec.condition:
                # Use domain-based condition (original logic)
                domain = [("id", "in", all_beneficiaries_ids)]
                domain += self._safe_eval(rec.condition)
                beneficiaries_ids = self.env["res.partner"].search(domain).ids
            else:
                beneficiaries_ids = all_beneficiaries_ids.copy()

            # Check if single evaluation
            if self.is_evaluate_single_item:
                for bid in beneficiaries_ids:
                    if bid in all_beneficiaries_ids:
                        all_beneficiaries_ids.remove(bid)

            # Get beneficiaries_with_entitlements to prevent duplicates
            beneficiaries_with_entitlements = (
                self.env["spp.entitlement.inkind"]
                .search(
                    [
                        ("cycle_id", "=", cycle.id),
                        ("partner_id", "in", beneficiaries_ids),
                        ("inkind_item_id", "=", rec.id),
                    ]
                )
                .mapped("partner_id.id")
            )
            entitlements_to_create = [bid for bid in beneficiaries_ids if bid not in beneficiaries_with_entitlements]

            entitlement_start_validity = cycle.start_date
            entitlement_end_validity = cycle.end_date

            entitlements = []

            for beneficiary_id in entitlements_to_create:
                beneficiary = all_beneficiaries.get(beneficiary_id)
                if not beneficiary:
                    beneficiary = self.env["res.partner"].browse(beneficiary_id)

                # Calculate quantity based on mode
                if rec.quantity_mode == "cel":
                    # Use CEL formula
                    try:
                        quantity = rec._calculate_cel_quantity(beneficiary)
                        _logger.debug(
                            "CEL quantity for beneficiary_id=%s: %s (formula: %s)",
                            beneficiary_id,
                            quantity,
                            rec.quantity_cel_expression,
                        )
                    except Exception as e:
                        _logger.error(
                            "Failed to calculate CEL quantity for beneficiary_id=%s: %s. Skipping.",
                            beneficiary_id,
                            str(e),
                        )
                        # Skip this beneficiary if formula fails
                        continue
                else:
                    # Use fixed quantity with multiplier (original logic)
                    multiplier = 1
                    if rec.multiplier_field:
                        multiplier = beneficiary.mapped(rec.multiplier_field.name)
                        if multiplier:
                            multiplier = multiplier[0] or 1
                    if rec.max_multiplier > 0 and multiplier > rec.max_multiplier:
                        multiplier = rec.max_multiplier
                    quantity = multiplier * rec.quantity

                # Skip if quantity is 0 or negative
                if quantity <= 0:
                    continue

                entitlement_fields = {
                    "cycle_id": cycle.id,
                    "partner_id": beneficiary_id,
                    "total_amount": rec.product_id.list_price * quantity,
                    "product_id": rec.product_id.id,
                    "quantity": quantity,
                    "unit_price": rec.product_id.list_price,
                    "uom_id": rec.uom_id.id,
                    "manage_inventory": self.manage_inventory,
                    "warehouse_id": self.warehouse_id and self.warehouse_id.id or None,
                    "inkind_item_id": rec.id,
                    "state": "draft",
                    "valid_from": entitlement_start_validity,
                    "valid_until": entitlement_end_validity,
                }

                # Check if there are additional fields to be added
                addl_fields = self._get_addl_entitlement_fields(beneficiary)
                if addl_fields:
                    entitlement_fields.update(addl_fields)

                entitlements.append(entitlement_fields)

            if entitlements:
                self.env["spp.entitlement.inkind"].create(entitlements)
