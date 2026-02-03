# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests for CEL parser, evaluator, and functions.

These tests verify that security controls are working correctly to prevent:
- Object traversal attacks via __class__, __globals__, etc.
- Arbitrary code execution via callable injection
- ReDoS (Regular Expression Denial of Service)
- Stack overflow via deep recursion
- Sensitive data exposure
"""

import time

from odoo.tests import TransactionCase, tagged

from ..services import cel_functions as F
from ..services import cel_parser as P


@tagged("post_install", "-at_install")
class TestCELSecurityParser(TransactionCase):
    """Security tests for CEL parser and evaluator."""

    def test_blocked_private_attribute_access(self):
        """Private attributes (starting with _) should be blocked."""
        ast = P.parse("obj.__class__")
        result = P.evaluate(ast, {"obj": object()})
        # Should return None, not the actual __class__
        self.assertIsNone(result)

    def test_blocked_dunder_class_traversal(self):
        """__class__ traversal should be blocked."""
        # This is a classic Python sandbox escape pattern
        ast = P.parse("obj.__class__.__bases__")
        result = P.evaluate(ast, {"obj": ""})
        self.assertIsNone(result)

    def test_blocked_globals_access(self):
        """__globals__ access should be blocked."""
        ast = P.parse("func.__globals__")

        def sample_func():
            pass

        result = P.evaluate(ast, {"func": sample_func})
        self.assertIsNone(result)

    def test_blocked_builtins_access(self):
        """__builtins__ access should be blocked."""
        ast = P.parse("obj.__builtins__")
        result = P.evaluate(ast, {"obj": {}})
        self.assertIsNone(result)

    def test_blocked_code_object_access(self):
        """__code__ access should be blocked."""
        ast = P.parse("func.__code__")

        def sample_func():
            pass

        result = P.evaluate(ast, {"func": sample_func})
        self.assertIsNone(result)

    def test_blocked_env_access(self):
        """Odoo 'env' attribute should be blocked."""
        ast = P.parse("record.env")
        result = P.evaluate(ast, {"record": {"env": "should_not_see"}})
        self.assertIsNone(result)

    def test_blocked_sudo_access(self):
        """Odoo 'sudo' attribute should be blocked."""
        ast = P.parse("record.sudo")
        result = P.evaluate(ast, {"record": {"sudo": "should_not_see"}})
        self.assertIsNone(result)

    def test_blocked_cursor_access(self):
        """Database cursor access should be blocked."""
        ast = P.parse("record.cr")
        result = P.evaluate(ast, {"record": {"cr": "cursor"}})
        self.assertIsNone(result)

    def test_allowed_normal_attribute_access(self):
        """Normal (non-dangerous) attributes should work."""
        ast = P.parse("record.name")
        result = P.evaluate(ast, {"record": {"name": "John"}})
        self.assertEqual(result, "John")

    def test_recursion_depth_limit(self):
        """Deep recursion should be limited."""
        # Create a deeply nested expression (beyond MAX_RECURSION_DEPTH)
        expr = "true"
        for _ in range(150):
            expr = f"({expr} and true)"

        ast = P.parse(expr)
        # Should raise RecursionError when exceeding limit
        with self.assertRaises(RecursionError) as ctx:
            P.evaluate(ast, {})
        self.assertIn("maximum recursion depth", str(ctx.exception))

    def test_callable_restriction_context_functions_allowed(self):
        """Functions registered in context should be callable."""

        def my_func(x):
            return x * 2

        ast = P.parse("my_func(5)")
        result = P.evaluate(ast, {"my_func": my_func})
        self.assertEqual(result, 10)

    def test_callable_restriction_arbitrary_callables_blocked(self):
        """Callables obtained via traversal should not execute."""

        class Container:
            def dangerous_method(self):
                return "DANGER"

        ast = P.parse("obj.dangerous_method()")
        obj = Container()
        # The method is callable but obtained via traversal, not context
        result = P.evaluate(ast, {"obj": obj})
        # Should return the bound method object, not call it
        self.assertNotEqual(result, "DANGER")

    def test_code_injection_via_import_blocked(self):
        """Code injection via __import__ should be blocked."""
        # Try to access __import__ through various means
        ast = P.parse("obj.__import__")
        result = P.evaluate(ast, {"obj": {}})
        self.assertIsNone(result)

    def test_subclasses_traversal_blocked(self):
        """__subclasses__ traversal (sandbox escape) should be blocked."""
        ast = P.parse("obj.__class__.__subclasses__")
        result = P.evaluate(ast, {"obj": ""})
        self.assertIsNone(result)

    def test_mro_traversal_blocked(self):
        """__mro__ traversal should be blocked."""
        ast = P.parse("obj.__class__.__mro__")
        result = P.evaluate(ast, {"obj": ""})
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestCELSecurityFunctions(TransactionCase):
    """Security tests for CEL helper functions."""

    def test_matches_pattern_length_limit(self):
        """Long regex patterns should be rejected."""
        # Create a pattern longer than MAX_REGEX_PATTERN_LENGTH
        long_pattern = "a" * 1001
        result = F.matches("test", long_pattern)
        self.assertFalse(result)

    def test_matches_redos_pattern_handled(self):
        """ReDoS patterns should not hang."""
        # Classic ReDoS pattern: (a+)+ with many 'a's
        # This can cause exponential backtracking
        evil_pattern = r"(a+)+$"
        evil_input = "a" * 30 + "!"

        start = time.time()
        result = F.matches(evil_input, evil_pattern)
        elapsed = time.time() - start

        # Should complete quickly (within timeout) not hang
        self.assertLess(elapsed, 5.0, f"ReDoS took {elapsed}s - should timeout")
        # Result should be False (timeout or no match)
        self.assertFalse(result)

    def test_matches_invalid_regex(self):
        """Invalid regex should return False, not crash."""
        result = F.matches("test", "[invalid")
        self.assertFalse(result)

    def test_matches_none_string(self):
        """None string should return False."""
        result = F.matches(None, "pattern")
        self.assertFalse(result)

    def test_matches_none_pattern(self):
        """Non-string pattern should return False."""
        result = F.matches("test", None)
        self.assertFalse(result)

    def test_has_blocks_private_attributes(self):
        """has() should block access to private attributes."""

        class Obj:
            _private = "secret"
            public = "visible"

        obj = Obj()
        self.assertFalse(F.has(obj, "_private"))
        self.assertTrue(F.has(obj, "public"))

    def test_has_blocks_dunder_attributes(self):
        """has() should block access to __dunder__ attributes."""

        class Obj:
            pass

        obj = Obj()
        self.assertFalse(F.has(obj, "__class__"))
        self.assertFalse(F.has(obj, "__dict__"))

    def test_has_blocks_dangerous_attributes(self):
        """has() should block access to dangerous Odoo attributes."""
        obj = {"env": "environment", "sudo": "sudo_method", "name": "John"}
        self.assertFalse(F.has(obj, "env"))
        self.assertFalse(F.has(obj, "sudo"))
        self.assertTrue(F.has(obj, "name"))

    def test_size_handles_none(self):
        """size() should return 0 for None."""
        self.assertEqual(F.size(None), 0)

    def test_size_handles_normal_collections(self):
        """size() should work for normal collections."""
        self.assertEqual(F.size([1, 2, 3]), 3)
        self.assertEqual(F.size("hello"), 5)
        self.assertEqual(F.size({"a": 1, "b": 2}), 2)


@tagged("post_install", "-at_install")
class TestCELSecurityIntegration(TransactionCase):
    """Integration security tests using the service layer."""

    def setUp(self):
        super().setUp()
        self.service = self.env["spp.cel.service"]

    def test_sql_injection_attempt(self):
        """SQL injection attempts should be safely handled."""
        # This should not execute SQL - it's just a string comparison
        result = self.service.compile_expression(
            'r.name == "Robert\'); DROP TABLE res_partner;--"',
            "registry_individuals",
        )
        # Should succeed or fail safely, never execute SQL
        self.assertIsInstance(result, dict)

    def test_code_injection_attempt(self):
        """Code injection attempts should fail safely."""
        result = self.service.compile_expression("__import__('os').system('ls')", "registry_individuals")
        # Should fail to compile or return empty results
        self.assertIsInstance(result, dict)

    def test_path_traversal_in_profile(self):
        """Path traversal in profile name should fail."""
        try:
            result = self.service.compile_expression("true", "../../../etc/passwd")
            # Should fail or return invalid
            self.assertFalse(result.get("valid", False))
        except Exception:
            pass  # Expected

    def test_xss_in_expression(self):
        """XSS attempts in expressions should be handled safely."""
        result = self.service.compile_expression('<script>alert("XSS")</script> == 1', "registry_individuals")
        # Should fail to compile (not valid CEL) or return safely
        self.assertIsInstance(result, dict)

    def test_deeply_nested_expression_dos(self):
        """Deeply nested expressions should not cause stack overflow."""
        # Create expression with 150 levels of nesting
        expr = "true"
        for _ in range(150):
            expr = f"({expr} and true)"

        result = self.service.compile_expression(expr, "registry_individuals", limit=0)
        # Should either fail gracefully or succeed with recursion limit
        self.assertIsInstance(result, dict)

    def test_large_list_dos(self):
        """Large list literals should be rejected for scalability."""
        # Create a list with 10000 items - exceeds 1000 limit
        items = ", ".join([str(i) for i in range(10000)])
        expr = f"r.id in [{items}]"

        result = self.service.compile_expression(expr, "registry_individuals", limit=0)

        # Should return error for scalability constraint
        self.assertIn("error", result)
        self.assertIn("10000", result["error"])  # Actual count
        self.assertIn("1000", result["error"])  # Limit
        self.assertIn("scale", result["error"].lower())  # Scalability message

    def test_list_within_limit_allowed(self):
        """List literals within the limit should be allowed."""
        # Create a list with 100 items - within 1000 limit
        items = ", ".join([str(i) for i in range(100)])
        expr = f"r.id in [{items}]"

        result = self.service.compile_expression(expr, "registry_individuals", limit=0)
        # Should succeed without error (error key may exist with None value)
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("error"), f"Unexpected error: {result.get('error')}")


@tagged("post_install", "-at_install")
class TestCELSecurityConstants(TransactionCase):
    """Test that security constants are properly defined."""

    def test_blocked_attributes_is_frozenset(self):
        """BLOCKED_ATTRIBUTES should be immutable."""
        self.assertIsInstance(P.BLOCKED_ATTRIBUTES, frozenset)

    def test_max_recursion_depth_defined(self):
        """MAX_RECURSION_DEPTH should be defined and reasonable."""
        self.assertIsInstance(P.MAX_RECURSION_DEPTH, int)
        self.assertGreater(P.MAX_RECURSION_DEPTH, 10)
        self.assertLess(P.MAX_RECURSION_DEPTH, 1000)

    def test_regex_timeout_defined(self):
        """REGEX_TIMEOUT_SECONDS should be defined."""
        self.assertIsInstance(F.REGEX_TIMEOUT_SECONDS, int)
        self.assertGreater(F.REGEX_TIMEOUT_SECONDS, 0)
        self.assertLess(F.REGEX_TIMEOUT_SECONDS, 60)

    def test_max_regex_pattern_length_defined(self):
        """MAX_REGEX_PATTERN_LENGTH should be defined."""
        self.assertIsInstance(F.MAX_REGEX_PATTERN_LENGTH, int)
        self.assertGreater(F.MAX_REGEX_PATTERN_LENGTH, 100)
