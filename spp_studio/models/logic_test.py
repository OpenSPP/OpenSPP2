import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LogicTest(models.Model):
    _name = "spp.studio.test"
    _description = "Logic Test Case"
    _order = "sequence, id"

    logic_id = fields.Many2one(
        "spp.cel.expression",
        string="Logic",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(
        string="Test Name",
        required=True,
        help="Descriptive name for this test case",
    )
    description = fields.Text(
        string="Description",
        help="Detailed description of what this test validates",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which tests are displayed and executed",
    )

    # Test Input
    input_type = fields.Selection(
        [
            ("persona", "Test Persona"),
            ("values", "Custom Values"),
            ("registrant", "Real Registrant"),
        ],
        string="Input Type",
        required=True,
        default="values",
        help="Source of input values for the test",
    )
    persona_id = fields.Many2one(
        "spp.studio.test.persona",
        string="Test Persona",
        help="Predefined persona with test values",
    )
    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        domain=[("is_registrant", "=", True)],
        help="Real registrant to test against",
    )
    custom_values = fields.Text(
        string="Custom Values",
        help="JSON object with variable values, e.g., {'income': 2500, 'hh_size': 4}",
    )

    # Expected Result
    expected_result = fields.Char(
        string="Expected Result",
        required=True,
        help="The expected outcome when running this test",
    )

    # Actual Result (computed, stored for history)
    actual_result = fields.Char(
        string="Actual Result",
        compute="_compute_result",
        store=True,
        help="The actual result from the most recent test run",
    )
    passed = fields.Boolean(
        string="Passed",
        compute="_compute_result",
        store=True,
        help="Whether the test passed (actual matches expected)",
    )
    execution_log = fields.Text(
        string="Execution Log",
        compute="_compute_result",
        store=True,
        help="Step-by-step explanation of the test execution",
    )
    last_run = fields.Datetime(
        string="Last Run",
        help="When this test was last executed",
    )
    error_message = fields.Char(
        string="Error Message",
        help="Error message if test execution failed",
    )
    result = fields.Selection(
        [
            ("pass", "Pass"),
            ("fail", "Fail"),
            ("error", "Error"),
            ("pending", "Pending"),
        ],
        string="Result",
        compute="_compute_result",
        store=True,
        help="Test result status",
    )

    @api.depends(
        "logic_id.compiled_expression",
        "input_type",
        "persona_id.values",
        "custom_values",
        "registrant_id",
        "expected_result",
    )
    def _compute_result(self):
        """Run the test and compute actual_result, passed, execution_log, result."""
        for test in self:
            # Skip if logic is not ready
            if not test.logic_id or not test.logic_id.compiled_expression:
                test.actual_result = False
                test.passed = False
                test.result = "pending"
                test.execution_log = "Logic expression not compiled"
                test.error_message = "No compiled expression available"
                continue

            try:
                # Get test context
                context = test._get_test_context()
                if context is None:
                    test.actual_result = False
                    test.passed = False
                    test.result = "error"
                    test.execution_log = "Failed to build test context"
                    test.error_message = "Invalid test input configuration"
                    continue

                # Execute the logic
                exec_result, steps = test._execute_logic(context)

                # Store results
                test.actual_result = str(exec_result) if exec_result is not None else "None"
                test.passed = test._compare_results(test.expected_result, test.actual_result)
                test.result = "pass" if test.passed else "fail"
                test.execution_log = test._format_execution_log(steps, context)
                test.error_message = False

            except Exception as e:
                _logger.exception("Error executing test ID %s", test.id)
                test.actual_result = False
                test.passed = False
                test.result = "error"
                test.execution_log = f"Execution failed: {str(e)}"
                test.error_message = str(e)

    def action_run_test(self):
        """Manually run this test and update results."""
        self.ensure_one()

        # Update last_run timestamp
        self.last_run = fields.Datetime.now()

        # Trigger recomputation
        self._compute_result()

        # Return a notification action
        if self.passed:
            message = "Test passed!"
        else:
            message = f"Test failed: expected '{self.expected_result}', " f"got '{self.actual_result}'"
        if self.error_message:
            message = f"Test error: {self.error_message}"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Test Result",
                "message": message,
                "type": "success" if self.passed else "danger",
                "sticky": False,
            },
        }

    def _get_test_context(self):
        """Build context dict from persona/values/registrant."""
        self.ensure_one()

        if self.input_type == "persona":
            if not self.persona_id:
                _logger.warning(
                    "Test %s: persona input type selected but no persona specified",
                    self.name,
                )
                return None
            return self.persona_id.get_values_dict()

        elif self.input_type == "values":
            if not self.custom_values:
                _logger.warning(
                    "Test %s: custom values input type selected but no values provided",
                    self.name,
                )
                return {}

            try:
                return json.loads(self.custom_values)
            except json.JSONDecodeError as e:
                _logger.error("Test ID %s: invalid JSON in custom_values: %s", self.id, str(e))
                return None

        elif self.input_type == "registrant":
            if not self.registrant_id:
                _logger.warning(
                    "Test %s: registrant input type selected but no registrant specified",
                    self.name,
                )
                return None

            # Use test runner to build registrant context
            runner = self.env["spp.studio.test.runner"]
            return runner._build_registrant_context(self.registrant_id)

        return None

    def _execute_logic(self, context):
        """Execute the logic with given context and return result with steps."""
        self.ensure_one()

        expression = self.logic_id.compiled_expression
        steps = []

        # Resolve variables in the expression (deferred resolution)
        resolver = self.env["spp.cel.variable.resolver"]
        resolution_result = resolver.resolve_for_evaluation(
            expression,
            context_type=self.logic_id.context_type or "group",
        )
        resolved_expression = resolution_result.get("expression", expression)

        # Try to use CEL service if available
        if self.env["ir.model"].search([("model", "=", "spp.cel.service")], limit=1):
            try:
                cel_service = self.env["spp.cel.service"]
                result = cel_service.evaluate_expression(resolved_expression, context)

                steps.append(
                    {
                        "expression": expression,
                        "resolved_expression": resolved_expression,
                        "result": result,
                        "type": "full_expression",
                    }
                )

                return result, steps
            except Exception as e:
                _logger.exception("CEL service execution failed for test ID %s", self.id)
                steps.append(
                    {
                        "expression": expression,
                        "error": str(e),
                        "type": "error",
                    }
                )
                raise

        # CEL service is required for evaluation
        error_msg = (
            "CEL service (spp.cel.service) is not available. " "Please install and configure the spp_cel_domain module."
        )
        _logger.error("CEL service not available for test ID %s", self.id)
        steps.append(
            {
                "expression": expression,
                "error": error_msg,
                "type": "missing_cel_service",
            }
        )
        raise UserError(error_msg)

    def _compare_results(self, expected, actual):
        """Compare expected and actual results, handling type conversion."""
        if expected is None or actual is None:
            return False

        # Convert both to strings for comparison
        expected_str = str(expected).strip().lower()
        actual_str = str(actual).strip().lower()

        # Direct comparison
        if expected_str == actual_str:
            return True

        # Try numeric comparison if both can be converted to numbers
        try:
            expected_num = float(expected_str)
            actual_num = float(actual_str)
            return abs(expected_num - actual_num) < 0.0001
        except (ValueError, TypeError):
            pass

        # Try boolean comparison
        if expected_str in ("true", "false"):
            expected_bool = expected_str == "true"
            actual_bool = actual_str == "true"
            return expected_bool == actual_bool

        return False

    def _format_execution_log(self, steps, context):
        """Format step-by-step explanation."""
        self.ensure_one()

        log_lines = [
            "=" * 60,
            f"Test: {self.name}",
            "=" * 60,
            "",
            "Input Context:",
        ]

        # Format context
        if context:
            for key, value in sorted(context.items()):
                log_lines.append(f"  {key}: {value}")
        else:
            log_lines.append("  (empty)")

        log_lines.extend(["", "Execution Steps:", ""])

        # Format steps
        for i, step in enumerate(steps, 1):
            step_type = step.get("type", "unknown")
            expression = step.get("expression", "")
            resolved_expression = step.get("resolved_expression", "")

            log_lines.append(f"Step {i} ({step_type}):")
            log_lines.append(f"  Expression: {expression}")
            if resolved_expression and resolved_expression != expression:
                log_lines.append(f"  Resolved:   {resolved_expression}")

            if "error" in step:
                log_lines.append(f"  Error: {step['error']}")
            else:
                result = step.get("result", "")
                log_lines.append(f"  Result: {result}")

            log_lines.append("")

        log_lines.extend(
            [
                "Final Result:",
                f"  Expected: {self.expected_result}",
                f"  Actual: {self.actual_result}",
                f"  Status: {'PASSED' if self.passed else 'FAILED'}",
                "",
                "=" * 60,
            ]
        )

        return "\n".join(log_lines)

    @api.constrains("input_type", "persona_id", "registrant_id", "custom_values")
    def _check_input_configuration(self):
        """Validate that appropriate input is provided based on input_type."""
        for test in self:
            if test.input_type == "persona" and not test.persona_id:
                raise ValidationError(f"Test '{test.name}': Persona input type requires a test persona to be selected.")
            if test.input_type == "registrant" and not test.registrant_id:
                raise ValidationError(
                    f"Test '{test.name}': Registrant input type requires a registrant to be selected."
                )
            if test.input_type == "values" and not test.custom_values:
                raise ValidationError(f"Test '{test.name}': Custom values input type requires values to be provided.")
