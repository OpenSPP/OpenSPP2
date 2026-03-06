# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from .common import AnalyticsTestCase


class TestScopeResolver(AnalyticsTestCase):
    """Tests for spp.analytics.scope.resolver service."""

    def test_resolve_explicit_scope(self):
        """Test resolving explicit partner IDs."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(scope)
        self.assertEqual(set(ids), set(self.registrants[:5].ids))

    def test_resolve_inline_explicit_scope(self):
        """Test resolving inline explicit scope definition."""
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:3].ids,
            }
        )
        self.assertEqual(set(ids), set(self.registrants[:3].ids))

    def test_resolve_area_scope(self):
        """Test resolving area scope."""
        scope = self.create_scope(
            "area",
            area_id=self.area_district.id,
            include_child_areas=False,
        )
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(scope)

        # Check all returned IDs are registrants in the district
        partners = self.env["res.partner"].browse(ids)
        for partner in partners:
            self.assertEqual(partner.area_id, self.area_district)

    def test_resolve_area_scope_with_children(self):
        """Test resolving area scope including child areas."""
        # First add some registrants to parent area
        self.env["res.partner"].create(
            {
                "name": "Regional Registrant",
                "is_registrant": True,
                "area_id": self.area_region.id,
            }
        )

        scope = self.create_scope(
            "area",
            area_id=self.area_region.id,
            include_child_areas=True,
        )
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(scope)

        # Should include registrants from both region and district
        partners = self.env["res.partner"].browse(ids)
        area_ids = partners.mapped("area_id.id")
        self.assertIn(self.area_region.id, area_ids)
        self.assertIn(self.area_district.id, area_ids)

    def test_resolve_area_tag_scope(self):
        """Test resolving area tag scope."""
        scope = self.create_scope(
            "area_tag",
            area_tag_ids=[(6, 0, [self.tag_urban.id])],
        )
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(scope)

        # Should find registrants in urban-tagged areas
        self.assertGreater(len(ids), 0)

    def test_resolve_multiple_scopes_union(self):
        """Test resolving multiple scopes with union."""
        scope1 = self.create_scope(
            "explicit",
            name="Scope 1",
            explicit_partner_ids=[(6, 0, self.registrants[:3].ids)],
        )
        scope2 = self.create_scope(
            "explicit",
            name="Scope 2",
            explicit_partner_ids=[(6, 0, self.registrants[2:5].ids)],
        )

        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve_multiple([scope1, scope2])

        # Union: 0,1,2 + 2,3,4 = 0,1,2,3,4
        self.assertEqual(set(ids), set(self.registrants[:5].ids))

    def test_resolve_multiple_scopes_intersect(self):
        """Test resolving multiple scopes with intersection."""
        scope1 = self.create_scope(
            "explicit",
            name="Scope 1",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        scope2 = self.create_scope(
            "explicit",
            name="Scope 2",
            explicit_partner_ids=[(6, 0, self.registrants[3:8].ids)],
        )

        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve_intersect([scope1, scope2])

        # Intersection: 0-4 ∩ 3-7 = 3,4
        self.assertEqual(set(ids), set(self.registrants[3:5].ids))

    def test_resolve_empty_scope_returns_empty(self):
        """Test that resolving empty scopes returns empty list."""
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve_multiple([])
        self.assertEqual(ids, [])

    def test_resolve_spatial_polygon_without_bridge(self):
        """Test spatial polygon returns empty without bridge module."""
        scope = self.create_scope(
            "spatial_polygon",
            geometry_geojson='{"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
        )
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(scope)
        # Without PostGIS bridge, returns empty
        self.assertEqual(ids, [])

    def test_resolve_inline_area_scope(self):
        """Test resolving inline area scope definition."""
        resolver = self.env["spp.analytics.scope.resolver"]
        ids = resolver.resolve(
            {
                "scope_type": "area",
                "area_id": self.area_district.id,
                "include_child_areas": False,
            }
        )
        self.assertGreater(len(ids), 0)


class TestScopeResolverPublicUser(AnalyticsTestCase):
    """Tests for scope resolver running as public user (uid:3).

    The scope resolver must work for unprivileged callers because it uses
    sudo() internally for model reads (res.partner, spp.area).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.public_user = cls.env.ref("base.public_user")

    def test_resolve_explicit_scope_as_public_user(self):
        """Test that explicit scope resolution works as public user."""
        resolver = self.env["spp.analytics.scope.resolver"].with_user(self.public_user)
        ids = resolver.resolve(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:5].ids,
            }
        )
        self.assertEqual(set(ids), set(self.registrants[:5].ids))

    def test_resolve_area_scope_as_public_user(self):
        """Test that area scope resolution works as public user."""
        resolver = self.env["spp.analytics.scope.resolver"].with_user(self.public_user)
        ids = resolver.resolve(
            {
                "scope_type": "area",
                "area_id": self.area_district.id,
                "include_child_areas": False,
            }
        )
        self.assertGreater(len(ids), 0)

    def test_resolve_area_tag_scope_as_public_user(self):
        """Test that area tag scope resolution works as public user."""
        resolver = self.env["spp.analytics.scope.resolver"].with_user(self.public_user)
        ids = resolver.resolve(
            {
                "scope_type": "area_tag",
                "area_tag_ids": [self.tag_urban.id],
            }
        )
        self.assertGreater(len(ids), 0)
