# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, ValidationError

from .common import AnalyticsTestCase


class TestAnalyticsService(AnalyticsTestCase):
    """Tests for spp.analytics.service main entry point."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]

    def test_compute_aggregation_basic(self):
        """Test basic aggregation with explicit scope."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:10].ids)],
        )
        result = self.service.compute_aggregation(scope)

        self.assertEqual(result["total_count"], 10)
        self.assertIn("computed_at", result)
        self.assertIn("access_level", result)

    def test_compute_aggregation_with_scope_id(self):
        """Test aggregation using scope ID instead of record."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        result = self.service.compute_aggregation(scope.id)

        self.assertEqual(result["total_count"], 5)

    def test_compute_aggregation_with_inline_scope(self):
        """Test aggregation using inline scope definition."""
        result = self.service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:3].ids,
            }
        )

        self.assertEqual(result["total_count"], 3)

    def test_compute_aggregation_with_statistics(self):
        """Test aggregation with statistics requested."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:10].ids)],
        )
        result = self.service.compute_aggregation(scope, statistics=["count"])

        self.assertIn("statistics", result)
        self.assertIn("count", result["statistics"])
        self.assertEqual(result["statistics"]["count"]["value"], 10)

    def test_compute_aggregation_with_group_by(self):
        """Test aggregation with group_by breakdown."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants.ids)],
        )
        result = self.service.compute_aggregation(
            scope,
            group_by=["registrant_type"],
        )

        self.assertIn("breakdown", result)
        # Should have cells for groups and individuals
        self.assertGreater(len(result["breakdown"]), 0)

    def test_compute_aggregation_max_dimensions(self):
        """Test that too many dimensions raises error."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )

        with self.assertRaises(ValidationError):
            self.service.compute_aggregation(
                scope,
                group_by=["dim1", "dim2", "dim3", "dim4"],  # 4 > max 3
            )

    def test_compute_aggregation_unknown_dimension(self):
        """Test that unknown dimension raises error."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )

        with self.assertRaises(ValidationError):
            self.service.compute_aggregation(
                scope,
                group_by=["nonexistent_dimension"],
            )

    def test_compute_for_area(self):
        """Test convenience method for area-based aggregation."""
        result = self.service.compute_for_area(self.area_district.id)

        self.assertIn("total_count", result)
        self.assertGreater(result["total_count"], 0)

    def test_compute_for_expression(self):
        """Test convenience method for CEL expression aggregation."""
        result = self.service.compute_for_expression(
            cel_expression="r.is_group == false",
            profile="registry_individuals",
        )

        self.assertIn("total_count", result)

    def test_compute_fairness(self):
        """Test fairness computation through service."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:10].ids)],
        )
        result = self.service.compute_fairness(scope)

        self.assertIn("equity_score", result)
        self.assertIn("has_disparity", result)
        self.assertIn("overall_coverage", result)

    def test_compute_distribution(self):
        """Test distribution computation through service."""
        amounts = [100, 200, 300, 400, 500]
        result = self.service.compute_distribution(amounts)

        self.assertEqual(result["count"], 5)
        self.assertEqual(result["total"], 1500)
        self.assertIn("gini_coefficient", result)

    def test_privacy_enforced_on_result(self):
        """Test that privacy protection is applied to results."""
        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        result = self.service.compute_aggregation(scope)

        # For aggregate access, should not have individual IDs
        if result["access_level"] == "aggregate":
            self.assertNotIn("registrant_ids", result)
            self.assertNotIn("partner_ids", result)

    def test_statistic_suppression_uses_stricter_threshold(self):
        """Test top-level statistic suppression uses max(user_k, stat_k)."""
        if "spp.indicator" not in self.env:
            self.skipTest("spp_indicator module not installed")

        variable = self.env["spp.cel.variable"].create(
            {
                "name": "agg_suppression_test_var",
                "cel_accessor": "agg_suppression_test_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        self.env["spp.indicator"].create(
            {
                "name": "agg_suppression_test_stat",
                "label": "Aggregation Suppression Test",
                "variable_id": variable.id,
                "minimum_count": 2,  # lower than user rule
                "is_published_api": True,
            }
        )
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "Agg Suppression Rule k10",
                "access_level": "aggregate",
                "user_id": self.env.user.id,
                "minimum_k_anonymity": 10,
                "allow_inline_scopes": True,
            }
        )

        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )
        result = self.service.compute_aggregation(
            scope,
            statistics=["agg_suppression_test_stat"],
            context="api",
        )

        stat = result["statistics"]["agg_suppression_test_stat"]
        self.assertTrue(stat["suppressed"])
        self.assertEqual(stat["value"], "<10")


class TestAnalyticsServiceAccessControl(AnalyticsTestCase):
    """Tests for access control in aggregation service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test user for access control tests
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Test Aggregation User",
                "login": "test_agg_user",
                "email": "test_agg@example.com",
                "group_ids": [(4, cls.env.ref("base.group_user").id)],
            }
        )

    def test_access_rule_aggregate_only(self):
        """Test that aggregate-only users cannot see IDs."""
        # Create user-specific rule
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "Test Aggregate Rule",
                "access_level": "aggregate",
                "user_id": self.test_user.id,
            }
        )

        scope = self.create_scope(
            "explicit",
            explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
        )

        # Run as test user
        service = self.env["spp.analytics.service"].with_user(self.test_user)
        result = service.compute_aggregation(scope)

        self.assertEqual(result["access_level"], "aggregate")
        self.assertNotIn("registrant_ids", result)

    def test_access_rule_restricts_inline_scopes(self):
        """Test that inline scopes can be restricted."""
        # Create user-specific rule
        self.env["spp.analytics.access.rule"].create(
            {
                "name": "Test Restricted Rule",
                "access_level": "aggregate",
                "user_id": self.test_user.id,
                "allow_inline_scopes": False,
                "allowed_scope_types": "predefined",
            }
        )

        # Run as test user
        service = self.env["spp.analytics.service"].with_user(self.test_user)

        # Inline scope should be blocked
        with self.assertRaises(AccessError):
            service.compute_aggregation(
                {
                    "scope_type": "explicit",
                    "explicit_partner_ids": self.registrants[:3].ids,
                }
            )

    def test_access_rule_restricts_dimensions(self):
        """Test that dimensions can be restricted."""
        # Create dimension first
        dimension = self.env["spp.demographic.dimension"].search(
            [
                ("name", "=", "registrant_type"),
            ],
            limit=1,
        )

        if dimension:
            # Create user-specific rule with dimension restriction
            self.env["spp.analytics.access.rule"].create(
                {
                    "name": "Test Dimension Rule",
                    "access_level": "aggregate",
                    "user_id": self.test_user.id,
                    "max_group_by_dimensions": 1,
                }
            )

            scope = self.create_scope(
                "explicit",
                explicit_partner_ids=[(6, 0, self.registrants[:5].ids)],
            )

            # Run as test user
            service = self.env["spp.analytics.service"].with_user(self.test_user)

            # Request with 2 dimensions when max is 1
            with self.assertRaises(ValidationError):
                service.compute_aggregation(
                    scope,
                    group_by=["registrant_type", "area"],
                )


class TestAnalyticsServicePublicUser(AnalyticsTestCase):
    """Tests for aggregation service running as public user (uid:3).

    The GIS API runs as base.public_user which has no Odoo model permissions.
    The aggregation service must work for this user because internal config/data
    reads use sudo() while access level is determined from the calling user.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.public_user = cls.env.ref("base.public_user")

    def test_compute_aggregation_explicit_scope_as_public_user(self):
        """Test that public user can compute aggregation with explicit scope."""
        service = self.env["spp.analytics.service"].with_user(self.public_user)
        result = service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:5].ids,
            }
        )

        self.assertEqual(result["total_count"], 5)
        self.assertIn("access_level", result)
        self.assertIn("computed_at", result)

    def test_statistics_computation_as_public_user(self):
        """Test that statistics are computed for public user."""
        service = self.env["spp.analytics.service"].with_user(self.public_user)
        result = service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:10].ids,
            },
            statistics=["count"],
        )

        self.assertIn("statistics", result)
        self.assertIn("count", result["statistics"])
        self.assertEqual(result["statistics"]["count"]["value"], 10)

    def test_access_level_defaults_to_aggregate_for_public_user(self):
        """Test that public user gets aggregate access level by default."""
        service = self.env["spp.analytics.service"].with_user(self.public_user)
        result = service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:3].ids,
            }
        )

        self.assertEqual(result["access_level"], "aggregate")

    def test_no_registrant_ids_in_result_for_public_user(self):
        """Test that registrant IDs are not exposed to public user."""
        service = self.env["spp.analytics.service"].with_user(self.public_user)
        result = service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants[:5].ids,
            }
        )

        # Privacy enforcement should strip individual IDs for aggregate access
        self.assertNotIn("registrant_ids", result)
        self.assertNotIn("partner_ids", result)
