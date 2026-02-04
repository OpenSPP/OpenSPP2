"""Tests for GIS Color Scheme Model.

Tests cover:
- Color scheme creation and configuration
- Color interpolation methods
- Discrete color generation
- Preview gradient generation
- Default scheme selection
"""

from odoo.tests import TransactionCase


class TestColorScheme(TransactionCase):
    """Test cases for spp.gis.color.scheme model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get predefined color schemes
        cls.viridis = cls.env["spp.gis.color.scheme"].search([("code", "=", "viridis")], limit=1)
        cls.blues = cls.env["spp.gis.color.scheme"].search([("code", "=", "blues")], limit=1)
        cls.red_white_blue = cls.env["spp.gis.color.scheme"].search([("code", "=", "red_white_blue")], limit=1)
        cls.set1 = cls.env["spp.gis.color.scheme"].search([("code", "=", "set1")], limit=1)

    def test_01_predefined_schemes_exist(self):
        """Test that predefined color schemes are loaded."""
        schemes = self.env["spp.gis.color.scheme"].search([])
        self.assertTrue(len(schemes) > 0, "Color schemes should be loaded from data")

        # Check specific schemes exist
        self.assertTrue(self.viridis, "Viridis scheme should exist")
        self.assertTrue(self.blues, "Blues scheme should exist")

    def test_02_default_scheme(self):
        """Test default scheme selection."""
        default = self.env["spp.gis.color.scheme"].get_default_scheme()
        self.assertTrue(default, "Default scheme should be returned")

        # Viridis should be default
        if self.viridis:
            default_scheme = self.env["spp.gis.color.scheme"].search([("is_default", "=", True)], limit=1)
            if default_scheme:
                self.assertEqual(default_scheme.code, "viridis")

    def test_03_scheme_types(self):
        """Test different scheme types."""
        if self.viridis:
            self.assertEqual(self.viridis.scheme_type, "sequential")

        if self.red_white_blue:
            self.assertEqual(self.red_white_blue.scheme_type, "diverging")

        if self.set1:
            self.assertEqual(self.set1.scheme_type, "qualitative")

    def test_04_get_colors_list(self):
        """Test color list extraction."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        colors = self.viridis.get_colors_list()
        self.assertIsInstance(colors, list)
        self.assertTrue(len(colors) > 0)
        self.assertTrue(all(c.startswith("#") for c in colors))

    def test_05_get_discrete_colors_sequential(self):
        """Test discrete color generation for sequential scheme."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Test various counts
        for count in [2, 3, 4, 5, 10]:
            colors = self.viridis.get_discrete_colors(count)
            self.assertEqual(len(colors), count)
            self.assertTrue(all(c.startswith("#") for c in colors))

    def test_06_get_discrete_colors_diverging(self):
        """Test discrete color generation for diverging scheme."""
        if not self.red_white_blue:
            self.skipTest("Red-white-blue scheme not available")

        colors = self.red_white_blue.get_discrete_colors(5)
        self.assertEqual(len(colors), 5)
        self.assertTrue(all(c.startswith("#") for c in colors))

    def test_07_get_discrete_colors_qualitative(self):
        """Test discrete color generation for qualitative scheme."""
        if not self.set1:
            self.skipTest("Set1 scheme not available")

        colors = self.set1.get_discrete_colors(4)
        self.assertEqual(len(colors), 4)

        # For qualitative, colors should be distinct (not interpolated)
        base_colors = self.set1.get_colors_list()
        for color in colors:
            self.assertIn(color, base_colors)

    def test_08_interpolate_color_sequential(self):
        """Test color interpolation for sequential scheme."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Test at boundaries
        color_min = self.viridis.interpolate_color(0, 0, 1)
        color_max = self.viridis.interpolate_color(1, 0, 1)
        color_mid = self.viridis.interpolate_color(0.5, 0, 1)

        self.assertTrue(color_min.startswith("#"))
        self.assertTrue(color_max.startswith("#"))
        self.assertTrue(color_mid.startswith("#"))

        # Min and max should be different
        self.assertNotEqual(color_min, color_max)

    def test_09_interpolate_color_diverging(self):
        """Test color interpolation for diverging scheme."""
        if not self.red_white_blue:
            self.skipTest("Red-white-blue scheme not available")

        # For diverging, middle should be the center color
        color_neg = self.red_white_blue.interpolate_color(0, 0, 1)
        color_zero = self.red_white_blue.interpolate_color(0.5, 0, 1)
        color_pos = self.red_white_blue.interpolate_color(1, 0, 1)

        self.assertTrue(color_neg.startswith("#"))
        self.assertTrue(color_zero.startswith("#"))
        self.assertTrue(color_pos.startswith("#"))

    def test_10_interpolate_same_min_max(self):
        """Test interpolation when min equals max."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Should return middle color
        color = self.viridis.interpolate_color(5, 5, 5)
        self.assertTrue(color.startswith("#"))

    def test_11_interpolate_out_of_range(self):
        """Test interpolation with out-of-range values."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Values outside range should be clamped
        color_below = self.viridis.interpolate_color(-1, 0, 1)
        color_above = self.viridis.interpolate_color(2, 0, 1)

        self.assertTrue(color_below.startswith("#"))
        self.assertTrue(color_above.startswith("#"))

    def test_12_preview_gradient_sequential(self):
        """Test preview gradient for sequential scheme."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        self.viridis._compute_preview_gradient()
        preview = self.viridis.preview_gradient

        self.assertTrue(preview)
        self.assertIn("linear-gradient", preview)

    def test_13_preview_gradient_qualitative(self):
        """Test preview gradient for qualitative scheme."""
        if not self.set1:
            self.skipTest("Set1 scheme not available")

        self.set1._compute_preview_gradient()
        preview = self.set1.preview_gradient

        self.assertTrue(preview)
        # Qualitative should show discrete blocks, not gradient
        self.assertIn("display:inline-block", preview)

    def test_14_colorblind_safe_flag(self):
        """Test color-blind safe flag."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Viridis should be marked as colorblind safe
        self.assertTrue(self.viridis.is_colorblind_safe)

        # Check we can filter by this flag
        safe_schemes = self.env["spp.gis.color.scheme"].search([("is_colorblind_safe", "=", True)])
        self.assertTrue(len(safe_schemes) > 0)

    def test_15_create_custom_scheme(self):
        """Test creating a custom color scheme."""
        scheme = self.env["spp.gis.color.scheme"].create(
            {
                "name": "Custom Test Scheme",
                "code": "custom_test",
                "scheme_type": "sequential",
                "colors": '["#000000", "#ffffff"]',
                "is_colorblind_safe": False,
            }
        )

        self.assertEqual(scheme.name, "Custom Test Scheme")
        self.assertEqual(scheme.scheme_type, "sequential")

        colors = scheme.get_colors_list()
        self.assertEqual(colors, ["#000000", "#ffffff"])

        # Clean up
        scheme.unlink()

    def test_16_code_uniqueness(self):
        """Test that color scheme codes are unique."""
        from psycopg2 import IntegrityError

        from odoo.exceptions import ValidationError

        # Try to create scheme with duplicate code
        # Use try/except instead of assertRaises with tuple (Odoo 19 compatibility)
        with self.assertRaises(Exception) as cm:
            self.env["spp.gis.color.scheme"].create(
                {
                    "name": "Duplicate Code Test",
                    "code": "viridis",  # Already exists
                    "scheme_type": "sequential",
                    "colors": '["#ff0000"]',
                }
            )
        # Verify it's one of the expected exception types
        self.assertTrue(
            isinstance(cm.exception, (ValidationError, IntegrityError)),
            f"Expected ValidationError or IntegrityError, got {type(cm.exception).__name__}",
        )

    def test_17_hex_to_rgb_conversion(self):
        """Test hex to RGB conversion."""
        scheme = self.env["spp.gis.color.scheme"]

        # Test various hex colors
        self.assertEqual(scheme._hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(scheme._hex_to_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(scheme._hex_to_rgb("#ff0000"), (255, 0, 0))
        self.assertEqual(scheme._hex_to_rgb("#00ff00"), (0, 255, 0))
        self.assertEqual(scheme._hex_to_rgb("#0000ff"), (0, 0, 255))

    def test_18_interpolate_between_colors(self):
        """Test interpolation between two colors."""
        if not self.viridis:
            self.skipTest("Viridis scheme not available")

        # Black to white at 50% should be gray
        result = self.viridis._interpolate_between("#000000", "#ffffff", 0.5)
        # Should be approximately #808080 (middle gray)
        self.assertTrue(result.startswith("#"))
        self.assertEqual(len(result), 7)  # #rrggbb format

    def test_19_single_color_interpolation(self):
        """Test interpolation with single color scheme."""
        scheme = self.env["spp.gis.color.scheme"].create(
            {
                "name": "Single Color",
                "code": "single_test",
                "scheme_type": "sequential",
                "colors": '["#ff0000"]',
            }
        )

        color = scheme.interpolate_color(0.5, 0, 1)
        self.assertEqual(color, "#ff0000")

        # Clean up
        scheme.unlink()

    def test_20_empty_colors_handling(self):
        """Test handling of empty or invalid colors JSON."""
        scheme = self.env["spp.gis.color.scheme"].create(
            {
                "name": "Empty Colors",
                "code": "empty_test",
                "scheme_type": "sequential",
                "colors": "[]",
            }
        )

        # Should return fallback gray
        color = scheme.interpolate_color(0.5, 0, 1)
        self.assertEqual(color, "#808080")

        # Clean up
        scheme.unlink()
