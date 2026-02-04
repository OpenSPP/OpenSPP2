import logging

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LogicTestRunner(models.Model):
    _name = "spp.studio.test.runner"
    _description = "Logic Test Runner"

    def run_all_tests(self, logic_id):
        """Run all tests for a logic and return summary.

        Args:
            logic_id: ID of the spp.cel.expression record

        Returns:
            dict: Test results summary with counts and details
        """
        logic = self.env["spp.cel.expression"].browse(logic_id)

        if not logic.exists():
            raise UserError(f"Logic with ID {logic_id} not found")

        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "details": [],
        }

        for test in logic.test_ids:
            try:
                test.action_run_test()
                results["total"] += 1

                if test.error_message:
                    results["errors"] += 1
                elif test.passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1

                results["details"].append(
                    {
                        "id": test.id,
                        "name": test.name,
                        "passed": test.passed,
                        "expected": test.expected_result,
                        "actual": test.actual_result,
                        "error": test.error_message,
                        "execution_log": test.execution_log,
                    }
                )

            except Exception as e:
                _logger.exception("Error running test ID %s", test.id)
                results["total"] += 1
                results["errors"] += 1
                results["details"].append(
                    {
                        "id": test.id,
                        "name": test.name,
                        "passed": False,
                        "expected": test.expected_result,
                        "actual": None,
                        "error": str(e),
                        "execution_log": f"Fatal error: {str(e)}",
                    }
                )

        return results

    def run_with_registrant(self, logic_id, registrant_id):
        """Run logic against a specific registrant and return detailed result.

        Args:
            logic_id: ID of the spp.cel.expression record
            registrant_id: ID of the res.partner (registrant) record

        Returns:
            dict: Detailed execution result with context and steps
        """
        logic = self.env["spp.cel.expression"].browse(logic_id)
        registrant = self.env["res.partner"].browse(registrant_id)

        if not logic.exists():
            raise UserError(f"Logic with ID {logic_id} not found")

        if not registrant.exists():
            raise UserError(f"Registrant with ID {registrant_id} not found")

        if not registrant.is_registrant:
            raise UserError(f"Partner '{registrant.name}' is not a registrant")

        if not logic.compiled_expression:
            raise UserError(f"Logic '{logic.name}' has no compiled expression")

        # Build context from registrant
        context = self._build_registrant_context(registrant)

        # Resolve variables in the expression (deferred resolution)
        resolver = self.env["spp.cel.variable.resolver"]
        resolution_result = resolver.resolve_for_evaluation(
            logic.compiled_expression,
            context_type=logic.context_type or "group",
        )
        resolved_expression = resolution_result.get("expression", logic.compiled_expression)

        # Execute and get step-by-step
        try:
            result, steps = self._execute_with_steps(resolved_expression, context)

            return {
                "result": result,
                "registrant_id": registrant.id,
                "registrant_name": registrant.name,
                "logic_id": logic.id,
                "logic_name": logic.name,
                "context": context,
                "steps": steps,
                "success": True,
                "error": None,
            }

        except Exception as e:
            _logger.exception(
                "Error executing logic %s against registrant ID=%s",
                logic.name,
                registrant.id,
            )
            return {
                "result": None,
                "registrant_id": registrant.id,
                "registrant_name": registrant.name,
                "logic_id": logic.id,
                "logic_name": logic.name,
                "context": context,
                "steps": [],
                "success": False,
                "error": str(e),
            }

    def _build_registrant_context(self, registrant):
        """Extract variable values from registrant.

        Args:
            registrant: res.partner record

        Returns:
            dict: Variable name -> value mapping
        """
        if not self.env["ir.model"].search([("model", "=", "spp.cel.variable")], limit=1):
            _logger.warning("spp.cel.variable model not found, returning empty context")
            return {}

        Variable = self.env["spp.cel.variable"]
        context = {}

        variables = Variable.search([("active", "=", True)])

        for var in variables:
            try:
                value = self._get_variable_value(var, registrant)
                if value is not None:
                    context[var.name] = value
            except Exception as e:
                _logger.warning(
                    "Error getting value for variable %s from registrant ID=%s: %s",
                    var.name,
                    registrant.id,
                    str(e),
                )
                # Continue with other variables even if one fails
                continue

        return context

    def _get_variable_value(self, variable, registrant):
        """Get value of a variable for a registrant.

        Args:
            variable: spp.cel.variable record
            registrant: res.partner record

        Returns:
            The variable value, or None if not available
        """
        if variable.source_type == "field":
            # Direct field access
            if not variable.source_field:
                _logger.warning(
                    "Variable %s has source_type='field' but no source_field",
                    variable.name,
                )
                return None

            try:
                # Check if field exists on registrant
                if hasattr(registrant, variable.source_field):
                    value = getattr(registrant, variable.source_field)

                    # Handle Many2one fields - return the ID or name
                    if hasattr(value, "id"):
                        return value.id if value else None

                    return value
                else:
                    _logger.warning(
                        "Field %s not found on registrant for variable %s",
                        variable.source_field,
                        variable.name,
                    )
                    return None

            except Exception:
                _logger.exception(
                    "Error accessing field %s for variable %s",
                    variable.source_field,
                    variable.name,
                )
                return None

        elif variable.source_type in (
            "vocabulary",
            "indicator",
            "scoring",
            "computed",
            "aggregate",
        ):
            # These variable types need CEL evaluation
            # Use the CEL service to evaluate the variable's expression
            return self._evaluate_variable_via_cel(variable, registrant)

        else:
            _logger.warning(
                "Unknown source_type '%s' for variable %s",
                variable.source_type,
                variable.name,
            )
            return None

    def _evaluate_variable_via_cel(self, variable, registrant):
        """Evaluate a variable using the CEL service.

        For vocabulary, indicator, scoring, computed, and aggregate variables,
        we need to evaluate their CEL expression using the full CEL engine.

        Args:
            variable: spp.cel.variable record
            registrant: res.partner record

        Returns:
            The evaluated value, or None if evaluation fails
        """
        if not variable.cel_expression:
            _logger.debug(
                "Variable %s (source_type=%s) has no cel_expression",
                variable.name,
                variable.source_type,
            )
            return None

        # Check if CEL service is available
        if not self.env["ir.model"].search([("model", "=", "spp.cel.service")], limit=1):
            _logger.debug("CEL service not available for variable ID %s", variable.id)
            return None

        try:
            cel_service = self.env["spp.cel.service"]

            # Build a minimal context with the registrant
            context = {"r": registrant, "registrant": registrant}

            # Add registrant fields to context for r.field access
            for field_name in registrant._fields:
                if not field_name.startswith("_"):
                    try:
                        context[f"r.{field_name}"] = getattr(registrant, field_name)
                    except Exception:
                        pass

            # Evaluate the variable's expression
            result = cel_service.evaluate_expression(variable.cel_expression, context)
            return result

        except Exception as e:
            _logger.debug(
                "CEL evaluation failed for variable %s: %s",
                variable.name,
                str(e),
            )
            return None

    def _execute_with_steps(self, expression, context):
        """Execute expression and return result with step-by-step breakdown.

        Args:
            expression: CEL expression string
            context: dict of variable values

        Returns:
            tuple: (result, steps) where steps is a list of execution step dicts
        """
        steps = []

        # Try to use CEL service if available
        if self.env["ir.model"].search([("model", "=", "spp.cel.service")], limit=1):
            try:
                cel_service = self.env["spp.cel.service"]
                result = cel_service.evaluate_expression(expression, context)

                steps.append(
                    {
                        "expression": expression,
                        "result": result,
                        "type": "cel_evaluation",
                    }
                )

                return result, steps

            except Exception as e:
                _logger.exception("CEL service execution failed")
                steps.append(
                    {
                        "expression": expression,
                        "error": str(e),
                        "type": "cel_error",
                    }
                )
                raise

        # CEL service is required for evaluation
        error_msg = (
            "CEL service (spp.cel.service) is not available. " "Please install and configure the spp_cel_domain module."
        )
        _logger.error(error_msg)
        steps.append(
            {
                "expression": expression,
                "error": error_msg,
                "type": "missing_cel_service",
            }
        )
        raise UserError(error_msg)

    @api.model
    def run_batch_tests(self, logic_ids):
        """Run all tests for multiple logic records.

        Args:
            logic_ids: List of spp.cel.expression IDs

        Returns:
            dict: Results for each logic
        """
        results = {}

        for logic_id in logic_ids:
            try:
                logic_results = self.run_all_tests(logic_id)
                logic = self.env["spp.cel.expression"].browse(logic_id)
                results[logic_id] = {
                    "logic_name": logic.name if logic.exists() else f"Unknown (ID: {logic_id})",
                    "results": logic_results,
                }
            except Exception as e:
                _logger.exception("Error running tests for logic %s", logic_id)
                results[logic_id] = {
                    "logic_name": f"Error (ID: {logic_id})",
                    "error": str(e),
                    "results": None,
                }

        return results
