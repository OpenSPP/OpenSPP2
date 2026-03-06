# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for statistics discovery endpoint."""

from odoo.tests.common import TransactionCase


class TestStatisticsEndpoint(TransactionCase):
    """Test statistics discovery endpoint logic."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Get or create categories (may already exist from demo data)
        Category = cls.env["spp.metric.category"]
        cls.demographics_category = Category.search([("code", "=", "demographics")], limit=1)
        if not cls.demographics_category:
            cls.demographics_category = Category.create(
                {
                    "name": "Demographics",
                    "code": "demographics",
                    "icon": "fa-users",
                    "sequence": 10,
                }
            )

        cls.vulnerability_category = Category.search([("code", "=", "vulnerability")], limit=1)
        if not cls.vulnerability_category:
            cls.vulnerability_category = Category.create(
                {
                    "name": "Vulnerability",
                    "code": "vulnerability",
                    "icon": "fa-shield-alt",
                    "sequence": 20,
                }
            )

        # Create a CEL variable
        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_stat_endpoint_var",
                "cel_accessor": "test_stat_endpoint",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        # Create GIS-published statistics
        cls.gis_stat_1 = cls.env["spp.indicator"].create(
            {
                "name": "total_households_disc",
                "label": "Total Households",
                "description": "Count of all registered households",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "unit": "households",
                "is_published_gis": True,
                "category_id": cls.demographics_category.id,
            }
        )

        cls.gis_stat_2 = cls.env["spp.indicator"].create(
            {
                "name": "disabled_members_disc",
                "label": "Disabled Members",
                "description": "Count of members with disability",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "unit": "people",
                "is_published_gis": True,
                "category_id": cls.vulnerability_category.id,
            }
        )

        # Non-GIS statistic (should not appear)
        cls.non_gis_stat = cls.env["spp.indicator"].create(
            {
                "name": "dashboard_only_disc",
                "label": "Dashboard Only",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "is_published_dashboard": True,
                "is_published_gis": False,
            }
        )

    def test_get_published_by_category_returns_gis_stats(self):
        """Test that get_published_by_category returns GIS-published stats."""
        Statistic = self.env["spp.indicator"]
        by_category = Statistic.get_published_by_category("gis")

        # Should include demographics and vulnerability categories
        self.assertIn("demographics", by_category)
        self.assertIn("vulnerability", by_category)

        # Demographics should contain total_households
        demo_names = [s.name for s in by_category["demographics"]]
        self.assertIn("total_households_disc", demo_names)

        # Vulnerability should contain disabled_members
        vuln_names = [s.name for s in by_category["vulnerability"]]
        self.assertIn("disabled_members_disc", vuln_names)

    def test_non_gis_stats_excluded(self):
        """Test that non-GIS statistics are excluded."""
        Statistic = self.env["spp.indicator"]
        by_category = Statistic.get_published_by_category("gis")

        # Collect all stat names across categories
        all_names = []
        for stats in by_category.values():
            all_names.extend(s.name for s in stats)

        self.assertNotIn("dashboard_only_disc", all_names)

    def test_statistic_to_dict(self):
        """Test that statistic to_dict returns expected fields."""
        stat_dict = self.gis_stat_1.to_dict("gis")

        self.assertEqual(stat_dict["name"], "total_households_disc")
        self.assertEqual(stat_dict["label"], "Total Households")
        self.assertEqual(stat_dict["format"], "count")
        self.assertEqual(stat_dict["unit"], "households")
        self.assertEqual(stat_dict["category"], "demographics")
        self.assertIn("description", stat_dict)

    def test_statistics_schema_validation(self):
        """Test that the Pydantic response schema works."""
        from ..schemas.statistics import (
            StatisticCategoryInfo,
            StatisticInfo,
            StatisticsListResponse,
        )

        response = StatisticsListResponse(
            categories=[
                StatisticCategoryInfo(
                    code="demographics",
                    name="Demographics",
                    icon="fa-users",
                    statistics=[
                        StatisticInfo(
                            name="total_households",
                            label="Total Households",
                            description="Count of all households",
                            format="count",
                            unit="households",
                        )
                    ],
                )
            ],
            total_count=1,
        )

        self.assertEqual(len(response.categories), 1)
        self.assertEqual(response.categories[0].code, "demographics")
        self.assertEqual(len(response.categories[0].statistics), 1)
        self.assertEqual(response.total_count, 1)

    def test_statistic_info_schema(self):
        """Test StatisticInfo schema with optional fields."""
        from ..schemas.statistics import StatisticInfo

        # Minimal
        info = StatisticInfo(
            name="test",
            label="Test",
            format="count",
        )
        self.assertIsNone(info.description)
        self.assertIsNone(info.unit)

        # Full
        info_full = StatisticInfo(
            name="test",
            label="Test",
            description="A test stat",
            format="sum",
            unit="units",
        )
        self.assertEqual(info_full.description, "A test stat")
        self.assertEqual(info_full.unit, "units")

    def test_inactive_stats_excluded(self):
        """Test that inactive statistics are excluded from published list."""
        Statistic = self.env["spp.indicator"]

        # Create an inactive GIS stat
        inactive_stat = Statistic.create(
            {
                "name": "inactive_gis_disc",
                "label": "Inactive GIS Stat",
                "variable_id": self.cel_variable.id,
                "format": "count",
                "is_published_gis": True,
                "active": False,
            }
        )

        by_category = Statistic.get_published_by_category("gis")

        all_names = []
        for stats in by_category.values():
            all_names.extend(s.name for s in stats)

        self.assertNotIn("inactive_gis_disc", all_names)

        # Cleanup
        inactive_stat.unlink()


class TestStatisticsScopeAccess(TransactionCase):
    """Tests for the statistics OAuth scope on GIS endpoints.

    Clients with either gis:read or statistics:read should be able to
    access the statistics batch endpoint.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.ApiClient = cls.env["spp.api.client"]
        cls.ApiScope = cls.env["spp.api.client.scope"]
        # Create a partner for API client (required field)
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Test Scope Organization",
            }
        )
        # Get or create organization type (required field)
        cls.org_type = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})

    def _create_client_with_scopes(self, scopes):
        """Create an API client with given scopes.

        Args:
            scopes: list of (resource, action) tuples
        """
        client = self.ApiClient.create(
            {
                "name": f"Test Client {len(scopes)}",
                "client_id": f"test_client_{id(scopes)}",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type.id,
            }
        )
        for resource, action in scopes:
            self.ApiScope.create(
                {
                    "client_id": client.id,
                    "resource": resource,
                    "action": action,
                }
            )
        return client

    def test_statistics_scope_grants_access(self):
        """Test that statistics:read scope exists and can be checked."""
        client = self._create_client_with_scopes([("statistics", "read")])
        self.assertTrue(client.has_scope("statistics", "read"))
        self.assertFalse(client.has_scope("gis", "read"))

    def test_gis_scope_grants_access(self):
        """Test that gis:read scope still works for statistics endpoints."""
        client = self._create_client_with_scopes([("gis", "read")])
        self.assertTrue(client.has_scope("gis", "read"))
        self.assertFalse(client.has_scope("statistics", "read"))

    def test_neither_scope_denies_access(self):
        """Test that client without gis or statistics scope is denied."""
        client = self._create_client_with_scopes([("individual", "read")])
        self.assertFalse(client.has_scope("gis", "read"))
        self.assertFalse(client.has_scope("statistics", "read"))

    def test_either_scope_accepted_by_check(self):
        """Test the combined scope check used by the endpoint."""
        # Statistics-only client
        stats_client = self._create_client_with_scopes([("statistics", "read")])
        has_access = stats_client.has_scope("gis", "read") or stats_client.has_scope("statistics", "read")
        self.assertTrue(has_access)

        # GIS-only client
        gis_client = self._create_client_with_scopes([("gis", "read")])
        has_access = gis_client.has_scope("gis", "read") or gis_client.has_scope("statistics", "read")
        self.assertTrue(has_access)

        # No relevant scope
        other_client = self._create_client_with_scopes([("individual", "read")])
        has_access = other_client.has_scope("gis", "read") or other_client.has_scope("statistics", "read")
        self.assertFalse(has_access)
