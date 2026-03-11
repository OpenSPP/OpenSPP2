# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestQuantileBreaksEdgeCases(TransactionCase):
    """Test _compute_quantile_breaks edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.IndicatorLayer = cls.env["spp.gis.indicator.layer"]

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_quantile_edge",
                "cel_accessor": "test_quantile_edge",
                "label": "Test Quantile Edge",
                "value_type": "number",
                "source_type": "constant",
            }
        )

    def test_quantile_breaks_empty_values(self):
        """Test _compute_quantile_breaks with empty values list."""
        layer = self.IndicatorLayer.create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
            }
        )
        result = layer._compute_quantile_breaks([], 3)
        self.assertEqual(result, [])

    def test_quantile_breaks_num_classes_less_than_2(self):
        """Test _compute_quantile_breaks with num_classes < 2."""
        layer = self.IndicatorLayer.create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
            }
        )
        result = layer._compute_quantile_breaks([10, 20, 30], 1)
        self.assertEqual(result, [])

    def test_quantile_breaks_unique_values_less_than_num_classes(self):
        """Test _compute_quantile_breaks when unique values < num_classes returns unique_values[:-1]."""
        layer = self.IndicatorLayer.create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
            }
        )
        # 2 unique values but requesting 5 classes
        result = layer._compute_quantile_breaks([10, 10, 20, 20], 5)
        # unique values are [10, 20], so [:-1] = [10]
        self.assertEqual(result, [10])

    def test_quantile_breaks_three_unique_for_five_classes(self):
        """Test _compute_quantile_breaks when 3 unique values but 5 classes requested."""
        layer = self.IndicatorLayer.create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
            }
        )
        result = layer._compute_quantile_breaks([10, 20, 30], 5)
        # unique values [10, 20, 30], 3 < 5, so returns [10, 20]
        self.assertEqual(result, [10, 20])


@tagged("post_install", "-at_install")
class TestLegendHtmlEdgeCases(TransactionCase):
    """Test _compute_legend_html edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_legend_edge",
                "cel_accessor": "test_legend_edge",
                "label": "Test Legend Edge",
                "value_type": "number",
                "source_type": "constant",
            }
        )

    def test_legend_html_empty_break_values(self):
        """Test legend HTML is empty when break_values is empty."""
        # Create a layer with no indicator data so break_values is empty
        var_empty = self.env["spp.cel.variable"].create(
            {
                "name": "test_legend_empty",
                "cel_accessor": "test_legend_empty",
                "label": "Test Legend Empty",
                "value_type": "number",
                "source_type": "constant",
            }
        )
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Empty Breaks Layer",
                "variable_id": var_empty.id,
                "period_key": "2099-01",
                "color_scale_id": self.color_scale.id,
            }
        )
        # No indicators exist for this variable/period, so break_values should be empty
        self.assertEqual(layer.break_values, "")
        self.assertEqual(layer.legend_html, "")

    def test_legend_html_with_valid_data(self):
        """Test legend HTML is generated when color_scale_id and break_values are present."""
        area1 = self.env["spp.area"].create(
            {
                "draft_name": "Legend Test Area 1",
                "code": "LTA1",
            }
        )
        area2 = self.env["spp.area"].create(
            {
                "draft_name": "Legend Test Area 2",
                "code": "LTA2",
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 50.0,
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": area2.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 100.0,
            }
        )
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "With Color Scale Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "num_classes": 2,
            }
        )
        # Should have legend content since we have data and color scale
        self.assertTrue(layer.break_values)
        self.assertTrue(layer.legend_html)
        self.assertIn("gis-choropleth-legend", layer.legend_html)


@tagged("post_install", "-at_install")
class TestGetFeatureColorsEdgeCases(TransactionCase):
    """Test get_feature_colors edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_feature_edge",
                "cel_accessor": "test_feature_edge",
                "label": "Test Feature Edge",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        cls.area1 = cls.env["spp.area"].create(
            {
                "draft_name": "Feature Area 1",
                "code": "FA1",
            }
        )
        cls.area2 = cls.env["spp.area"].create(
            {
                "draft_name": "Feature Area 2",
                "code": "FA2",
            }
        )
        cls.area3 = cls.env["spp.area"].create(
            {
                "draft_name": "Feature Area 3",
                "code": "FA3",
            }
        )
        cls.area4 = cls.env["spp.area"].create(
            {
                "draft_name": "Feature Area 4",
                "code": "FA4",
            }
        )

    def test_get_feature_colors_no_indicators(self):
        """Test get_feature_colors returns empty dict when no indicators exist."""
        var_empty = self.env["spp.cel.variable"].create(
            {
                "name": "test_fc_empty",
                "cel_accessor": "test_fc_empty",
                "label": "Test FC Empty",
                "value_type": "number",
                "source_type": "constant",
            }
        )
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "No Indicators Layer",
                "variable_id": var_empty.id,
                "period_key": "2099-01",
                "color_scale_id": self.color_scale.id,
            }
        )
        result = layer.get_feature_colors([self.area1.id, self.area2.id])
        self.assertEqual(result, {})

    def test_get_feature_colors_empty_break_values(self):
        """Test get_feature_colors when break_values is truly empty string returns empty dict."""
        var_nodata = self.env["spp.cel.variable"].create(
            {
                "name": "test_fc_nodata",
                "cel_accessor": "test_fc_nodata",
                "label": "Test FC No Data",
                "value_type": "number",
                "source_type": "constant",
            }
        )
        # No indicators at all => break_values will be empty string
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Empty Breaks Layer",
                "variable_id": var_nodata.id,
                "period_key": "2099-01",
                "color_scale_id": self.color_scale.id,
                "classification_method": "equal_interval",
                "num_classes": 3,
            }
        )
        # No data => break_values is empty string
        self.assertEqual(layer.break_values, "")
        result = layer.get_feature_colors([self.area1.id, self.area2.id])
        self.assertEqual(result, {})

    def test_get_feature_colors_all_same_values(self):
        """Test get_feature_colors when all values are the same (breaks is [])."""
        var_single = self.env["spp.cel.variable"].create(
            {
                "name": "test_fc_single",
                "cel_accessor": "test_fc_single",
                "label": "Test FC Single",
                "value_type": "number",
                "source_type": "constant",
            }
        )
        for area in [self.area1, self.area2]:
            self.env["spp.hxl.area.indicator"].create(
                {
                    "area_id": area.id,
                    "variable_id": var_single.id,
                    "period_key": "2024-12",
                    "value": 100.0,
                }
            )
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Same Values Layer",
                "variable_id": var_single.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "equal_interval",
                "num_classes": 3,
            }
        )
        # All values equal => breaks is "[]", which is truthy
        self.assertEqual(layer.break_values, "[]")
        # With 0 breaks => 1 class, all areas get the first color
        result = layer.get_feature_colors([self.area1.id, self.area2.id])
        self.assertEqual(len(result), 2)
        # All should have the same color (first color)
        colors = list(result.values())
        self.assertEqual(colors[0], colors[1])

    def test_get_feature_colors_missing_area_not_in_result(self):
        """Test that areas without indicators are not in the result."""
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-06",
                "value": 50.0,
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area2.id,
                "variable_id": self.variable.id,
                "period_key": "2024-06",
                "value": 200.0,
            }
        )
        # area3 has no indicator for this period/variable

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Missing Area Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-06",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 2,
            }
        )

        area_ids = [self.area1.id, self.area2.id, self.area3.id]
        result = layer.get_feature_colors(area_ids)
        # area3 has no indicator => not in result
        self.assertNotIn(self.area3.id, result)
        # area1 and area2 should have colors
        self.assertIn(self.area1.id, result)
        self.assertIn(self.area2.id, result)

    def test_get_feature_colors_zero_value_not_skipped(self):
        """Test that indicators with value=0 are NOT skipped."""
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-07",
                "value": 0.0,
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area2.id,
                "variable_id": self.variable.id,
                "period_key": "2024-07",
                "value": 100.0,
            }
        )

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Zero Value Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-07",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 2,
            }
        )

        area_ids = [self.area1.id, self.area2.id]
        result = layer.get_feature_colors(area_ids)
        # value=0 should NOT be skipped
        self.assertIn(self.area1.id, result)
        self.assertIn(self.area2.id, result)

    def test_get_feature_colors_boundary_values(self):
        """Test boundary value classification in get_feature_colors."""
        # Create 4 indicators with known values
        for area, val in [(self.area1, 10.0), (self.area2, 50.0), (self.area3, 90.0), (self.area4, 100.0)]:
            self.env["spp.hxl.area.indicator"].create(
                {
                    "area_id": area.id,
                    "variable_id": self.variable.id,
                    "period_key": "2024-08",
                    "value": val,
                }
            )

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Boundary Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-08",
                "color_scale_id": self.color_scale.id,
                "classification_method": "manual",
                "manual_breaks": "50,90",
            }
        )

        area_ids = [self.area1.id, self.area2.id, self.area3.id, self.area4.id]
        result = layer.get_feature_colors(area_ids)
        self.assertEqual(len(result), 4)

        # area1 (10) is < 50 => class 0 => first color
        # area2 (50) is >= 50 but < 90 => class 1
        # area3 (90) is >= 90 => class 2
        # area4 (100) is >= 90 => class 2
        # Verify different classes get different colors (at least area1 vs area3/area4)
        self.assertNotEqual(result[self.area1.id], result[self.area4.id])
        # area3 and area4 should be same class => same color
        self.assertEqual(result[self.area3.id], result[self.area4.id])


@tagged("post_install", "-at_install")
class TestGetIndicatorValuesEdgeCases(TransactionCase):
    """Test _get_indicator_values edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_indicator_vals",
                "cel_accessor": "test_indicator_vals",
                "label": "Test Indicator Vals",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        cls.area1 = cls.env["spp.area"].create(
            {
                "draft_name": "Indicator Val Area 1",
                "code": "IVA1",
            }
        )

    def test_get_indicator_values_with_incident_filter(self):
        """Test _get_indicator_values with incident_id filter."""
        # Create a hazard incident
        hazard_cat = self.env["spp.hazard.category"].create(
            {
                "name": "Test Hazard Category",
                "code": "THC",
            }
        )
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Test Incident",
                "code": "TI001",
                "category_id": hazard_cat.id,
                "start_date": "2024-01-01",
            }
        )

        # Create indicator with incident
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 999.0,
                "incident_id": incident.id,
            }
        )

        # Create indicator without incident
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 111.0,
            }
        )

        # Layer WITH incident filter
        layer_with_incident = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Incident Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "incident_id": incident.id,
            }
        )
        values = layer_with_incident._get_indicator_values()
        self.assertEqual(len(values), 1)
        self.assertIn(999.0, values)
        self.assertNotIn(111.0, values)

    def test_get_indicator_values_empty_period_key(self):
        """Test _get_indicator_values with empty period_key matches all periods."""
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-01",
                "value": 10.0,
            }
        )

        # Layer with empty period_key: the domain won't include period_key filter
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "No Period Layer",
                "variable_id": self.variable.id,
                "period_key": "",
                "color_scale_id": self.color_scale.id,
            }
        )
        values = layer._get_indicator_values()
        # Should find the indicator since no period_key filter
        self.assertIn(10.0, values)


@tagged("post_install", "-at_install")
class TestComputeBreakValuesEdgeCases(TransactionCase):
    """Test _compute_break_values edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_break_edge",
                "cel_accessor": "test_break_edge",
                "label": "Test Break Edge",
                "value_type": "number",
                "source_type": "constant",
            }
        )

    def test_break_values_no_indicator_data(self):
        """Test _compute_break_values with no indicator data results in empty break_values."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "No Data Layer",
                "variable_id": self.variable.id,
                "period_key": "2099-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
            }
        )
        self.assertEqual(layer.break_values, "")

    def test_break_values_no_variable(self):
        """Test _compute_break_values when variable_id triggers empty."""
        # After creation, we check the logic. variable_id is required,
        # but the compute explicitly checks for it.
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Break No Var Layer",
                "variable_id": self.variable.id,
                "period_key": "2099-12",
                "color_scale_id": self.color_scale.id,
            }
        )
        # Layer with no data -> empty break_values
        self.assertEqual(layer.break_values, "")

    def test_break_values_unknown_classification_fallback(self):
        """Test _compute_break_values with data falls back to empty breaks for unknown method."""
        # Create indicators so values list is non-empty (use different areas to avoid unique constraint)
        area1 = self.env["spp.area"].create(
            {
                "draft_name": "Break Fallback Area 1",
                "code": "BFA1",
            }
        )
        area2 = self.env["spp.area"].create(
            {
                "draft_name": "Break Fallback Area 2",
                "code": "BFA2",
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 50.0,
            }
        )
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": area2.id,
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "value": 100.0,
            }
        )
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Fallback Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 2,
            }
        )
        # Forcefully set classification_method to an unsupported value via SQL
        # to test the else branch in _compute_break_values
        self.env.cr.execute(
            "UPDATE spp_gis_indicator_layer SET classification_method = %s WHERE id = %s",
            ("unknown_method", layer.id),
        )
        layer.invalidate_recordset()
        # Re-trigger compute
        layer._compute_break_values()
        self.assertEqual(layer.break_values, "[]")


@tagged("post_install", "-at_install")
class TestGetColorForValueEdgeCases(TransactionCase):
    """Test GisColorScale.get_color_for_value edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        cls.diverging_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(cls.diverging_colors),
            }
        )

        cls.sequential_colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
        cls.sequential_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Sequential Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(cls.sequential_colors),
            }
        )

    def test_diverging_min_equals_max(self):
        """Test diverging scale when min == max returns center color."""
        color = self.diverging_scale.get_color_for_value(50, 50, 50)
        center_idx = len(self.diverging_colors) // 2
        self.assertEqual(color, self.diverging_colors[center_idx])

    def test_diverging_center_equals_min(self):
        """Test diverging scale when center == min_val."""
        # center=0, min_val=0, max_val=100, value below center is clamped
        # value < center but center == min_val => normalized = 0
        color = self.diverging_scale.get_color_for_value(0, 0, 100, center=0)
        # value == min_val => colors[0]
        self.assertEqual(color, self.diverging_colors[0])

    def test_diverging_center_equals_max(self):
        """Test diverging scale when max_val == center."""
        # center=100, min_val=0, max_val=100
        # value > center is impossible since max_val == center
        # value at center should map to upper half with normalized=1
        color = self.diverging_scale.get_color_for_value(50, 0, 100, center=100)
        # 50 < center (100), so lower half: normalized = (50 - 0) / (100 - 0) = 0.5
        self.assertIn(color, self.diverging_colors)

    def test_sequential_exact_boundary(self):
        """Test sequential scale at exact boundary values."""
        # Test at 0 (min)
        color_min = self.sequential_scale.get_color_for_value(0, 0, 100)
        self.assertEqual(color_min, self.sequential_colors[0])

        # Test at 100 (max)
        color_max = self.sequential_scale.get_color_for_value(100, 0, 100)
        self.assertEqual(color_max, self.sequential_colors[-1])

        # Test at exactly 25% (first quarter)
        color_quarter = self.sequential_scale.get_color_for_value(25, 0, 100)
        self.assertIn(color_quarter, self.sequential_colors)

    def test_sequential_value_slightly_above_min(self):
        """Test sequential scale with value just above min."""
        color = self.sequential_scale.get_color_for_value(1, 0, 100)
        # Should be first or second color
        self.assertIn(color, self.sequential_colors[:2])


@tagged("post_install", "-at_install")
class TestGetChoroplethConfigEdgeCases(TransactionCase):
    """Test GisDataLayerIndicator._get_choropleth_config edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.DataLayer = cls.env["spp.gis.data.layer"]

        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_choropleth_cfg",
                "cel_accessor": "test_choropleth_cfg",
                "label": "Test Choropleth Config",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        cls.indicator_layer = cls.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Indicator Config",
                "variable_id": cls.variable.id,
                "color_scale_id": cls.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 5,
            }
        )

        # Find a geo field for testing
        geo_field = cls.env["ir.model.fields"].search(
            [
                ("model", "=", "spp.area"),
                ("ttype", "=", "geo_polygon"),
            ],
            limit=1,
        )
        cls.geo_field_id = geo_field.id if geo_field else False

        cls.gis_view = cls.env["ir.ui.view"].search(
            [("type", "=", "spp_gis")],
            limit=1,
        )

    def _skip_if_no_gis_prereqs(self):
        """Skip test if GIS prerequisites are missing."""
        if not self.gis_view:
            self.skipTest("No GIS view available for testing")
        if not self.geo_field_id:
            self.skipTest("No geo_polygon field available for testing")

    def test_choropleth_config_indicator_no_color_scale_colors(self):
        """Test _get_choropleth_config when indicator has color_scale but empty colors."""
        self._skip_if_no_gis_prereqs()

        # Create a color scale and then clear its colors
        empty_color_scale = self.env["spp.gis.color.scale"].create(
            {
                "name": "Temp Scale",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#000", "#fff"]),
            }
        )
        indicator_layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "No Colors Indicator",
                "variable_id": self.variable.id,
                "color_scale_id": empty_color_scale.id,
            }
        )

        layer = self.DataLayer.create(
            {
                "name": "Config Test Layer",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "choropleth",
                "indicator_layer_id": indicator_layer.id,
            }
        )

        config = layer._get_choropleth_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["type"], "indicator")
        # color_ramp should have colors from the scale
        self.assertEqual(config["color_ramp"], ["#000", "#fff"])

    def test_choropleth_config_with_empty_break_values(self):
        """Test _get_choropleth_config when break_values is empty."""
        self._skip_if_no_gis_prereqs()

        # indicator_layer has no data, so break_values is ""
        layer = self.DataLayer.create(
            {
                "name": "Empty Breaks Config",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "choropleth",
                "indicator_layer_id": self.indicator_layer.id,
            }
        )

        config = layer._get_choropleth_config()
        self.assertIsNotNone(config)
        self.assertEqual(config["type"], "indicator")
        # break_values is empty (""), json.loads("" or "[]") => []
        self.assertEqual(config["break_values"], [])

    def test_choropleth_config_non_choropleth_returns_none(self):
        """Test that _get_choropleth_config returns None for non-choropleth layers."""
        self._skip_if_no_gis_prereqs()

        layer = self.DataLayer.create(
            {
                "name": "Basic Layer Config",
                "view_id": self.gis_view.id,
                "geo_field_id": self.geo_field_id,
                "geo_repr": "basic",
            }
        )

        config = layer._get_choropleth_config()
        self.assertIsNone(config)


@tagged("post_install", "-at_install")
class TestCheckColorsJsonEdgeCases(TransactionCase):
    """Test GisColorScale._check_colors_json edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ColorScale = cls.env["spp.gis.color.scale"]

    def test_empty_string_colors_json(self):
        """Test _check_colors_json with empty string passes (skipped by constraint)."""
        scale = self.ColorScale.create(
            {
                "name": "Empty Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#000", "#fff"]),
            }
        )
        # Setting colors_json to empty string should pass the constraint
        # (the constraint has `if not rec.colors_json: continue`)
        scale.colors_json = ""
        # No error raised means constraint passes for empty

    def test_short_hex_format_accepted(self):
        """Test that short hex format (#fff) is accepted by constraint."""
        scale = self.ColorScale.create(
            {
                "name": "Short Hex Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#fff", "#000", "#abc"]),
            }
        )
        colors = scale.get_colors()
        self.assertEqual(colors, ["#fff", "#000", "#abc"])

    def test_mixed_short_long_hex(self):
        """Test that mix of short and long hex formats is accepted."""
        scale = self.ColorScale.create(
            {
                "name": "Mixed Hex Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#fff", "#ff0000"]),
            }
        )
        colors = scale.get_colors()
        self.assertEqual(len(colors), 2)

    def test_invalid_length_hex_rejected(self):
        """Test that hex colors with wrong length are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Bad Length",
                    "scale_type": "sequential",
                    "colors_json": json.dumps(["#ff00", "#ffffff"]),
                }
            )
        self.assertIn("Invalid hex color format", str(ctx.exception))
