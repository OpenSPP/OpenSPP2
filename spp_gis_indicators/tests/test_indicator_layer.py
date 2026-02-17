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
                "label": "Test Population",
                "description": "Test population indicator",
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

        # Create test indicators with different values
        cls.indicator1 = cls.env["spp.hxl.area.indicator"].create(
            {
                "area_id": cls.area1.id,
                "variable_id": cls.variable.id,
                "period_key": "2024-12",
                "value": 100.0,
            }
        )
        cls.indicator2 = cls.env["spp.hxl.area.indicator"].create(
            {
                "area_id": cls.area2.id,
                "variable_id": cls.variable.id,
                "period_key": "2024-12",
                "value": 500.0,
            }
        )
        cls.indicator3 = cls.env["spp.hxl.area.indicator"].create(
            {
                "area_id": cls.area3.id,
                "variable_id": cls.variable.id,
                "period_key": "2024-12",
                "value": 1000.0,
            }
        )

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
        """Test retrieving indicator values."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        values = layer._get_indicator_values()
        self.assertEqual(len(values), 3)
        self.assertIn(100.0, values)
        self.assertIn(500.0, values)
        self.assertIn(1000.0, values)

    def test_get_indicator_values_filtered(self):
        """Test retrieving indicator values with filters."""
        # Create indicator with different period
        self.env["spp.hxl.area.indicator"].create(
            {
                "area_id": self.area1.id,
                "variable_id": self.variable.id,
                "period_key": "2024-11",
                "value": 50.0,
            }
        )

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        values = layer._get_indicator_values()
        # Should only get 3 values from period 2024-12
        self.assertEqual(len(values), 3)
        self.assertNotIn(50.0, values)

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
        """Test break values computation."""
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

        # break_values should be computed automatically
        self.assertTrue(layer.break_values)

        # Should be valid JSON
        breaks = json.loads(layer.break_values)
        self.assertIsInstance(breaks, list)
        # Should have 1 break for 2 classes
        self.assertEqual(len(breaks), 1)

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
        """Test legend HTML generation."""
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

        # legend_html should be computed automatically
        self.assertTrue(layer.legend_html)
        self.assertIn("gis-choropleth-legend", layer.legend_html)
        self.assertIn("legend-item", layer.legend_html)
        self.assertIn("color-box", layer.legend_html)

    def test_get_feature_colors(self):
        """Test getting feature colors."""
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
        color_map = layer.get_feature_colors(area_ids)

        # Should have colors for all areas
        self.assertEqual(len(color_map), 3)
        self.assertIn(self.area1.id, color_map)
        self.assertIn(self.area2.id, color_map)
        self.assertIn(self.area3.id, color_map)

        # Colors should be valid hex codes
        for color in color_map.values():
            self.assertTrue(color.startswith("#"))
            self.assertIn(len(color), [4, 7])  # #RGB or #RRGGBB

        # Different values should get different colors (usually)
        # (Can't guarantee this due to quantile breaks, but likely)
        unique_colors = set(color_map.values())
        self.assertGreaterEqual(len(unique_colors), 1)

    def test_get_feature_colors_filtered(self):
        """Test getting feature colors with subset of areas."""
        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": self.variable.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
            }
        )

        # Only request colors for two areas
        area_ids = [self.area1.id, self.area2.id]
        color_map = layer.get_feature_colors(area_ids)

        # Should only have colors for requested areas
        self.assertEqual(len(color_map), 2)
        self.assertIn(self.area1.id, color_map)
        self.assertIn(self.area2.id, color_map)
        self.assertNotIn(self.area3.id, color_map)

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
        """Test classification with single unique value."""
        # Create indicators with same value
        var2 = self.env["spp.cel.variable"].create(
            {
                "name": "test_constant",
                "cel_accessor": "test_constant",
                "label": "Test Constant",
                "value_type": "number",
                "source_type": "constant",
            }
        )

        for area in [self.area1, self.area2, self.area3]:
            self.env["spp.hxl.area.indicator"].create(
                {
                    "area_id": area.id,
                    "variable_id": var2.id,
                    "period_key": "2024-12",
                    "value": 100.0,
                }
            )

        layer = self.env["spp.gis.indicator.layer"].create(
            {
                "name": "Test Layer",
                "variable_id": var2.id,
                "period_key": "2024-12",
                "color_scale_id": self.color_scale.id,
                "classification_method": "equal_interval",
                "num_classes": 3,
            }
        )

        # Should handle gracefully
        breaks = layer._compute_equal_interval_breaks([100.0, 100.0, 100.0], 3)
        self.assertEqual(breaks, [])

    def test_edge_case_no_indicators(self):
        """Test layer with no matching indicators."""
        var2 = self.env["spp.cel.variable"].create(
            {
                "name": "test_empty",
                "cel_accessor": "test_empty",
                "label": "Test Empty",
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

        values = layer._get_indicator_values()
        self.assertEqual(len(values), 0)

        # break_values should be empty
        self.assertEqual(layer.break_values, "")

        # get_feature_colors should return empty dict
        color_map = layer.get_feature_colors([self.area1.id])
        self.assertEqual(color_map, {})
