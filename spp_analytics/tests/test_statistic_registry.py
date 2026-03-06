# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class TestStatisticRegistry(TransactionCase):
    """Tests for spp.analytics.indicator.registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stat_registry = cls.env["spp.analytics.indicator.registry"]

        # Create test registrants
        cls.registrants = cls.env["res.partner"]
        for i in range(10):
            cls.registrants |= cls.env["res.partner"].create(
                {
                    "name": f"Test Registrant {i}",
                    "is_registrant": True,
                }
            )

    def test_compute_count_builtin(self):
        """Test that count builtin returns correct count."""
        result = self.stat_registry.compute("count", self.registrants.ids)
        self.assertEqual(result, 10)

    def test_compute_count_builtin_empty(self):
        """Test that count returns 0 for empty list."""
        result = self.stat_registry.compute("count", [])
        self.assertEqual(result, 0)

    def test_compute_gini_builtin(self):
        """Test that gini builtin returns None (placeholder)."""
        result = self.stat_registry.compute("gini", self.registrants.ids)
        self.assertIsNone(result)

    def test_compute_gini_coefficient_builtin(self):
        """Test that gini_coefficient is an alias for gini."""
        result = self.stat_registry.compute("gini_coefficient", self.registrants.ids)
        self.assertIsNone(result)

    def test_compute_unknown_statistic(self):
        """Test that unknown statistic returns None with warning."""
        with self.assertLogs("odoo.addons.spp_analytics.models.statistic_registry", level="WARNING") as log:
            result = self.stat_registry.compute("nonexistent_stat", self.registrants.ids)
            self.assertIsNone(result)
            self.assertTrue(any("Unknown statistic: nonexistent_stat" in msg for msg in log.output))

    def test_list_available_includes_builtins(self):
        """Test that list_available includes builtin statistics."""
        available = self.stat_registry.list_available()

        # Should include count and gini
        stat_names = [s["name"] for s in available]
        self.assertIn("count", stat_names)
        self.assertIn("gini", stat_names)
        self.assertIn("gini_coefficient", stat_names)

        # Check structure
        count_stat = next(s for s in available if s["name"] == "count")
        self.assertEqual(count_stat["label"], "Total Count")
        self.assertEqual(count_stat["source"], "builtin")


class TestStatisticRegistryIntegration(TransactionCase):
    """Integration tests for statistic registry with spp.indicator and spp.cel.variable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stat_registry = cls.env["spp.analytics.indicator.registry"]

        # Create test registrants
        cls.registrants = cls.env["res.partner"]
        for i in range(5):
            cls.registrants |= cls.env["res.partner"].create(
                {
                    "name": f"Test Registrant {i}",
                    "is_registrant": True,
                }
            )

    def test_compute_from_cel_variable(self):
        """Test computing statistic from spp.cel.variable."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # Create a simple CEL variable
        self.env["spp.cel.variable"].create(
            {
                "name": "test_registry_var",
                "cel_accessor": "test_registry_var",
                "source_type": "computed",
                "cel_expression": "r.is_registrant == true",
                "value_type": "number",
                "state": "active",
            }
        )

        # Compute via registry
        result = self.stat_registry.compute("test_registry_var", self.registrants.ids)

        # Should count registrants matching the expression
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_compute_from_statistic_model(self):
        """Test computing statistic from spp.indicator via variable."""
        if "spp.indicator" not in self.env:
            self.skipTest("spp_indicator module not installed")
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # Create CEL variable
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_registry_stat_var",
                "cel_accessor": "test_registry_stat_var",
                "source_type": "computed",
                "cel_expression": "r.is_registrant == true",
                "value_type": "number",
                "state": "active",
            }
        )

        # Create statistic that uses the variable
        self.env["spp.indicator"].create(
            {
                "name": "test_registry_stat",
                "label": "Test Registry Statistic",
                "variable_id": variable.id,
                "is_published_api": True,
            }
        )

        # Compute via registry using statistic name
        result = self.stat_registry.compute("test_registry_stat", self.registrants.ids)

        # Should compute via the variable
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)

    def test_list_available_includes_statistics(self):
        """Test that list_available includes spp.indicator records."""
        if "spp.indicator" not in self.env:
            self.skipTest("spp_indicator module not installed")
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # Create a statistic
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_list_var",
                "cel_accessor": "test_list_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )
        self.env["spp.indicator"].create(
            {
                "name": "test_list_stat",
                "label": "Test List Statistic",
                "variable_id": variable.id,
                "is_published_api": True,
                "active": True,
            }
        )

        available = self.stat_registry.list_available()

        # Should include the statistic
        stat_names = [s["name"] for s in available]
        self.assertIn("test_list_stat", stat_names)

        # Check structure
        test_stat = next(s for s in available if s["name"] == "test_list_stat")
        self.assertEqual(test_stat["label"], "Test List Statistic")
        self.assertEqual(test_stat["source"], "statistic")

    def test_list_available_includes_variables(self):
        """Test that list_available can find CEL variables."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        available = self.stat_registry.list_available()

        # Should at least include builtins
        self.assertGreater(len(available), 0)

        # Check structure is correct for all items
        for item in available:
            self.assertIn("name", item)
            self.assertIn("source", item)
            self.assertIn(item["source"], ["builtin", "statistic", "variable"])

    def test_compute_from_variable_empty_registrants(self):
        """Test that computing with empty registrant list returns 0."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        self.env["spp.cel.variable"].create(
            {
                "name": "test_empty_var",
                "cel_accessor": "test_empty_var",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_empty_var", [])
        self.assertEqual(result, 0)

    def test_compute_from_variable_handles_group_profile(self):
        """Test that registry uses correct CEL profile for group variables."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # Create groups
        groups = self.env["res.partner"]
        for i in range(3):
            groups |= self.env["res.partner"].create(
                {
                    "name": f"Test Group {i}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )

        # Create a group-targeted variable
        self.env["spp.cel.variable"].create(
            {
                "name": "test_group_var",
                "cel_accessor": "test_group_var",
                "source_type": "computed",
                "cel_expression": "r.is_group == true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_group_var", groups.ids)

        # Should compute successfully
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result, 0)


class TestStatisticRegistryMemberAggregate(TransactionCase):
    """Tests for member aggregate sum computation.

    Verifies that aggregate CEL variables (e.g., members.count(m, true))
    return the SUM of per-group values, not the count of groups.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stat_registry = cls.env["spp.analytics.indicator.registry"]

        if "spp.cel.variable" not in cls.env:
            return

        # Create 3 groups with different member counts
        cls.groups = cls.env["res.partner"]
        member_counts = [2, 3, 4]  # Total = 9 members
        for i, count in enumerate(member_counts):
            group = cls.env["res.partner"].create(
                {
                    "name": f"Aggregate Test Group {i}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            for j in range(count):
                individual = cls.env["res.partner"].create(
                    {
                        "name": f"Member {i}-{j}",
                        "is_registrant": True,
                        "is_group": False,
                    }
                )
                cls.env["spp.group.membership"].create(
                    {
                        "group": group.id,
                        "individual": individual.id,
                    }
                )
            cls.groups |= group

    def test_aggregate_count_returns_member_sum_not_group_count(self):
        """Test that members.count(m, true) returns total members, not group count."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        self.env["spp.cel.variable"].create(
            {
                "name": "test_agg_total_members",
                "cel_accessor": "test_agg_total_members",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_agg_total_members", self.groups.ids)

        # Should be 2+3+4=9 (sum of members), NOT 3 (count of groups)
        self.assertEqual(result, 9)

    def test_aggregate_count_with_filter(self):
        """Test that filtered member aggregates also return correct sums."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # All members match 'true' filter, so result should be same as total
        self.env["spp.cel.variable"].create(
            {
                "name": "test_agg_filtered",
                "cel_accessor": "test_agg_filtered",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_agg_filtered", self.groups.ids)
        self.assertEqual(result, 9)

    def test_aggregate_count_empty_registrants(self):
        """Test aggregate with empty registrant list returns 0."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        self.env["spp.cel.variable"].create(
            {
                "name": "test_agg_empty",
                "cel_accessor": "test_agg_empty",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_agg_empty", [])
        self.assertEqual(result, 0)

    def test_computed_variable_still_returns_count(self):
        """Test that non-aggregate (computed) variables still return group count."""
        if "spp.cel.variable" not in self.env:
            self.skipTest("spp_cel module not installed")

        # source_type=computed → compile_expression count path
        self.env["spp.cel.variable"].create(
            {
                "name": "test_computed_count",
                "cel_accessor": "test_computed_count",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        result = self.stat_registry.compute("test_computed_count", self.groups.ids)
        # Should be 3 (count of groups matching 'true'), not member sum
        self.assertEqual(result, 3)


class TestStatisticRegistryViaService(TransactionCase):
    """Tests that verify the service correctly uses the registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.analytics.service"]
        cls.registrants = cls.env["res.partner"]
        for i in range(5):
            cls.registrants |= cls.env["res.partner"].create(
                {
                    "name": f"Test Registrant {i}",
                    "is_registrant": True,
                }
            )

    def test_service_uses_registry_for_count(self):
        """Test that service delegates to registry for count statistic."""
        result = self.service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants.ids,
            },
            statistics=["count"],
        )

        self.assertIn("statistics", result)
        self.assertIn("count", result["statistics"])
        self.assertEqual(result["statistics"]["count"]["value"], 5)
        self.assertFalse(result["statistics"]["count"]["suppressed"])

    def test_service_uses_registry_for_unknown_statistic(self):
        """Test that service handles unknown statistics via registry."""
        result = self.service.compute_aggregation(
            {
                "scope_type": "explicit",
                "explicit_partner_ids": self.registrants.ids,
            },
            statistics=["nonexistent"],
        )

        self.assertIn("statistics", result)
        self.assertIn("nonexistent", result["statistics"])
        # Should have None value due to unknown statistic
        self.assertIsNone(result["statistics"]["nonexistent"]["value"])
