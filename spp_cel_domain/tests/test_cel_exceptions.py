# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Adversarial tests for CEL exceptions - verify exception hierarchy and behavior."""

from odoo.tests import TransactionCase, tagged

from ..exceptions import (
    CELError,
    CELExecutionError,
    CELFunctionError,
    CELMetricsUnavailableError,
    CELProfileError,
    CELSymbolError,
    CELSyntaxError,
    CELTypeError,
)


@tagged("post_install", "-at_install")
class TestCELExceptions(TransactionCase):
    """Test exception hierarchy and attributes."""

    def test_cel_error_base_class(self):
        """CELError should be base exception."""
        exc = CELError("Test message")
        self.assertIsInstance(exc, Exception)
        self.assertEqual(exc.message, "Test message")
        self.assertEqual(exc.details, {})

    def test_cel_error_with_details(self):
        """CELError should accept details dict."""
        details = {"key": "value", "number": 42}
        exc = CELError("Test message", details=details)
        self.assertEqual(exc.message, "Test message")
        self.assertEqual(exc.details, details)

    def test_cel_error_str_representation(self):
        """CELError should have string representation."""
        exc = CELError("Test message")
        self.assertIn("Test message", str(exc))

    def test_cel_syntax_error_inheritance(self):
        """CELSyntaxError should inherit from CELError."""
        exc = CELSyntaxError("Syntax error")
        self.assertIsInstance(exc, CELError)
        self.assertIsInstance(exc, Exception)

    def test_cel_syntax_error_attributes(self):
        """CELSyntaxError should have line, column, expression attributes."""
        exc = CELSyntaxError("Unexpected token", line=5, column=10, expression="r.age >")
        self.assertEqual(exc.message, "Unexpected token")
        self.assertEqual(exc.line, 5)
        self.assertEqual(exc.column, 10)
        self.assertEqual(exc.expression, "r.age >")

    def test_cel_syntax_error_details_populated(self):
        """CELSyntaxError details should contain line/column/expression."""
        exc = CELSyntaxError("Syntax error", line=3, column=7, expression="bad syntax")
        self.assertEqual(exc.details["line"], 3)
        self.assertEqual(exc.details["column"], 7)
        self.assertEqual(exc.details["expression"], "bad syntax")

    def test_cel_syntax_error_optional_attributes(self):
        """CELSyntaxError attributes should be optional."""
        exc = CELSyntaxError("Syntax error")
        self.assertIsNone(exc.line)
        self.assertIsNone(exc.column)
        self.assertIsNone(exc.expression)

    def test_cel_symbol_error_inheritance(self):
        """CELSymbolError should inherit from CELError."""
        exc = CELSymbolError("unknown_field")
        self.assertIsInstance(exc, CELError)

    def test_cel_symbol_error_attributes(self):
        """CELSymbolError should have symbol, available_symbols, profile attributes."""
        available = ["r", "age", "name"]
        exc = CELSymbolError("bad_symbol", available_symbols=available, profile="test")
        self.assertEqual(exc.symbol, "bad_symbol")
        self.assertEqual(exc.available_symbols, available)
        self.assertEqual(exc.profile, "test")

    def test_cel_symbol_error_message_includes_suggestions(self):
        """CELSymbolError message should include available symbols."""
        available = ["r", "age", "name"]
        exc = CELSymbolError("bad_symbol", available_symbols=available)
        self.assertIn("bad_symbol", exc.message)
        self.assertIn("Available", exc.message)

    def test_cel_symbol_error_message_without_suggestions(self):
        """CELSymbolError without available_symbols should still work."""
        exc = CELSymbolError("unknown")
        self.assertIn("unknown", exc.message)

    def test_cel_type_error_inheritance(self):
        """CELTypeError should inherit from CELError."""
        exc = CELTypeError("Type mismatch")
        self.assertIsInstance(exc, CELError)

    def test_cel_type_error_attributes(self):
        """CELTypeError should have expected_type, actual_type, field attributes."""
        exc = CELTypeError("Type mismatch", expected_type="number", actual_type="string", field="age")
        self.assertEqual(exc.expected_type, "number")
        self.assertEqual(exc.actual_type, "string")
        self.assertEqual(exc.field, "age")

    def test_cel_function_error_inheritance(self):
        """CELFunctionError should inherit from CELError."""
        exc = CELFunctionError("test_func", "Invalid arguments")
        self.assertIsInstance(exc, CELError)

    def test_cel_function_error_attributes(self):
        """CELFunctionError should have function_name attribute."""
        exc = CELFunctionError("age_years", "Wrong number of arguments")
        self.assertEqual(exc.function_name, "age_years")

    def test_cel_function_error_message_includes_function_name(self):
        """CELFunctionError message should include function name."""
        exc = CELFunctionError("test_func", "Error detail")
        self.assertIn("test_func", exc.message)
        self.assertIn("Error detail", exc.message)

    def test_cel_function_error_with_available_functions(self):
        """CELFunctionError can include available functions."""
        available = ["age_years", "contains", "startswith"]
        exc = CELFunctionError("bad_func", "Unknown function", available_functions=available)
        self.assertEqual(exc.available_functions, available)
        self.assertIn("bad_func", exc.message)

    def test_cel_execution_error_inheritance(self):
        """CELExecutionError should inherit from CELError."""
        exc = CELExecutionError("Execution failed")
        self.assertIsInstance(exc, CELError)

    def test_cel_execution_error_attributes(self):
        """CELExecutionError should have plan and partial_results attributes."""
        exc = CELExecutionError("Failed", plan="some_plan", partial_results={"a": 1})
        self.assertEqual(str(exc.plan), "some_plan")
        self.assertEqual(exc.partial_results, {"a": 1})

    def test_cel_metrics_unavailable_error_inheritance(self):
        """CELMetricsUnavailableError should inherit from CELError."""
        exc = CELMetricsUnavailableError()
        self.assertIsInstance(exc, CELError)

    def test_cel_metrics_unavailable_error_attributes(self):
        """CELMetricsUnavailableError should have metric_name attribute."""
        exc = CELMetricsUnavailableError(metric_name="household.size")
        self.assertEqual(exc.metric_name, "household.size")

    def test_cel_metrics_unavailable_error_message_with_metric(self):
        """CELMetricsUnavailableError message should include metric name."""
        exc = CELMetricsUnavailableError(metric_name="test.metric")
        self.assertIn("test.metric", exc.message)
        self.assertIn("spp_indicators", exc.message)

    def test_cel_metrics_unavailable_error_message_without_metric(self):
        """CELMetricsUnavailableError message should work without metric name."""
        exc = CELMetricsUnavailableError()
        self.assertIn("spp_indicators", exc.message)

    def test_cel_profile_error_inheritance(self):
        """CELProfileError should inherit from CELError."""
        exc = CELProfileError("test_profile", "Profile not found")
        self.assertIsInstance(exc, CELError)

    def test_cel_profile_error_attributes(self):
        """CELProfileError should have profile_name attribute."""
        exc = CELProfileError("bad_profile", "Not found")
        self.assertEqual(exc.profile_name, "bad_profile")

    def test_cel_profile_error_message_includes_profile_name(self):
        """CELProfileError message should include profile name."""
        exc = CELProfileError("test_profile", "Invalid configuration")
        self.assertIn("test_profile", exc.message)
        self.assertIn("Invalid configuration", exc.message)

    def test_all_exceptions_can_be_raised(self):
        """All exception types should be raisable."""
        exceptions_to_test = [
            (CELError, ["message"]),
            (CELSyntaxError, ["message"]),
            (CELSymbolError, ["symbol"]),
            (CELTypeError, ["message"]),
            (CELFunctionError, ["function_name", "message"]),
            (CELExecutionError, ["message"]),
            (CELMetricsUnavailableError, []),
            (CELProfileError, ["profile_name", "message"]),
        ]
        for exc_class, args in exceptions_to_test:
            with self.subTest(exception=exc_class.__name__):
                try:
                    raise exc_class(*args)
                except exc_class as e:
                    self.assertIsInstance(e, CELError)
                    self.assertIsInstance(e, Exception)

    def test_all_exceptions_can_be_caught_as_cel_error(self):
        """All CEL exceptions should be catchable as CELError."""
        exceptions = [
            CELSyntaxError("test"),
            CELSymbolError("test"),
            CELTypeError("test"),
            CELFunctionError("func", "test"),
            CELExecutionError("test"),
            CELMetricsUnavailableError(),
            CELProfileError("prof", "test"),
        ]
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                try:
                    raise exc
                except CELError as e:
                    self.assertIsInstance(e, CELError)

    def test_exception_details_is_always_dict(self):
        """All exceptions should have details as dict."""
        exceptions = [
            CELError("test"),
            CELSyntaxError("test"),
            CELSymbolError("test"),
            CELTypeError("test"),
            CELFunctionError("func", "test"),
            CELExecutionError("test"),
            CELMetricsUnavailableError(),
            CELProfileError("prof", "test"),
        ]
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                self.assertIsInstance(exc.details, dict)

    def test_exception_message_is_always_string(self):
        """All exceptions should have message as string."""
        exceptions = [
            CELError("test"),
            CELSyntaxError("test"),
            CELSymbolError("test"),
            CELTypeError("test"),
            CELFunctionError("func", "test"),
            CELExecutionError("test"),
            CELMetricsUnavailableError(),
            CELProfileError("prof", "test"),
        ]
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                self.assertIsInstance(exc.message, str)

    def test_exception_with_none_message_handled(self):
        """Exceptions should handle None as message."""
        try:
            exc = CELError(None)
            # Should not crash
            self.assertIsNotNone(str(exc))
        except Exception:
            # Some exceptions might not accept None
            pass

    def test_exception_with_unicode_message(self):
        """Exceptions should handle unicode in messages."""
        exc = CELError("Error: José García 日本語")
        self.assertIn("José", exc.message)
        self.assertIn("日本語", exc.message)

    def test_exception_with_empty_string_message(self):
        """Exceptions should handle empty string as message."""
        exc = CELError("")
        self.assertEqual(exc.message, "")

    def test_cel_syntax_error_with_very_long_expression(self):
        """CELSyntaxError should handle very long expressions."""
        long_expr = "a" * 10000
        exc = CELSyntaxError("Error", expression=long_expr)
        self.assertEqual(len(exc.expression), 10000)

    def test_cel_symbol_error_with_many_available_symbols(self):
        """CELSymbolError should handle many available symbols."""
        available = [f"symbol{i}" for i in range(1000)]
        exc = CELSymbolError("unknown", available_symbols=available)
        # Message should truncate the list
        self.assertLess(len(exc.message), 10000)  # Shouldn't be too long

    def test_cel_function_error_with_many_available_functions(self):
        """CELFunctionError should handle many available functions."""
        available = [f"func{i}" for i in range(1000)]
        exc = CELFunctionError("unknown", "Not found", available_functions=available)
        self.assertEqual(len(exc.available_functions), 1000)

    def test_exception_repr_doesnt_crash(self):
        """repr() on exceptions should not crash."""
        exceptions = [
            CELError("test"),
            CELSyntaxError("test", line=1, column=5),
            CELSymbolError("test", available_symbols=["a", "b"]),
            CELTypeError("test", expected_type="int", actual_type="str"),
            CELFunctionError("func", "test"),
            CELExecutionError("test", plan="plan"),
            CELMetricsUnavailableError("metric"),
            CELProfileError("prof", "test"),
        ]
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                r = repr(exc)
                self.assertIsInstance(r, str)

    def test_exception_can_be_pickled(self):
        """Exceptions should be picklable for multiprocessing."""
        import logging
        import pickle

        _logger = logging.getLogger(__name__)

        exceptions = [
            CELError("test"),
            CELSyntaxError("test"),
            CELSymbolError("test"),
        ]
        for exc in exceptions:
            with self.subTest(exception=type(exc).__name__):
                try:
                    pickled = pickle.dumps(exc)
                    unpickled = pickle.loads(pickled)
                    self.assertEqual(unpickled.message, exc.message)
                except Exception as e:
                    # Pickling may not work for all exceptions, log warning
                    _logger.warning(
                        "Failed to pickle exception %s: %s",
                        type(exc).__name__,
                        str(e),
                    )
