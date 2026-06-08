# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Security Warning model.

Covers models/security_warning.py:
- get_security_warnings()  when all settings are disabled (default)
- get_security_warnings()  when one or more settings are enabled
- has_security_warnings()
- get_warning_summary()
"""

from odoo.tests import TransactionCase


class TestDCISecurityWarning(TransactionCase):
    """Test cases for spp.dci.security.warning abstract model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SecurityWarning = cls.env["spp.dci.security.warning"]
        cls.ConfigParam = cls.env["ir.config_parameter"].sudo()

    def _set_param(self, key, value):
        """Helper: set a system parameter."""
        self.ConfigParam.set_param(key, value)

    def _clear_all_insecure_params(self):
        """Reset all insecure params to 'false' so tests start clean."""
        for setting in self.SecurityWarning.INSECURE_SETTINGS:
            self._set_param(setting["key"], "false")

    def setUp(self):
        super().setUp()
        self._clear_all_insecure_params()

    def test_no_warnings_when_all_params_false(self):
        """With all params set to 'false', get_security_warnings() returns empty list."""
        warnings = self.SecurityWarning.get_security_warnings()
        self.assertIsInstance(warnings, list)
        self.assertEqual(len(warnings), 0)

    def test_warning_returned_when_param_enabled(self):
        """Setting one insecure param to 'true' produces exactly one warning."""
        self._set_param("dci.allow_unsigned_requests", "true")

        warnings = self.SecurityWarning.get_security_warnings()
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["key"], "dci.allow_unsigned_requests")
        self.assertIn("name", warnings[0])
        self.assertIn("description", warnings[0])

    def test_multiple_warnings_when_multiple_params_enabled(self):
        """Each enabled insecure param produces its own warning entry."""
        self._set_param("dci.allow_unsigned_requests", "true")
        self._set_param("dci.bypass_bearer_auth", "true")

        warnings = self.SecurityWarning.get_security_warnings()
        self.assertEqual(len(warnings), 2)
        keys = [w["key"] for w in warnings]
        self.assertIn("dci.allow_unsigned_requests", keys)
        self.assertIn("dci.bypass_bearer_auth", keys)

    def test_all_four_insecure_settings_trigger_warnings(self):
        """Enabling all four params produces four distinct warnings."""
        for setting in self.SecurityWarning.INSECURE_SETTINGS:
            self._set_param(setting["key"], "true")

        warnings = self.SecurityWarning.get_security_warnings()
        self.assertEqual(len(warnings), 4)
        keys = {w["key"] for w in warnings}
        for setting in self.SecurityWarning.INSECURE_SETTINGS:
            self.assertIn(setting["key"], keys)

    def test_case_insensitive_true_value(self):
        """The param value check is case-insensitive ('True', 'TRUE' all match)."""
        self._set_param("dci.allow_http_callbacks", "True")
        warnings = self.SecurityWarning.get_security_warnings()
        keys = [w["key"] for w in warnings]
        self.assertIn("dci.allow_http_callbacks", keys)

    def test_has_security_warnings_false_when_all_disabled(self):
        """has_security_warnings() returns False when no insecure settings are on."""
        result = self.SecurityWarning.has_security_warnings()
        self.assertFalse(result)

    def test_has_security_warnings_true_when_one_enabled(self):
        """has_security_warnings() returns True when at least one setting is enabled."""
        self._set_param("dci.allow_internal_callback_ips", "true")
        result = self.SecurityWarning.has_security_warnings()
        self.assertTrue(result)

    def test_get_warning_summary_no_warnings(self):
        """get_warning_summary() with no active warnings returns correct shape."""
        summary = self.SecurityWarning.get_warning_summary()

        self.assertIn("has_warnings", summary)
        self.assertIn("warning_count", summary)
        self.assertIn("warnings", summary)
        self.assertIn("message", summary)

        self.assertFalse(summary["has_warnings"])
        self.assertEqual(summary["warning_count"], 0)
        self.assertIsInstance(summary["warnings"], list)
        self.assertEqual(summary["message"], "")

    def test_get_warning_summary_with_warnings(self):
        """get_warning_summary() with active warnings returns correct shape and message."""
        self._set_param("dci.bypass_bearer_auth", "true")

        summary = self.SecurityWarning.get_warning_summary()

        self.assertTrue(summary["has_warnings"])
        self.assertEqual(summary["warning_count"], 1)
        self.assertEqual(len(summary["warnings"]), 1)
        self.assertIn("DCI security setting", summary["message"])

    def test_insecure_settings_constant_structure(self):
        """Every entry in INSECURE_SETTINGS must have key, name, and description."""
        for setting in self.SecurityWarning.INSECURE_SETTINGS:
            with self.subTest(key=setting.get("key")):
                self.assertIn("key", setting)
                self.assertIn("name", setting)
                self.assertIn("description", setting)
                self.assertTrue(setting["key"].startswith("dci."))

    def test_warning_not_returned_when_param_set_to_false_string(self):
        """A param explicitly set to 'false' must not appear in warnings."""
        self._set_param("dci.allow_unsigned_requests", "false")

        warnings = self.SecurityWarning.get_security_warnings()
        keys = [w["key"] for w in warnings]
        self.assertNotIn("dci.allow_unsigned_requests", keys)
