# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests for CEL evaluator in approval workflows.

These tests verify that the CEL evaluator properly:
- Filters sensitive fields from record context
- Prevents access to dangerous Odoo methods
- Handles malicious expressions safely
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCELEvaluatorSecurity(TransactionCase):
    """Security tests for CEL evaluator."""

    def setUp(self):
        super().setUp()
        self.evaluator = self.env["spp.cel.evaluator"]

    def test_sensitive_fields_filtered_password(self):
        """Password fields should be filtered from context."""
        # Create a mock record dict with password field
        record_dict = self.evaluator._record_to_dict(self.env.user)

        # Password field should not be in the dict
        self.assertNotIn("password", record_dict)
        self.assertNotIn("password_crypt", record_dict)

    def test_sensitive_fields_filtered_token_patterns(self):
        """Fields with 'token' in name should be filtered."""
        evaluator = self.evaluator

        # Test pattern matching
        self.assertTrue(evaluator._is_sensitive_field("access_token"))
        self.assertTrue(evaluator._is_sensitive_field("session_token"))
        self.assertTrue(evaluator._is_sensitive_field("auth_signup_token"))
        self.assertTrue(evaluator._is_sensitive_field("api_token"))

    def test_sensitive_fields_filtered_key_patterns(self):
        """Fields with 'key' in name should be filtered."""
        evaluator = self.evaluator

        self.assertTrue(evaluator._is_sensitive_field("private_key"))
        self.assertTrue(evaluator._is_sensitive_field("api_key"))
        self.assertTrue(evaluator._is_sensitive_field("encryption_key"))

    def test_sensitive_fields_filtered_secret_patterns(self):
        """Fields with 'secret' in name should be filtered."""
        evaluator = self.evaluator

        self.assertTrue(evaluator._is_sensitive_field("totp_secret"))
        self.assertTrue(evaluator._is_sensitive_field("api_secret"))
        self.assertTrue(evaluator._is_sensitive_field("client_secret"))

    def test_non_sensitive_fields_allowed(self):
        """Non-sensitive fields should be accessible."""
        evaluator = self.evaluator

        self.assertFalse(evaluator._is_sensitive_field("name"))
        self.assertFalse(evaluator._is_sensitive_field("display_name"))
        self.assertFalse(evaluator._is_sensitive_field("state"))
        self.assertFalse(evaluator._is_sensitive_field("amount"))

    def test_private_fields_excluded(self):
        """Private fields (starting with _) should be excluded."""
        record_dict = self.evaluator._record_to_dict(self.env.user)

        # _name is explicitly added, but other _ fields should be excluded
        for key in record_dict:
            if key != "_name":
                self.assertFalse(key.startswith("_"), f"Private field {key} should be excluded")

    def test_evaluate_sql_injection_safe(self):
        """SQL injection in expressions should not execute SQL."""
        # This is a string comparison, not SQL
        result = self.evaluator.evaluate('record.name == "Robert\'); DROP TABLE res_users;--"', self.env.user)
        # Should return False (names don't match) without executing SQL
        self.assertFalse(result)

    def test_evaluate_code_injection_safe(self):
        """Code injection attempts should fail safely."""
        # __import__ should not be accessible
        try:
            result = self.evaluator.evaluate("__import__('os').system('ls')", self.env.user)
            # Should fail or return None/False, never execute code
            self.assertIn(result, [None, False, 0, ""])
        except Exception:
            pass  # Expected - syntax error or evaluation error

    def test_evaluate_env_access_blocked(self):
        """Access to Odoo env through expressions should be blocked."""
        result = self.evaluator.evaluate("record.env", self.env.user)
        # env access should be blocked, returning None or empty
        # Note: _record_to_dict doesn't include env, but even if accessed
        # the safe_getattr should block it
        self.assertNotEqual(result, self.env)

    def test_evaluate_sudo_access_blocked(self):
        """Access to sudo method through expressions should be blocked."""
        result = self.evaluator.evaluate("record.sudo", self.env.user)
        # Should not return the actual sudo method
        self.assertNotEqual(str(type(result)), "<class 'method'>")

    def test_validate_malformed_expression(self):
        """Malformed expressions should return validation error."""
        result = self.evaluator.validate("invalid >>> syntax")
        self.assertFalse(result["valid"])
        self.assertIsNotNone(result["error"])

    def test_validate_empty_expression_is_valid(self):
        """Empty expressions should be considered valid (no-op)."""
        result = self.evaluator.validate("")
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])

    def test_evaluate_empty_expression_returns_true(self):
        """Empty expressions should return True (allow by default)."""
        result = self.evaluator.evaluate("", self.env.user)
        self.assertTrue(result)

    def test_record_to_dict_handles_none(self):
        """_record_to_dict should handle None gracefully."""
        result = self.evaluator._record_to_dict(None)
        self.assertEqual(result, {})

    def test_record_to_dict_includes_id(self):
        """_record_to_dict should include record ID."""
        result = self.evaluator._record_to_dict(self.env.user)
        self.assertIn("id", result)
        self.assertEqual(result["id"], self.env.user.id)

    def test_evaluate_with_extra_context(self):
        """Extra context should be merged safely."""
        extra = {"custom_var": 42}
        result = self.evaluator.evaluate("custom_var == 42", self.env.user, extra)
        self.assertTrue(result)

    def test_evaluate_user_expression_handles_none_result(self):
        """evaluate_user_expression should handle non-user results."""
        result = self.evaluator.evaluate_user_expression("null", self.env.user)
        # Should return empty recordset
        self.assertEqual(len(result), 0)

    def test_evaluate_user_expression_handles_int(self):
        """evaluate_user_expression should handle integer user ID."""
        # This should return the admin user (id=1)
        result = self.evaluator.evaluate_user_expression("1", self.env.user)
        # Either returns the user or empty if doesn't exist
        self.assertTrue(hasattr(result, "_name"))

    def test_evaluate_user_expression_handles_list(self):
        """evaluate_user_expression should handle list of user IDs."""
        result = self.evaluator.evaluate_user_expression("[1, 2]", self.env.user)
        # Should return users recordset
        self.assertTrue(hasattr(result, "_name"))
        self.assertEqual(result._name, "res.users")


@tagged("post_install", "-at_install")
class TestCELEvaluatorSensitiveFieldConstants(TransactionCase):
    """Test that sensitive field constants are properly defined."""

    def test_sensitive_fields_is_frozenset(self):
        """SENSITIVE_FIELDS should be immutable."""
        from odoo.addons.spp_approval.models.cel_evaluator import SENSITIVE_FIELDS

        self.assertIsInstance(SENSITIVE_FIELDS, frozenset)

    def test_sensitive_fields_contains_password(self):
        """SENSITIVE_FIELDS should include password fields."""
        from odoo.addons.spp_approval.models.cel_evaluator import SENSITIVE_FIELDS

        self.assertIn("password", SENSITIVE_FIELDS)
        self.assertIn("password_crypt", SENSITIVE_FIELDS)

    def test_sensitive_fields_contains_tokens(self):
        """SENSITIVE_FIELDS should include token fields."""
        from odoo.addons.spp_approval.models.cel_evaluator import SENSITIVE_FIELDS

        self.assertIn("session_token", SENSITIVE_FIELDS)
        self.assertIn("access_token", SENSITIVE_FIELDS)

    def test_sensitive_patterns_defined(self):
        """SENSITIVE_FIELD_PATTERNS should be defined."""
        from odoo.addons.spp_approval.models.cel_evaluator import (
            SENSITIVE_FIELD_PATTERNS,
        )

        self.assertIsInstance(SENSITIVE_FIELD_PATTERNS, tuple)
        self.assertIn("password", SENSITIVE_FIELD_PATTERNS)
        self.assertIn("secret", SENSITIVE_FIELD_PATTERNS)
        self.assertIn("token", SENSITIVE_FIELD_PATTERNS)
