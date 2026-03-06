# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for shared scope builder utilities."""

from odoo.addons.spp_aggregation.services import (
    build_area_scope,
    build_cel_scope,
    build_explicit_scope,
)

from .common import AggregationTestCase


class TestScopeBuilder(AggregationTestCase):
    """Tests for scope builder utility functions."""

    def test_build_explicit_scope_with_list(self):
        """Test building explicit scope with list of partner IDs."""
        partner_ids = [1, 2, 3, 4, 5]
        scope = build_explicit_scope(partner_ids)

        self.assertEqual(scope["scope_type"], "explicit")
        self.assertEqual(scope["explicit_partner_ids"], [1, 2, 3, 4, 5])
        self.assertIsInstance(scope["explicit_partner_ids"], list)

    def test_build_explicit_scope_with_set(self):
        """Test building explicit scope with set of partner IDs."""
        partner_ids = {5, 4, 3, 2, 1}
        scope = build_explicit_scope(partner_ids)

        self.assertEqual(scope["scope_type"], "explicit")
        self.assertIsInstance(scope["explicit_partner_ids"], list)
        # Convert both to sets for comparison since set order is not guaranteed
        self.assertEqual(set(scope["explicit_partner_ids"]), {1, 2, 3, 4, 5})

    def test_build_explicit_scope_with_empty_list(self):
        """Test building explicit scope with empty list."""
        scope = build_explicit_scope([])

        self.assertEqual(scope["scope_type"], "explicit")
        self.assertEqual(scope["explicit_partner_ids"], [])

    def test_build_area_scope_with_children(self):
        """Test building area scope with child areas included."""
        scope = build_area_scope(area_id=123, include_children=True)

        self.assertEqual(scope["scope_type"], "area")
        self.assertEqual(scope["area_id"], 123)
        self.assertTrue(scope["include_child_areas"])

    def test_build_area_scope_without_children(self):
        """Test building area scope without child areas."""
        scope = build_area_scope(area_id=456, include_children=False)

        self.assertEqual(scope["scope_type"], "area")
        self.assertEqual(scope["area_id"], 456)
        self.assertFalse(scope["include_child_areas"])

    def test_build_area_scope_default_includes_children(self):
        """Test building area scope defaults to including children."""
        scope = build_area_scope(area_id=789)

        self.assertEqual(scope["scope_type"], "area")
        self.assertEqual(scope["area_id"], 789)
        self.assertTrue(scope["include_child_areas"])

    def test_build_cel_scope_with_default_profile(self):
        """Test building CEL scope with default profile."""
        scope = build_cel_scope("partner.age > 18")

        self.assertEqual(scope["scope_type"], "cel")
        self.assertEqual(scope["cel_expression"], "partner.age > 18")
        self.assertEqual(scope["cel_profile"], "registry_individuals")

    def test_build_cel_scope_with_custom_profile(self):
        """Test building CEL scope with custom profile."""
        scope = build_cel_scope("partner.is_group == true", profile="registry_groups")

        self.assertEqual(scope["scope_type"], "cel")
        self.assertEqual(scope["cel_expression"], "partner.is_group == true")
        self.assertEqual(scope["cel_profile"], "registry_groups")

    def test_explicit_scope_resolves_correctly(self):
        """Test that explicit scope built by utility resolves correctly."""
        # Create some test registrants
        test_registrants = self.registrants[:5]
        scope = build_explicit_scope(test_registrants.ids)

        # Resolve the scope using the resolver
        resolver = self.env["spp.aggregation.scope.resolver"]
        resolved_ids = resolver.resolve(scope)

        self.assertEqual(set(resolved_ids), set(test_registrants.ids))

    def test_area_scope_resolves_correctly(self):
        """Test that area scope built by utility resolves correctly."""
        scope = build_area_scope(area_id=self.area_district.id, include_children=False)

        # Resolve the scope using the resolver
        resolver = self.env["spp.aggregation.scope.resolver"]
        resolved_ids = resolver.resolve(scope)

        # Check all returned IDs are registrants in the district
        partners = self.env["res.partner"].browse(resolved_ids)
        for partner in partners:
            self.assertEqual(partner.area_id, self.area_district)

    def test_scope_compatible_with_aggregation_service(self):
        """Test that scopes built by utilities work with aggregation service."""
        # Create explicit scope for first 10 registrants
        test_registrants = self.registrants[:10]
        scope = build_explicit_scope(test_registrants.ids)

        # Compute aggregation using the scope
        aggregation_service = self.env["spp.aggregation.service"]
        result = aggregation_service.compute_aggregation(
            scope=scope,
            statistics=["count"],
            context="test",
        )

        # Verify result structure
        self.assertIn("total_count", result)
        self.assertEqual(result["total_count"], 10)
        self.assertIn("statistics", result)
        self.assertIn("count", result["statistics"])
