# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError

from .common import AnalyticsTestCase


class TestAnalyticsScope(AnalyticsTestCase):
    """Tests for spp.analytics.scope model."""

    def test_create_cel_scope(self):
        """Test creating a CEL expression scope."""
        scope = self.create_scope(
            "cel",
            cel_expression="r.is_group == false",
            cel_profile="registry_individuals",
        )
        self.assertEqual(scope.scope_type, "cel")
        self.assertEqual(scope.cel_expression, "r.is_group == false")

    def test_create_area_scope(self):
        """Test creating an area scope."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
            include_child_areas=True,
        )
        self.assertEqual(scope.scope_type, "area")
        self.assertEqual(scope.area_id, self.area_district)

    def test_create_explicit_scope(self):
        """Test creating an explicit IDs scope."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        self.assertEqual(scope.scope_type, "explicit")
        self.assertEqual(len(scope.explicit_partner_ids), 5)

    def test_cel_scope_requires_expression(self):
        """CEL scope type must have a CEL expression."""
        with self.assertRaises(ValidationError):
            self.create_scope("cel")

    def test_area_scope_requires_area(self):
        """Area scope type must have an area."""
        with self.assertRaises(ValidationError):
            self.create_scope("area")

    def test_explicit_scope_requires_ids(self):
        """Explicit scope type must have partner IDs."""
        with self.assertRaises(ValidationError):
            self.create_scope("explicit")

    def test_spatial_polygon_requires_geojson(self):
        """Spatial polygon scope must have GeoJSON."""
        with self.assertRaises(ValidationError):
            self.create_scope("spatial_polygon")

    def test_spatial_polygon_validates_geojson(self):
        """Spatial polygon scope validates GeoJSON format."""
        with self.assertRaises(ValidationError):
            self.create_scope("spatial_polygon", geometry_geojson="not valid json")

        with self.assertRaises(ValidationError):
            self.create_scope(
                "spatial_polygon",
                geometry_geojson='{"type": "Point", "coordinates": [0, 0]}',
            )

    def test_spatial_buffer_requires_params(self):
        """Spatial buffer scope requires center and radius."""
        with self.assertRaises(ValidationError):
            self.create_scope("spatial_buffer")

        with self.assertRaises(ValidationError):
            self.create_scope(
                "spatial_buffer",
                buffer_center_latitude=0,
                buffer_center_longitude=0,
            )

    def test_spatial_buffer_validates_coords(self):
        """Spatial buffer validates coordinate ranges."""
        with self.assertRaises(ValidationError):
            self.create_scope(
                "spatial_buffer",
                buffer_center_latitude=100,  # Invalid
                buffer_center_longitude=0,
                buffer_radius_km=10,
            )

    def test_resolve_explicit_scope(self):
        """Test resolving explicit scope to IDs."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        ids = scope.resolve_registrant_ids()
        self.assertEqual(len(ids), 5)
        self.assertEqual(set(ids), set(self.registrants[:5].ids))

    def test_resolve_area_scope(self):
        """Test resolving area scope to IDs."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
            include_child_areas=False,
        )
        ids = scope.resolve_registrant_ids()
        # Should find registrants in district
        self.assertGreater(len(ids), 0)

    def test_registrant_count_computed(self):
        """Test that registrant count is computed."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        self.assertEqual(scope.registrant_count, 5)
