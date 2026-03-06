# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestColorScale(TransactionCase):
    """Test GIS Color Scale model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ColorScale = cls.env["spp.gis.color.scale"]

        # Standard test colors
        cls.valid_colors = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]

    def test_create_color_scale(self):
        """Test basic color scale creation."""
        scale = self.ColorScale.create(
            {
                "name": "Test Blues",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        self.assertEqual(scale.name, "Test Blues")
        self.assertEqual(scale.scale_type, "sequential")
        self.assertTrue(scale.active)
        self.assertEqual(scale.sequence, 10)

    def test_all_scale_types(self):
        """Test all scale type selections."""
        for scale_type in ["sequential", "diverging", "categorical"]:
            scale = self.ColorScale.create(
                {
                    "name": f"Test {scale_type}",
                    "scale_type": scale_type,
                    "colors_json": json.dumps(self.valid_colors),
                }
            )
            self.assertEqual(scale.scale_type, scale_type)

    def test_colors_json_validation_invalid_json(self):
        """Test that invalid JSON is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Invalid JSON",
                    "scale_type": "sequential",
                    "colors_json": "not valid json",
                }
            )
        self.assertIn("Invalid JSON", str(ctx.exception))

    def test_colors_json_validation_not_array(self):
        """Test that non-array JSON is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Not Array",
                    "scale_type": "sequential",
                    "colors_json": json.dumps({"color": "#ff0000"}),
                }
            )
        self.assertIn("must be a JSON array", str(ctx.exception))

    def test_colors_json_validation_min_colors(self):
        """Test that at least 2 colors are required."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Single Color",
                    "scale_type": "sequential",
                    "colors_json": json.dumps(["#ff0000"]),
                }
            )
        self.assertIn("at least 2 colors", str(ctx.exception))

    def test_colors_json_validation_invalid_hex(self):
        """Test that invalid hex colors are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Invalid Hex",
                    "scale_type": "sequential",
                    "colors_json": json.dumps(["#ff0000", "notahex"]),
                }
            )
        self.assertIn("Invalid hex color format", str(ctx.exception))

    def test_colors_json_validation_color_not_string(self):
        """Test that non-string colors are rejected."""
        with self.assertRaises(ValidationError) as ctx:
            self.ColorScale.create(
                {
                    "name": "Non-string Color",
                    "scale_type": "sequential",
                    "colors_json": json.dumps(["#ff0000", 123]),
                }
            )
        self.assertIn("must be strings", str(ctx.exception))

    def test_colors_json_validation_short_hex(self):
        """Test that short hex format (#RGB) is accepted."""
        scale = self.ColorScale.create(
            {
                "name": "Short Hex",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#fff", "#000"]),
            }
        )
        self.assertEqual(scale.get_colors(), ["#fff", "#000"])

    def test_get_colors(self):
        """Test get_colors method returns parsed colors."""
        scale = self.ColorScale.create(
            {
                "name": "Get Colors Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        colors = scale.get_colors()
        self.assertEqual(colors, self.valid_colors)
        self.assertEqual(len(colors), 5)

    def test_get_colors_empty(self):
        """Test get_colors with no colors_json."""
        scale = self.ColorScale.create(
            {
                "name": "Empty Colors",
                "scale_type": "sequential",
                "colors_json": json.dumps(["#000", "#fff"]),
            }
        )
        # Clear the colors_json field
        scale.colors_json = ""

        colors = scale.get_colors()
        self.assertEqual(colors, [])

    def test_get_color_for_value_min(self):
        """Test get_color_for_value at minimum value."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(0, 0, 100)
        self.assertEqual(color, self.valid_colors[0])

    def test_get_color_for_value_max(self):
        """Test get_color_for_value at maximum value."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(100, 0, 100)
        self.assertEqual(color, self.valid_colors[-1])

    def test_get_color_for_value_below_min(self):
        """Test get_color_for_value below minimum."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(-10, 0, 100)
        self.assertEqual(color, self.valid_colors[0])

    def test_get_color_for_value_above_max(self):
        """Test get_color_for_value above maximum."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(150, 0, 100)
        self.assertEqual(color, self.valid_colors[-1])

    def test_get_color_for_value_equal_min_max(self):
        """Test get_color_for_value when min equals max."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(50, 50, 50)
        self.assertEqual(color, self.valid_colors[0])

    def test_get_color_for_value_midpoint(self):
        """Test get_color_for_value at midpoint."""
        scale = self.ColorScale.create(
            {
                "name": "Color Mapping",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        color = scale.get_color_for_value(50, 0, 100)
        # At 50%, should be middle color
        self.assertIn(color, self.valid_colors)

    def test_active_toggle(self):
        """Test active field functionality."""
        scale = self.ColorScale.create(
            {
                "name": "Active Test",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
            }
        )

        self.assertTrue(scale.active)

        scale.active = False
        self.assertFalse(scale.active)

        scale.active = True
        self.assertTrue(scale.active)

    def test_ordering(self):
        """Test scales are ordered by sequence and name."""
        scale1 = self.ColorScale.create(
            {
                "name": "B Scale",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
                "sequence": 20,
            }
        )

        scale2 = self.ColorScale.create(
            {
                "name": "A Scale",
                "scale_type": "sequential",
                "colors_json": json.dumps(self.valid_colors),
                "sequence": 10,
            }
        )

        scales = self.ColorScale.search([("id", "in", [scale1.id, scale2.id])])

        # scale2 (sequence 10) should come before scale1 (sequence 20)
        self.assertEqual(scales[0], scale2)
        self.assertEqual(scales[1], scale1)

    def test_description_field(self):
        """Test description field."""
        scale = self.ColorScale.create(
            {
                "name": "Described Scale",
                "scale_type": "diverging",
                "colors_json": json.dumps(self.valid_colors),
                "description": "A diverging scale for positive/negative values",
            }
        )

        self.assertEqual(scale.description, "A diverging scale for positive/negative values")

    def test_diverging_scale_center_color(self):
        """Test diverging scale returns center color for equal min/max."""
        # 5 colors: indices 0,1,2,3,4 - center is index 2
        diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        scale = self.ColorScale.create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(diverging_colors),
            }
        )

        # When min == max, should return center color
        color = scale.get_color_for_value(50, 50, 50)
        self.assertEqual(color, diverging_colors[2])  # Center color

    def test_diverging_scale_below_center(self):
        """Test diverging scale maps values below center to first half."""
        diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        scale = self.ColorScale.create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(diverging_colors),
            }
        )

        # Value at min should be first color
        color = scale.get_color_for_value(-100, -100, 100)
        self.assertEqual(color, diverging_colors[0])

        # Value slightly below center should be in lower half
        color = scale.get_color_for_value(-25, -100, 100)
        self.assertIn(color, diverging_colors[:3])  # Should be in lower half

    def test_diverging_scale_above_center(self):
        """Test diverging scale maps values above center to second half."""
        diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        scale = self.ColorScale.create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(diverging_colors),
            }
        )

        # Value at max should be last color
        color = scale.get_color_for_value(100, -100, 100)
        self.assertEqual(color, diverging_colors[-1])

        # Value slightly above center should be in upper half
        color = scale.get_color_for_value(25, -100, 100)
        self.assertIn(color, diverging_colors[2:])  # Should be in upper half

    def test_diverging_scale_at_center(self):
        """Test diverging scale at center point returns center color."""
        diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        scale = self.ColorScale.create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(diverging_colors),
            }
        )

        # Value exactly at center (0 for -100 to 100 range)
        color = scale.get_color_for_value(0, -100, 100)
        # Should be center or close to center
        center_idx = len(diverging_colors) // 2
        self.assertIn(color, diverging_colors[center_idx - 1 : center_idx + 2])

    def test_diverging_scale_custom_center(self):
        """Test diverging scale with custom center point."""
        diverging_colors = ["#d73027", "#fc8d59", "#ffffbf", "#91bfdb", "#4575b4"]
        scale = self.ColorScale.create(
            {
                "name": "Diverging Test",
                "scale_type": "diverging",
                "colors_json": json.dumps(diverging_colors),
            }
        )

        # Custom center at 25 (not midpoint of 0-100)
        # Value below center should map to lower colors
        color = scale.get_color_for_value(10, 0, 100, center=25)
        self.assertIn(color, diverging_colors[:3])

        # Value above center should map to upper colors
        color = scale.get_color_for_value(75, 0, 100, center=25)
        self.assertIn(color, diverging_colors[2:])
