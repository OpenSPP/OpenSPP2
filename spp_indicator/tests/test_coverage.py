# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for apply_suppression method coverage in spp.indicator."""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApplySuppression(TransactionCase):
    """Tests for the apply_suppression k-anonymity method on spp.indicator."""

    @classmethod
    def setUpClass(cls):
        """Set up shared indicator for suppression tests."""
        super().setUpClass()

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "suppression_test_var",
                "cel_accessor": "suppression_test",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        # Default indicator: minimum_count=5, suppression_display='less_than'
        cls.indicator = cls.env["spp.indicator"].create(
            {
                "name": "suppression_test_stat",
                "label": "Suppression Test",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )

    # ─── Normal (pass-through) cases ────────────────────────────────────

    def test_count_above_threshold_passes_through(self):
        """Value is returned unchanged when count is at or above the threshold."""
        value, is_suppressed = self.indicator.apply_suppression(100, count=10)

        self.assertEqual(value, 100)
        self.assertFalse(is_suppressed)

    def test_count_equal_to_threshold_passes_through(self):
        """Value is returned unchanged when count exactly equals the threshold."""
        value, is_suppressed = self.indicator.apply_suppression(50, count=5)

        self.assertEqual(value, 50)
        self.assertFalse(is_suppressed)

    # ─── Suppression cases ──────────────────────────────────────────────

    def test_count_below_threshold_is_suppressed(self):
        """Value is suppressed when count is below the minimum threshold."""
        value, is_suppressed = self.indicator.apply_suppression(3, count=3)

        self.assertTrue(is_suppressed)

    def test_count_zero_is_suppressed(self):
        """A count of zero is below the threshold and must be suppressed."""
        value, is_suppressed = self.indicator.apply_suppression(0, count=0)

        self.assertTrue(is_suppressed)

    def test_count_one_is_suppressed(self):
        """A count of one is below the default threshold of 5."""
        value, is_suppressed = self.indicator.apply_suppression(1, count=1)

        self.assertTrue(is_suppressed)

    # ─── Suppression display modes ──────────────────────────────────────

    def test_suppression_display_less_than(self):
        """less_than mode returns '<{threshold}' as display value."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "less_than_mode_stat",
                "label": "Less Than Mode",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )

        display_value, is_suppressed = indicator.apply_suppression(3, count=3)

        self.assertTrue(is_suppressed)
        self.assertEqual(display_value, "<5")

    def test_suppression_display_asterisk(self):
        """asterisk mode returns '*' as display value."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "asterisk_mode_stat",
                "label": "Asterisk Mode",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "asterisk",
            }
        )

        display_value, is_suppressed = indicator.apply_suppression(3, count=3)

        self.assertTrue(is_suppressed)
        self.assertEqual(display_value, "*")

    def test_suppression_display_null(self):
        """null mode returns None as display value."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "null_mode_stat",
                "label": "Null Mode",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "null",
            }
        )

        display_value, is_suppressed = indicator.apply_suppression(3, count=3)

        self.assertTrue(is_suppressed)
        self.assertIsNone(display_value)

    # ─── Return tuple format ────────────────────────────────────────────

    def test_return_value_is_tuple(self):
        """apply_suppression always returns a 2-tuple."""
        result = self.indicator.apply_suppression(100, count=10)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_return_tuple_unsuppressed_types(self):
        """Unsuppressed result has original value type and bool False."""
        display_value, is_suppressed = self.indicator.apply_suppression(42, count=10)

        self.assertEqual(display_value, 42)
        self.assertIsInstance(is_suppressed, bool)
        self.assertFalse(is_suppressed)

    def test_return_tuple_suppressed_types(self):
        """Suppressed result has string/None display value and bool True."""
        display_value, is_suppressed = self.indicator.apply_suppression(3, count=3)

        self.assertIsInstance(is_suppressed, bool)
        self.assertTrue(is_suppressed)

    # ─── None count edge cases ──────────────────────────────────────────

    def test_none_count_uses_int_value_as_count(self):
        """When count is None and value is int, value is used as count."""
        # value=3 is an int below threshold=5, so should be suppressed
        value, is_suppressed = self.indicator.apply_suppression(3)

        self.assertTrue(is_suppressed)

    def test_none_count_with_high_int_value_passes_through(self):
        """When count is None and value is int above threshold, no suppression."""
        value, is_suppressed = self.indicator.apply_suppression(100)

        self.assertEqual(value, 100)
        self.assertFalse(is_suppressed)

    def test_none_count_with_non_int_value_uses_zero(self):
        """When count is None and value is not an int, count defaults to 0.

        0 is below the threshold of 5, so the value is suppressed.
        """
        value, is_suppressed = self.indicator.apply_suppression(3.14)

        self.assertTrue(is_suppressed)

    def test_none_count_with_string_value_uses_zero(self):
        """When count is None and value is a string, count defaults to 0."""
        value, is_suppressed = self.indicator.apply_suppression("some_value")

        self.assertTrue(is_suppressed)

    # ─── Context-specific minimum_count override ────────────────────────

    def test_context_minimum_count_override_suppresses_with_higher_threshold(self):
        """A context record with higher minimum_count suppresses values the default would pass."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "ctx_threshold_stat",
                "label": "Context Threshold",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )
        self.env["spp.indicator.context"].create(
            {
                "statistic_id": indicator.id,
                "context": "gis",
                "minimum_count": 20,
            }
        )

        # count=8 passes the default threshold of 5 but not the GIS override of 20
        value, is_suppressed = indicator.apply_suppression(8, count=8, context="gis")

        self.assertTrue(is_suppressed)

    def test_context_minimum_count_override_passes_when_above_override_threshold(self):
        """Values above the context-specific threshold are not suppressed."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "ctx_threshold_pass_stat",
                "label": "Context Threshold Pass",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )
        self.env["spp.indicator.context"].create(
            {
                "statistic_id": indicator.id,
                "context": "gis",
                "minimum_count": 10,
            }
        )

        # count=15 exceeds the GIS override of 10
        value, is_suppressed = indicator.apply_suppression(15, count=15, context="gis")

        self.assertEqual(value, 15)
        self.assertFalse(is_suppressed)

    def test_no_context_record_falls_back_to_indicator_defaults(self):
        """When no context record exists, indicator-level defaults are used."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "no_ctx_fallback_stat",
                "label": "No Context Fallback",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "asterisk",
            }
        )
        # No context record created — should use indicator minimum_count=5
        display_value, is_suppressed = indicator.apply_suppression(3, count=3, context="dashboard")

        self.assertTrue(is_suppressed)
        self.assertEqual(display_value, "*")

    def test_context_none_uses_indicator_defaults_directly(self):
        """When context=None, indicator-level config is used without lookup."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "null_ctx_stat",
                "label": "Null Context",
                "variable_id": self.cel_variable.id,
                "minimum_count": 10,
                "suppression_display": "null",
            }
        )

        # count=7 is below minimum_count=10
        display_value, is_suppressed = indicator.apply_suppression(7, count=7)

        self.assertTrue(is_suppressed)
        self.assertIsNone(display_value)

    # ─── Threshold boundary with context ────────────────────────────────

    def test_context_less_than_display_shows_context_threshold(self):
        """less_than display uses the context-specific threshold value."""
        indicator = self.env["spp.indicator"].create(
            {
                "name": "ctx_lt_display_stat",
                "label": "Context Less Than",
                "variable_id": self.cel_variable.id,
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )
        self.env["spp.indicator.context"].create(
            {
                "statistic_id": indicator.id,
                "context": "api",
                "minimum_count": 15,
            }
        )

        display_value, is_suppressed = indicator.apply_suppression(8, count=8, context="api")

        self.assertTrue(is_suppressed)
        self.assertEqual(display_value, "<15")
