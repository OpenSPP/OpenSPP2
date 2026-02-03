"""CEL-based entitlement amount calculation.

This module extends the cash entitlement manager to support CEL expressions
for dynamic amount calculations based on beneficiary data.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class ValidationProxy:
    """Proxy for validation context that returns None for missing attributes.

    Used during CEL expression validation when we don't have a real record.
    Returns default values for any attribute access.
    """

    # Blocked attributes should raise errors during validation too
    _BLOCKED_ATTRS = frozenset(
        {
            "env",
            "sudo",
            "with_user",
            "with_context",
            "with_company",
            "write",
            "create",
            "unlink",
            "copy",
            "search",
            "browse",
        }
    )

    def __init__(self, data=None):
        object.__setattr__(self, "_data", data or {})

    def __getattr__(self, name):
        # Block private attributes
        if name.startswith("_"):
            raise AttributeError(f"Access to private attribute '{name}' not allowed")

        # Block dangerous methods - same as SafeRecordProxy
        if name in self._BLOCKED_ATTRS:
            raise AttributeError(f"Access to '{name}' not allowed in CEL formulas")

        data = object.__getattribute__(self, "_data")
        if name in data:
            value = data[name]
            if isinstance(value, dict):
                return ValidationProxy(value)
            return value
        # Return safe defaults for common field types
        return None

    def __setattr__(self, name, value):
        raise AttributeError("Setting attributes not allowed")

    @property
    def id(self):
        """Return a default ID for validation."""
        data = object.__getattribute__(self, "_data")
        return data.get("id", 1)


class SafeRecordProxy:
    """Safe proxy for ORM record access in CEL expressions.

    Provides controlled access to record fields while blocking dangerous methods
    like env, sudo(), write(), create(), unlink(), etc.

    This proxy is used by the CEL service to safely access beneficiary data
    in entitlement amount formulas.
    """

    # Methods and attributes that should never be accessible
    _BLOCKED_ATTRS = frozenset(
        {
            "env",
            "sudo",
            "with_user",
            "with_context",
            "with_company",
            "write",
            "create",
            "unlink",
            "copy",
            "search",
            "browse",
            "_cr",
            "_uid",
            "_context",
            "_cache",
            "_ids",
        }
    )

    def __init__(self, record):
        object.__setattr__(self, "_record", record)

    def __getattr__(self, name):
        # Block private attributes
        if name.startswith("_"):
            raise AttributeError(f"Access to private attribute '{name}' not allowed")

        # Block dangerous methods
        if name in self._BLOCKED_ATTRS:
            raise AttributeError(f"Access to '{name}' not allowed in CEL formulas")

        # Get the value from the wrapped record
        record = object.__getattribute__(self, "_record")
        try:
            value = getattr(record, name)
        except AttributeError:
            return None

        # Block callable methods
        if callable(value) and not isinstance(value, bool):
            raise AttributeError(f"Method calls not allowed: {name}")

        # Return safe scalar values directly
        if isinstance(value, int | float | str | bool | None):
            return value

        # For relational fields, return wrapped proxy or ID
        if hasattr(value, "_name"):  # It's a recordset
            if len(value) == 0:
                return None
            if len(value) == 1:
                return SafeRecordProxy(value)
            # For multiple records, return list of proxies
            return [SafeRecordProxy(r) for r in value]

        return value

    def __setattr__(self, name, value):
        raise AttributeError("Setting attributes not allowed in CEL formulas")

    @property
    def id(self):
        """Allow safe access to record ID."""
        return object.__getattribute__(self, "_record").id

    def __repr__(self):
        record = object.__getattribute__(self, "_record")
        return f"<SafeRecordProxy({record._name}, {record.id})>"


class SPPCashEntitlementItem(models.Model):
    """Extend cash entitlement item to support CEL amount expressions."""

    _inherit = "spp.program.entitlement.manager.cash.item"

    # Mode selection: CEL formula (default)
    amount_mode = fields.Selection(
        selection=[
            ("cel", "CEL Formula"),
        ],
        string="Amount Mode",
        default="cel",
        required=True,
        help="Calculate entitlement amount using CEL formulas based on beneficiary data.\n"
        "Examples:\n"
        "- 500 (fixed amount)\n"
        "- me.household_size * 100 (per-member amount)\n"
        "- base_amount * (1 + me.dependents_count * 0.1) (base + percentage)",
    )

    # CEL expression for amount calculation
    amount_cel_expression = fields.Text(
        string="Amount Formula",
        default=False,
        help="Write a formula to calculate the entitlement amount.\n\n"
        "Available variables:\n"
        "- me: The beneficiary record (access fields like me.household_size)\n"
        "- base_amount: The fixed amount field value\n\n"
        "Examples:\n"
        "- 500  (fixed amount)\n"
        "- me.household_size * 100  (per-member amount)\n"
        "- base_amount * (1 + me.dependents_count * 0.1)  (base + 10% per dependent)\n"
        "- min(me.children_count * 50, 500)  (per-child with cap)\n"
        "- base_amount if me.is_woman_headed else base_amount * 0.8  (conditional)",
    )

    # Preview of the CEL formula
    amount_cel_preview = fields.Char(
        string="Formula Preview",
        compute="_compute_amount_cel_preview",
        help="Sample calculation to verify the formula",
    )

    amount_cel_is_valid = fields.Boolean(
        string="Formula Valid",
        compute="_compute_amount_cel_preview",
    )

    amount_cel_error = fields.Text(
        string="Formula Error",
        compute="_compute_amount_cel_preview",
    )

    @api.depends("amount_cel_expression", "amount", "entitlement_id.program_id")
    def _compute_amount_cel_preview(self):
        """Compute a preview of the CEL formula with sample data."""
        for rec in self:
            rec.amount_cel_preview = ""
            rec.amount_cel_is_valid = False
            rec.amount_cel_error = ""

            if not rec.amount_cel_expression:
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
                        result = rec._calculate_cel_amount(sample_beneficiary)
                        rec.amount_cel_preview = _("Sample calculation → %(amount).2f %(currency)s") % {
                            "amount": result,
                            "currency": rec.currency_id.name or "",
                        }
                        rec.amount_cel_is_valid = True
                    except Exception as e:
                        rec.amount_cel_error = _("Calculation error: %s") % str(e)
                else:
                    # No sample beneficiary, just validate syntax
                    try:
                        rec._validate_cel_expression()
                        rec.amount_cel_preview = _("Formula syntax is valid (no sample beneficiary available)")
                        rec.amount_cel_is_valid = True
                    except Exception as e:
                        rec.amount_cel_error = _("Syntax error: %s") % str(e)

            except Exception as e:
                rec.amount_cel_error = _("Error: %s") % str(e)
                _logger.exception("Error computing CEL amount preview")

    def _validate_cel_expression(self):
        """Validate the CEL expression syntax using the CEL service."""
        self.ensure_one()
        if not self.amount_cel_expression:
            raise ValidationError(_("Amount formula is required when using CEL mode"))

        # Use CEL service for validation
        service = self.env["spp.cel.service"]
        try:
            # Test with dummy context to validate syntax
            # Use ValidationProxy to support attribute access like me.field_name
            context = {
                "me": ValidationProxy({"id": 1, "name": "Test", "active": True}),
                "base_amount": 100.0,
            }
            service.evaluate_expression(self.amount_cel_expression, context)
        except Exception as e:
            raise ValidationError(_("Invalid CEL expression: %s") % str(e)) from e

    def _calculate_cel_amount(self, beneficiary):
        """Calculate the entitlement amount using the CEL service.

        Args:
            beneficiary: res.partner record (the beneficiary)

        Returns:
            float: The calculated amount

        Raises:
            UserError: If the formula evaluation fails
        """
        import math

        self.ensure_one()

        if not self.amount_cel_expression:
            raise UserError(_("Amount formula is required"))

        try:
            # Use CEL service for expression evaluation
            service = self.env["spp.cel.service"]

            # Build context with safe record proxy
            context = {
                "me": SafeRecordProxy(beneficiary),
                "base_amount": float(self.amount or 0.0),
            }

            # Evaluate the expression using CEL service
            result = service.evaluate_expression(self.amount_cel_expression, context)

            # Ensure result is not None
            if result is None:
                raise UserError(_("Formula must return a number, got no result"))

            # Reject string results (they shouldn't be allowed even if numeric-looking)
            if isinstance(result, str):
                raise UserError(_("Formula must return a number, not a string. Got: '%s'") % result)

            # Convert to float
            try:
                amount = float(result)
            except (TypeError, ValueError) as e:
                raise UserError(
                    _("Formula must return a number. Got: %s (type: %s)") % (result, type(result).__name__)
                ) from e

            # Check for NaN and infinity
            if math.isnan(amount):
                raise UserError(_("Formula returned NaN (not a number)"))
            if math.isinf(amount):
                raise UserError(_("Formula returned infinity (division by zero?)"))

            # Ensure amount is non-negative
            if amount < 0:
                _logger.warning(
                    "CEL formula returned negative amount (%s) for beneficiary_id=%s. Setting to 0.",
                    amount,
                    beneficiary.id,
                )
                amount = 0.0

            return amount

        except ValidationError:
            raise
        except UserError:
            raise
        except Exception as e:
            _logger.exception(
                "Error evaluating CEL amount formula for beneficiary_id=%s: %s",
                beneficiary.id,
                self.amount_cel_expression,
            )
            raise UserError(
                _("Error calculating amount: %(error)s")
                % {
                    "error": str(e),
                }
            ) from e

    @api.constrains("amount_cel_expression")
    def _check_cel_expression(self):
        """Validate the CEL expression."""
        for rec in self:
            if rec.amount_cel_expression:
                rec._validate_cel_expression()


class SPPCashEntitlementManager(models.Model):
    """Extend cash entitlement manager to support CEL amount calculations."""

    _inherit = "spp.program.entitlement.manager.cash"

    def prepare_entitlements(self, cycle, beneficiaries):
        """Override to support CEL amount calculations.

        This method extends the parent to handle CEL formulas for amount calculation.
        """
        if not self.entitlement_item_ids:
            raise UserError(_("There are no items entered for this entitlement manager."))

        all_beneficiaries_ids = beneficiaries.mapped("partner_id.id")
        new_entitlements_to_create = {}

        for rec in self.entitlement_item_ids:
            # Determine which beneficiaries qualify for this item
            if rec.condition:
                beneficiaries_ids = self._get_all_beneficiaries(
                    all_beneficiaries_ids, rec.condition, self.evaluate_one_item
                )
            else:
                beneficiaries_ids = all_beneficiaries_ids

            _logger.info("Processing entitlement item %s for %d beneficiaries", rec.id, len(beneficiaries_ids))

            # Get beneficiaries who don't already have entitlements
            beneficiaries_with_entitlements = (
                self.env["spp.entitlement"]
                .search(
                    [
                        ("cycle_id", "=", cycle.id),
                        ("partner_id", "in", beneficiaries_ids),
                    ]
                )
                .mapped("partner_id.id")
            )
            entitlements_to_create = [
                beneficiaries_id
                for beneficiaries_id in beneficiaries_ids
                if beneficiaries_id not in beneficiaries_with_entitlements
            ]

            entitlement_start_validity = cycle.start_date
            entitlement_end_validity = cycle.end_date
            entitlement_currency = rec.currency_id.id

            beneficiaries_with_entitlements_to_create = self.env["res.partner"].browse(entitlements_to_create)

            for beneficiary_id in beneficiaries_with_entitlements_to_create:
                # Calculate amount using CEL formula
                try:
                    amount = rec._calculate_cel_amount(beneficiary_id)
                    _logger.debug(
                        "CEL amount for beneficiary_id=%s: %s (formula: %s)",
                        beneficiary_id.id,
                        amount,
                        rec.amount_cel_expression,
                    )
                except Exception as e:
                    _logger.error(
                        "Failed to calculate CEL amount for beneficiary_id=%s: %s. Skipping.",
                        beneficiary_id.id,
                        str(e),
                    )
                    # Skip this beneficiary if formula fails
                    continue

                # Compute the sum of cash entitlements
                if beneficiary_id.id in new_entitlements_to_create:
                    amount = amount + new_entitlements_to_create[beneficiary_id.id]["initial_amount"]

                # Check if amount > max_amount; ignore if max_amount is set to 0
                if self.max_amount > 0.0 and amount > self.max_amount:
                    amount = self.max_amount

                new_entitlements_to_create[beneficiary_id.id] = {
                    "cycle_id": cycle.id,
                    "partner_id": beneficiary_id.id,
                    "initial_amount": amount,
                    "currency_id": entitlement_currency,
                    "state": "draft",
                    "is_cash_entitlement": True,
                    "valid_from": entitlement_start_validity,
                    "valid_until": entitlement_end_validity,
                }

                # Check if there are additional fields to be added in entitlements
                addl_fields = self._get_addl_entitlement_fields(beneficiary_id)
                if addl_fields:
                    new_entitlements_to_create[beneficiary_id.id].update(addl_fields)

        # Create entitlement records
        for ent in new_entitlements_to_create:
            initial_amount = new_entitlements_to_create[ent]["initial_amount"]
            new_entitlements_to_create[ent]["initial_amount"] = self._check_subsidy(initial_amount)
            # Create non-zero entitlements only
            if new_entitlements_to_create[ent]["initial_amount"] > 0.0:
                self.env["spp.entitlement"].create(new_entitlements_to_create[ent])
