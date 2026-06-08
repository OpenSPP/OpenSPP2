# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestIndicatorLayer(TransactionCase):
    """Test GIS Indicator Layer functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test color scale
        cls.color_scale = cls.env["spp.gis.color.scale"].create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
            }
        )

        # Create test CEL variable
        # Required fields: name, cel_accessor, value_type, source_type
        cls.variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_population",
                "cel_accessor": "test_population",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        # Create test areas (spp.area uses draft_name, name is computed)
        cls.area1 = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area 1",
                "code": "TA1",
            }
        )
        cls.area2 = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area 2",
                "code": "TA2",
            }
        )
        cls.area3 = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area 3",
                "code": "TA3",
            }
        )

        # NOTE: The area-indicator data source (spp.hxl.area.indicator) was removed
        # along with spp_hxl_area. Indicator-driven values/colors are disabled, so
        # the tests below assert the disabled contract (empty values/colors) rather
        # than creating indicator records. See internal plan remove-hxl-modules.md.

    def test_create_indicator_layer(self):
        """Test basic indicator layer creation."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Population Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 3,
            }
        )

        self.assertEqual(layer.name, "Test Population Layer")
        self.assertEqual(layer.variable_id, self.variable)
        self.assertEqual(layer.period_key, "2024-12")
        self.assertEqual(layer.color_scale_id, self.color_scale)
        self.assertTrue(layer.active)

    def test_num_classes_validation(self):
        """Test that num_classes is validated."""
        # Too few classes
        with self.assertRaises(ValidationError):
            self.env["spp.gis.indicator.layer"].create(
                {
                    "name": "Test Layer",
                    "variable_id": self.variable.id,
                    "color_scale_id": self.color_scale.id,
                    "num_classes": 1,
                }
            )

        # Too many classes
        with self.assertRaises(ValidationError):
            self.env["spp.gis.indicator.layer"].create(
                {
                    "name": "Test Layer",
                    "variable_id": self.variable.id,
                    "color_scale_id": self.color_scale.id,
                    "num_classes": 15,
                }
            )

    def test_manual_breaks_validation(self):
        """Test manual breaks validation."""
        # Missing manual breaks
        with self.assertRaises(ValidationError):
            self.env["spp.gis.indicator.layer"].create(
                {
                    "name": "Test Layer",
                    "variable_id": self.variable.id,
                    "color_scale_id": self.color_scale.id,
                    "classification_method": "manual",
                    "manual_breaks": "",
                }
            )

        # Invalid format
        with self.assertRaises(ValidationError):
            self.env["spp.gis.indicator.layer"].create(
                {
                    "name": "Test Layer",
                    "variable_id": self.variable.id,
                    "color_scale_id": self.color_scale.id,
                    "classification_method": "manual",
                    "manual_breaks": "abc,def",
                }
            )

        # Not in ascending order
        with self.assertRaises(ValidationError):
            self.env["spp.gis.indicator.layer"].create(
                {
                    "name": "Test Layer",
                    "variable_id": self.variable.id,
                    "color_scale_id": self.color_scale.id,
                    "classification_method": "manual",
                    "manual_breaks": "100,50,200",
                }
            )

    def test_manual_breaks_valid(self):
        """Test valid manual breaks."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
                "classification_method": "manual",
                "manual_breaks": "200,500,800",
            }
        )

        self.assertEqual(layer.manual_breaks, "200,500,800")

    def test_get_indicator_values(self):
        """Indicator values are disabled (data source removed) -> empty list."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        self.assertEqual(layer._get_indicator_values(), [])

    def test_get_indicator_values_filtered(self):
        """Period/incident filters still return nothing while the source is disabled."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        self.assertEqual(layer._get_indicator_values(), [])

    def test_compute_quantile_breaks(self):
        """Test quantile break computation."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 3,
            }
        )

        values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        breaks = layer._compute_quantile_breaks(values, 3)

        # Should have 2 breaks for 3 classes
        self.assertEqual(len(breaks), 2)
        # Breaks should be between min and max
        self.assertTrue(100 < breaks[0] < 1000)
        self.assertTrue(100 < breaks[1] < 1000)
        # Breaks should be ordered
        self.assertTrue(breaks[0] < breaks[1])

    def test_compute_equal_interval_breaks(self):
        """Test equal interval break computation."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "color_scale_id": self.color_scale.id,
            }
        )

        values = [100, 200, 300, 400, 500]
        breaks = layer._compute_equal_interval_breaks(values, 4)

        # Should have 3 breaks for 4 classes
        self.assertEqual(len(breaks), 3)
        # Interval should be 100 (400 range / 4 classes)
        self.assertAlmostEqual(breaks[0], 200.0, places=1)
        self.assertAlmostEqual(breaks[1], 300.0, places=1)
        self.assertAlmostEqual(breaks[2], 400.0, places=1)

    def test_compute_break_values(self):
        """Data-driven (quantile) breaks are empty while the indicator source is disabled."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 2,
            }
        )

        # No indicator data -> no computed breaks
        self.assertEqual(layer.break_values, "")

    def test_compute_break_values_manual(self):
        """Test break values with manual classification."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "manual",
                "manual_breaks": "200,600",
            }
        )

        # break_values should be computed from manual_breaks
        self.assertTrue(layer.break_values)

        breaks = json.loads(layer.break_values)
        self.assertEqual(len(breaks), 2)
        self.assertEqual(breaks[0], 200.0)
        self.assertEqual(breaks[1], 600.0)

    def test_compute_legend_html(self):
        """Legend HTML generation works from manual breaks (independent of indicator data)."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "manual",
                "manual_breaks": "200,500",
            }
        )

        # legend_html should be computed automatically from manual breaks
        self.assertTrue(layer.legend_html)
        self.assertIn("gis-choropleth-legend", layer.legend_html)
        self.assertIn("legend-item", layer.legend_html)
        self.assertIn("color-box", layer.legend_html)

    def test_get_feature_colors(self):
        """Feature colors are disabled (data source removed) -> empty mapping."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "quantile",
                "num_classes": 3,
            }
        )

        area_ids = [self.area1.id, self.area2.id, self.area3.id]
        self.assertEqual(layer.get_feature_colors(area_ids), {})

    def test_get_feature_colors_filtered(self):
        """Requesting a subset of areas still yields nothing while the source is disabled."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        area_ids = [self.area1.id, self.area2.id]
        self.assertEqual(layer.get_feature_colors(area_ids), {})

    def test_parse_manual_breaks(self):
        """Test parsing manual break strings."""
        layer = self.env["spp.gis.indicator.layer"]

        # Valid breaks
        breaks = layer._parse_manual_breaks("10,50,100,500")
        self.assertEqual(breaks, [10.0, 50.0, 100.0, 500.0])

        # With whitespace
        breaks = layer._parse_manual_breaks("10, 50, 100, 500")
        self.assertEqual(breaks, [10.0, 50.0, 100.0, 500.0])

        # Empty string
        breaks = layer._parse_manual_breaks("")
        self.assertEqual(breaks, [])

        # Invalid format should raise
        with self.assertRaises(ValueError):
            layer._parse_manual_breaks("abc,def")

    def test_edge_case_single_value(self):
        """Equal-interval classification returns no breaks when all values are identical."""
        # Pure-function check, independent of the (disabled) indicator data source.
        layer = self.env["spp.gis.indicator.layer"]
        breaks = layer._compute_equal_interval_breaks([100.0, 100.0, 100.0], 3)
        self.assertEqual(breaks, [])

    def test_edge_case_no_indicators(self):
        """With the indicator source disabled, a layer reports no values/breaks/colors."""
        var2 = self.env["spp.cel.variable"].create(
            {
                "name": "test_empty",
                "cel_accessor": "test_empty",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": var2.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        self.assertEqual(layer._get_indicator_values(), [])

        # break_values should be empty
        self.assertEqual(layer.break_values, "")

        # get_feature_colors should return empty dict
        self.assertEqual(layer.get_feature_colors([self.area1.id]), {})
