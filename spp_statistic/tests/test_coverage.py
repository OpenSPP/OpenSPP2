# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Supplemental tests for spp_statistic to reach 95%+ coverage.

Covers gaps not addressed by existing tests:
- apply_suppression() all branches and display modes
- get_context_config() with partial overrides and defaults
- get_published_for_context() invalid context
- get_published_by_category() uncategorized statistics
- to_dict() with context and without category
- StatisticContext model fields
- Name format edge cases
- Publication flag combinations
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSuppressionAllBranches(TransactionCase):
    """Test apply_suppression() with all display modes and branches."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "suppression_test_var",
                "cel_accessor": "suppression_test",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

    def _create_stat(self, name, display="less_than", min_count=5):
        return self.env["spp.statistic"].create(
            {
                "name": name,
                "label": name.replace("_", " ").title(),
                "variable_id": self.cel_var.id,
                "suppression_display": display,
                "minimum_count": min_count,
            }
        )

    def test_suppression_less_than_below_threshold(self):
        """Count below threshold with less_than display returns '<k'."""
        stat = self._create_stat("supp_lt", "less_than", 5)
        value, suppressed = stat.apply_suppression(3)
        self.assertTrue(suppressed)
        self.assertEqual(value, "<5")

    def test_suppression_null_below_threshold(self):
        """Count below threshold with null display returns None."""
        stat = self._create_stat("supp_null", "null", 5)
        value, suppressed = stat.apply_suppression(2)
        self.assertTrue(suppressed)
        self.assertIsNone(value)

    def test_suppression_asterisk_below_threshold(self):
        """Count below threshold with asterisk display returns '*'."""
        stat = self._create_stat("supp_asterisk", "asterisk", 5)
        value, suppressed = stat.apply_suppression(1)
        self.assertTrue(suppressed)
        self.assertEqual(value, "*")

    def test_suppression_above_threshold_not_suppressed(self):
        """Count above threshold returns original value."""
        stat = self._create_stat("supp_above", "less_than", 5)
        value, suppressed = stat.apply_suppression(10)
        self.assertFalse(suppressed)
        self.assertEqual(value, 10)

    def test_suppression_equal_threshold_not_suppressed(self):
        """Count equal to threshold returns original value."""
        stat = self._create_stat("supp_equal", "less_than", 5)
        value, suppressed = stat.apply_suppression(5)
        self.assertFalse(suppressed)
        self.assertEqual(value, 5)

    def test_suppression_count_none_uses_value_as_count(self):
        """When count is None and value is int, uses value as count."""
        stat = self._create_stat("supp_count_none", "less_than", 10)
        value, suppressed = stat.apply_suppression(3)
        self.assertTrue(suppressed)

    def test_suppression_count_none_non_int_value(self):
        """When count is None and value is not int, count defaults to 0."""
        stat = self._create_stat("supp_non_int", "less_than", 5)
        # String value with no explicit count => count=0 < min_count=5
        value, suppressed = stat.apply_suppression("some_string")
        self.assertTrue(suppressed)

    def test_suppression_explicit_count_overrides_value(self):
        """Explicit count parameter overrides value-derived count."""
        stat = self._create_stat("supp_explicit", "less_than", 5)
        # Value is 3 (would trigger) but count=10 (above threshold)
        value, suppressed = stat.apply_suppression(3, count=10)
        self.assertFalse(suppressed)
        self.assertEqual(value, 3)

    def test_suppression_with_context_override(self):
        """Context-specific minimum_count is used when context is provided."""
        stat = self._create_stat("supp_ctx", "less_than", 5)
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": stat.id,
                "context": "gis",
                "minimum_count": 20,
            }
        )
        # Value=10 is above default min_count=5 but below context min=20
        value, suppressed = stat.apply_suppression(10, context="gis")
        self.assertTrue(suppressed)

    def test_suppression_no_context_uses_defaults(self):
        """When context=None, uses statistic's default threshold."""
        stat = self._create_stat("supp_no_ctx", "less_than", 5)
        value, suppressed = stat.apply_suppression(10, context=None)
        self.assertFalse(suppressed)


@tagged("post_install", "-at_install")
class TestContextConfigBranches(TransactionCase):
    """Test get_context_config() with partial overrides and edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "ctx_config_var",
                "cel_accessor": "ctx_config_test",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        cls.category = cls.env["spp.metric.category"].create({"name": "Ctx Config Cat", "code": "ctx_config_cat"})
        cls.stat = cls.env["spp.statistic"].create(
            {
                "name": "ctx_config_stat",
                "label": "Default Label",
                "variable_id": cls.cel_var.id,
                "format": "count",
                "category_id": cls.category.id,
                "minimum_count": 5,
                "suppression_display": "less_than",
            }
        )

    def test_config_no_context_returns_defaults(self):
        """No context config returns defaults from statistic."""
        config = self.stat.get_context_config("dashboard")
        self.assertEqual(config["label"], "Default Label")
        self.assertEqual(config["format"], "count")
        self.assertEqual(config["group"], "ctx_config_cat")
        self.assertIsNone(config["icon"])
        self.assertIsNone(config["color"])
        self.assertEqual(config["minimum_count"], 5)

    def test_config_partial_override_label_only(self):
        """Context with only label override falls back on other fields."""
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "gis",
                "label": "GIS Label",
            }
        )
        config = self.stat.get_context_config("gis")
        self.assertEqual(config["label"], "GIS Label")
        self.assertEqual(config["format"], "count")  # falls back to default
        self.assertEqual(config["group"], "ctx_config_cat")  # falls back to category

    def test_config_partial_override_group_only(self):
        """Context with only group override uses it."""
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "api",
                "group": "custom_grp",
            }
        )
        config = self.stat.get_context_config("api")
        self.assertEqual(config["group"], "custom_grp")
        self.assertEqual(config["label"], "Default Label")  # default

    def test_config_icon_and_color(self):
        """Context with icon and color returns them."""
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "dashboard",
                "icon": "fa-chart-bar",
                "color": "#ff0000",
            }
        )
        config = self.stat.get_context_config("dashboard")
        self.assertEqual(config["icon"], "fa-chart-bar")
        self.assertEqual(config["color"], "#ff0000")

    def test_config_minimum_count_override(self):
        """Context with minimum_count override uses it."""
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "report",
                "minimum_count": 15,
            }
        )
        config = self.stat.get_context_config("report")
        self.assertEqual(config["minimum_count"], 15)

    def test_config_no_category_returns_none_group(self):
        """Statistic without category returns None for group in defaults."""
        stat_no_cat = self.env["spp.statistic"].create(
            {
                "name": "no_cat_stat",
                "label": "No Cat",
                "variable_id": self.cel_var.id,
            }
        )
        config = stat_no_cat.get_context_config("dashboard")
        self.assertIsNone(config["group"])


@tagged("post_install", "-at_install")
class TestPublicationAndQueryEdgeCases(TransactionCase):
    """Test publication flags and query method edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "pub_edge_var",
                "cel_accessor": "pub_edge",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

    def test_get_published_invalid_context(self):
        """Invalid context returns empty recordset."""
        result = self.env["spp.statistic"].get_published_for_context("nonexistent")
        self.assertFalse(result)

    def test_get_published_api_context(self):
        """API context returns only API-published stats."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "api_pub_stat",
                "label": "API Pub",
                "variable_id": self.cel_var.id,
                "is_published_api": True,
            }
        )
        result = self.env["spp.statistic"].get_published_for_context("api")
        self.assertIn(stat, result)

    def test_get_published_report_context(self):
        """Report context returns only report-published stats."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "report_pub_stat",
                "label": "Report Pub",
                "variable_id": self.cel_var.id,
                "is_published_report": True,
            }
        )
        result = self.env["spp.statistic"].get_published_for_context("report")
        self.assertIn(stat, result)

    def test_get_published_inactive_excluded(self):
        """Inactive stats are excluded from published queries."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "inactive_pub_stat",
                "label": "Inactive Pub",
                "variable_id": self.cel_var.id,
                "is_published_gis": True,
                "active": False,
            }
        )
        result = self.env["spp.statistic"].get_published_for_context("gis")
        self.assertNotIn(stat, result)

    def test_get_published_by_category_uncategorized(self):
        """Statistics without category appear under 'uncategorized'."""
        self.env["spp.statistic"].create(
            {
                "name": "uncat_stat",
                "label": "No Category",
                "variable_id": self.cel_var.id,
                "is_published_gis": True,
            }
        )
        grouped = self.env["spp.statistic"].get_published_by_category("gis")
        self.assertIn("uncategorized", grouped)

    def test_get_published_by_category_empty(self):
        """Empty result returns empty dict."""
        grouped = self.env["spp.statistic"].get_published_by_category("nonexistent")
        self.assertEqual(grouped, {})


@tagged("post_install", "-at_install")
class TestToDictEdgeCases(TransactionCase):
    """Test to_dict() edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "todict_var",
                "cel_accessor": "todict_acc",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

    def test_to_dict_without_category(self):
        """to_dict returns None for category when not set."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "no_cat_dict",
                "label": "No Cat Dict",
                "variable_id": self.cel_var.id,
            }
        )
        data = stat.to_dict()
        self.assertIsNone(data["category"])

    def test_to_dict_with_context_override(self):
        """to_dict uses context config when context provided."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "ctx_dict_stat",
                "label": "Default",
                "variable_id": self.cel_var.id,
                "format": "count",
            }
        )
        self.env["spp.statistic.context"].create(
            {
                "statistic_id": stat.id,
                "context": "gis",
                "label": "GIS Override",
                "format": "sum",
            }
        )
        data = stat.to_dict(context="gis")
        self.assertEqual(data["label"], "GIS Override")
        self.assertEqual(data["format"], "sum")

    def test_to_dict_variable_accessor(self):
        """to_dict includes variable_accessor from related field."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "accessor_dict",
                "label": "Accessor Dict",
                "variable_id": self.cel_var.id,
            }
        )
        data = stat.to_dict()
        self.assertEqual(data["variable_accessor"], "todict_acc")

    def test_to_dict_decimal_places(self):
        """to_dict includes decimal_places field."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "decimal_dict",
                "label": "Decimal Dict",
                "variable_id": self.cel_var.id,
                "decimal_places": 3,
            }
        )
        data = stat.to_dict()
        self.assertEqual(data["decimal_places"], 3)


@tagged("post_install", "-at_install")
class TestNameFormatEdgeCases(TransactionCase):
    """Test _check_name_format edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "name_fmt_var",
                "cel_accessor": "name_fmt",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

    def test_single_char_name_valid(self):
        """Single lowercase character is valid."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "a",
                "label": "A",
                "variable_id": self.cel_var.id,
            }
        )
        self.assertTrue(stat.id)

    def test_name_with_hyphens_invalid(self):
        """Names with hyphens are invalid."""
        with self.assertRaises(ValidationError):
            self.env["spp.statistic"].create(
                {
                    "name": "my-stat",
                    "label": "Hyphen",
                    "variable_id": self.cel_var.id,
                }
            )

    def test_name_with_spaces_invalid(self):
        """Names with spaces are invalid."""
        with self.assertRaises(ValidationError):
            self.env["spp.statistic"].create(
                {
                    "name": "my stat",
                    "label": "Space",
                    "variable_id": self.cel_var.id,
                }
            )

    def test_name_leading_underscore_invalid(self):
        """Names starting with underscore are invalid."""
        with self.assertRaises(ValidationError):
            self.env["spp.statistic"].create(
                {
                    "name": "_leading",
                    "label": "Leading",
                    "variable_id": self.cel_var.id,
                }
            )

    def test_name_trailing_underscore_valid(self):
        """Names with trailing underscore are valid."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "trailing_",
                "label": "Trailing",
                "variable_id": self.cel_var.id,
            }
        )
        self.assertTrue(stat.id)


@tagged("post_install", "-at_install")
class TestStatisticContextFields(TransactionCase):
    """Test StatisticContext model fields and edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cel_var = cls.env["spp.cel.variable"].create(
            {
                "name": "ctx_fields_var",
                "cel_accessor": "ctx_fields",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        cls.stat = cls.env["spp.statistic"].create(
            {
                "name": "ctx_fields_stat",
                "label": "Ctx Fields",
                "variable_id": cls.cel_var.id,
            }
        )

    def test_context_gis_threshold_mode(self):
        """GIS-specific threshold mode can be set."""
        ctx = self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "gis",
                "gis_threshold_mode": "auto_quartile",
            }
        )
        self.assertEqual(ctx.gis_threshold_mode, "auto_quartile")

    def test_context_dashboard_widget_type(self):
        """Dashboard-specific widget type can be set."""
        ctx = self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "dashboard",
                "dashboard_widget_type": "gauge",
            }
        )
        self.assertEqual(ctx.dashboard_widget_type, "gauge")

    def test_context_api_with_format_override(self):
        """API context with format override."""
        ctx = self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "api",
                "format": "percent",
            }
        )
        self.assertEqual(ctx.format, "percent")

    def test_context_report_with_all_fields(self):
        """Report context with all optional fields set."""
        ctx = self.env["spp.statistic.context"].create(
            {
                "statistic_id": self.stat.id,
                "context": "report",
                "label": "Report Label",
                "format": "currency",
                "group": "finance",
                "icon": "fa-money",
                "color": "#00ff00",
                "minimum_count": 10,
            }
        )
        self.assertEqual(ctx.label, "Report Label")
        self.assertEqual(ctx.format, "currency")
        self.assertEqual(ctx.minimum_count, 10)

    def test_context_cascade_delete(self):
        """Deleting a statistic cascades to its contexts."""
        stat2 = self.env["spp.statistic"].create(
            {
                "name": "cascade_stat",
                "label": "Cascade",
                "variable_id": self.cel_var.id,
            }
        )
        ctx = self.env["spp.statistic.context"].create(
            {
                "statistic_id": stat2.id,
                "context": "gis",
            }
        )
        ctx_id = ctx.id
        stat2.unlink()
        remaining = self.env["spp.statistic.context"].search([("id", "=", ctx_id)])
        self.assertFalse(remaining)

    def test_related_field_variable_accessor(self):
        """variable_accessor related field tracks variable changes."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "rel_field_stat",
                "label": "Rel Field",
                "variable_id": self.cel_var.id,
            }
        )
        self.assertEqual(stat.variable_accessor, "ctx_fields")
        self.assertEqual(stat.variable_source_type, "computed")

    def test_sensitive_flag(self):
        """is_sensitive flag can be set and defaults to False."""
        stat = self.env["spp.statistic"].create(
            {
                "name": "sensitive_stat",
                "label": "Sensitive",
                "variable_id": self.cel_var.id,
                "is_sensitive": True,
            }
        )
        self.assertTrue(stat.is_sensitive)

    def test_format_selection_values(self):
        """All format selection values can be set."""
        for fmt in ("count", "sum", "avg", "percent", "ratio", "currency"):
            stat = self.env["spp.statistic"].create(
                {
                    "name": f"fmt_{fmt}_stat",
                    "label": f"Format {fmt}",
                    "variable_id": self.cel_var.id,
                    "format": fmt,
                }
            )
            self.assertEqual(stat.format, fmt)
