# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for CEL SQL generation for scale.

These tests verify the SQL generation path that enables scaling to millions of records:
- _domain_to_id_sql() - converts Odoo domains to SQL subqueries
- _exists_to_sql() - generates SQL for EXISTS operations
- _count_to_sql() - generates SQL for COUNT operations with HAVING
- _plan_to_sql() - dispatcher for SQL generation
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.tools.sql import SQL


class TestCelSqlGeneration(TransactionCase):
    """Test CEL SQL generation for scalability."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.executor = cls.env["spp.cel.executor"]
        cls.translator = cls.env["spp.cel.translator"]
        cls.service = cls.env["spp.cel.service"]

        # Create test households with members
        cls.household1 = cls.env["res.partner"].create(
            {
                "name": "SQL Test Household 1",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create members - one adult, one child
        cls.adult1 = cls.env["res.partner"].create(
            {
                "name": "SQL Test Adult 1",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=30 * 365),  # 30 years old
            }
        )
        cls.child1 = cls.env["res.partner"].create(
            {
                "name": "SQL Test Child 1",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=3 * 365),  # 3 years old
            }
        )

        # Create memberships
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household1.id,
                "individual": cls.adult1.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household1.id,
                "individual": cls.child1.id,
            }
        )

        # Create household without children
        cls.household2 = cls.env["res.partner"].create(
            {
                "name": "SQL Test Household 2",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.adult2 = cls.env["res.partner"].create(
            {
                "name": "SQL Test Adult 2",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=25 * 365),  # 25 years old
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household2.id,
                "individual": cls.adult2.id,
            }
        )

    def test_domain_to_id_sql_simple(self):
        """Test _domain_to_id_sql with simple domain."""
        domain = [("is_registrant", "=", True), ("is_group", "=", False)]
        sql = self.executor._domain_to_id_sql("res.partner", domain)
        self.assertIsNotNone(sql, "Should return SQL for simple domain")
        self.assertIsInstance(sql, SQL, "Should return SQL object")

    def test_domain_to_id_sql_empty_returns_none(self):
        """Test _domain_to_id_sql with empty domain."""
        sql = self.executor._domain_to_id_sql("res.partner", [])
        self.assertIsNone(sql, "Empty domain should return None")

    def test_exists_to_sql_basic(self):
        """Test _exists_to_sql generates valid SQL."""
        from ..models.cel_queryplan import ExistsThrough, LeafDomain

        # Create an ExistsThrough plan manually
        child_plan = LeafDomain(
            model="res.partner",
            domain=[("is_registrant", "=", True), ("is_group", "=", False)],
        )
        plan = ExistsThrough(
            through_model="spp.group.membership",
            parent_field="group",
            link_field="individual",
            child_model="res.partner",
            child_plan=child_plan,
            default_domain=[("is_ended", "=", False)],
        )

        sql = self.executor._exists_to_sql(plan)
        self.assertIsNotNone(sql, "Should return SQL for EXISTS plan")
        self.assertIsInstance(sql, SQL, "Should return SQL object")

    def test_count_to_sql_basic(self):
        """Test _count_to_sql generates valid SQL."""
        from ..models.cel_queryplan import CountThrough, LeafDomain

        child_plan = LeafDomain(
            model="res.partner",
            domain=[("is_registrant", "=", True)],
        )
        plan = CountThrough(
            through_model="spp.group.membership",
            parent_field="group",
            link_field="individual",
            child_model="res.partner",
            child_plan=child_plan,
            op=">=",
            rhs=2,
            default_domain=[("is_ended", "=", False)],
        )

        sql = self.executor._count_to_sql(plan)
        self.assertIsNotNone(sql, "Should return SQL for COUNT plan")
        self.assertIsInstance(sql, SQL, "Should return SQL object")

    def test_plan_to_sql_leaf_domain(self):
        """Test _plan_to_sql with LeafDomain."""
        from ..models.cel_queryplan import LeafDomain

        plan = LeafDomain(
            model="res.partner",
            domain=[("is_registrant", "=", True)],
        )
        sql = self.executor._plan_to_sql("res.partner", plan)
        self.assertIsNotNone(sql, "Should return SQL for LeafDomain")

    def test_plan_to_sql_and(self):
        """Test _plan_to_sql with AND of LeafDomains."""
        from ..models.cel_queryplan import AND, LeafDomain

        plan = AND(
            [
                LeafDomain(model="res.partner", domain=[("is_registrant", "=", True)]),
                LeafDomain(model="res.partner", domain=[("is_group", "=", False)]),
            ]
        )
        sql = self.executor._plan_to_sql("res.partner", plan)
        self.assertIsNotNone(sql, "Should return SQL for AND plan")

    def test_plan_to_sql_or(self):
        """Test _plan_to_sql with OR of LeafDomains."""
        from ..models.cel_queryplan import OR, LeafDomain

        plan = OR(
            [
                LeafDomain(model="res.partner", domain=[("is_group", "=", True)]),
                LeafDomain(model="res.partner", domain=[("is_group", "=", False)]),
            ]
        )
        sql = self.executor._plan_to_sql("res.partner", plan)
        self.assertIsNotNone(sql, "Should return SQL for OR plan")

    def test_sql_path_produces_same_results_as_python(self):
        """Test that SQL path produces same results as Python path for exists()."""
        # Use the full service to ensure we're testing the actual code path
        # Expression: households with at least one member under 5 years old
        expression = "members.exists(m, age_years(m.birthdate) < 5)"

        # Get result via service (which uses SQL path if available)
        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household1.id, self.household2.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        # household1 has a child under 5, household2 does not
        self.assertIn(
            self.household1.id,
            result["ids"],
            "Household1 should match (has child under 5)",
        )
        self.assertNotIn(
            self.household2.id,
            result["ids"],
            "Household2 should not match (no children under 5)",
        )

    def test_sql_path_for_count(self):
        """Test that SQL path works for count operations."""
        expression = "members.count(m, true) >= 2"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household1.id, self.household2.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        # household1 has 2 members, household2 has 1 member
        self.assertIn(self.household1.id, result["ids"], "Household1 should match (has 2 members)")
        self.assertNotIn(
            self.household2.id,
            result["ids"],
            "Household2 should not match (has only 1 member)",
        )

    def test_format_domain_for_log_truncates_large_lists(self):
        """Test that _format_domain_for_log truncates large ID lists."""
        large_ids = list(range(1, 10001))  # 10,000 IDs
        domain = [("id", "in", large_ids)]

        formatted = self.executor._format_domain_for_log(domain)

        # Should not contain all 10,000 IDs
        self.assertLess(len(formatted), 500, "Formatted domain should be truncated")
        self.assertIn("more", formatted, "Should indicate truncation")
        self.assertIn("9990", formatted, "Should show how many IDs were truncated")

    def test_format_domain_for_log_handles_sql_objects(self):
        """Test that _format_domain_for_log handles SQL objects."""
        sql = SQL("SELECT id FROM res_partner WHERE is_group = %s", True)
        domain = [("id", "in", sql)]

        formatted = self.executor._format_domain_for_log(domain)

        self.assertIn("SQL subquery", formatted, "Should show SQL subquery placeholder")

    def test_format_domain_for_log_small_list_unchanged(self):
        """Test that _format_domain_for_log preserves small lists."""
        small_ids = [1, 2, 3]
        domain = [("id", "in", small_ids)]

        formatted = self.executor._format_domain_for_log(domain)

        self.assertIn("[1, 2, 3]", formatted, "Small list should be preserved")
        self.assertNotIn("more", formatted, "Should not indicate truncation")


class TestSQLPythonParity(TransactionCase):
    """Every expression must produce identical results in both paths.

    These tests verify that the SQL generation path produces exactly the same
    results as the Python execution path, as required by spec section 8.2.

    Strategy:
    1. Execute expression normally (SQL path if available)
    2. Force Python path by mocking _plan_to_sql to return None
    3. Assert both produce identical ID sets and counts
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.executor = cls.env["spp.cel.executor"]
        cls.service = cls.env["spp.cel.service"]

        # Set up test data - multiple households with different member profiles

        # Household 1: 2 members (1 adult, 1 child under 5)
        cls.household1 = cls.env["res.partner"].create(
            {
                "name": "Parity Test HH1",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.adult1 = cls.env["res.partner"].create(
            {
                "name": "Parity Adult 1",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=30 * 365),  # 30 years old
            }
        )
        cls.child1 = cls.env["res.partner"].create(
            {
                "name": "Parity Child 1",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=3 * 365),  # 3 years old
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household1.id,
                "individual": cls.adult1.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household1.id,
                "individual": cls.child1.id,
            }
        )

        # Household 2: 1 member (adult only, no children)
        cls.household2 = cls.env["res.partner"].create(
            {
                "name": "Parity Test HH2",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.adult2 = cls.env["res.partner"].create(
            {
                "name": "Parity Adult 2",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=25 * 365),  # 25 years old
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household2.id,
                "individual": cls.adult2.id,
            }
        )

        # Household 3: 3 members (all adults)
        cls.household3 = cls.env["res.partner"].create(
            {
                "name": "Parity Test HH3",
                "is_registrant": True,
                "is_group": True,
            }
        )
        for i in range(3):
            adult = cls.env["res.partner"].create(
                {
                    "name": f"Parity Adult 3-{i}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=(20 + i) * 365),
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.household3.id,
                    "individual": adult.id,
                }
            )

        # Household 4: No members (empty household)
        cls.household4 = cls.env["res.partner"].create(
            {
                "name": "Parity Test HH4",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Household 5: Not a registrant (for filtering tests)
        cls.household5 = cls.env["res.partner"].create(
            {
                "name": "Parity Test HH5",
                "is_registrant": False,
                "is_group": True,
            }
        )

        # Base domain to limit search to our test households
        cls.test_base_domain = [
            ("is_group", "=", True),
            (
                "id",
                "in",
                [
                    cls.household1.id,
                    cls.household2.id,
                    cls.household3.id,
                    cls.household4.id,
                    cls.household5.id,
                ],
            ),
        ]

    def _assert_paths_equal(self, expression, test_description):
        """Helper to verify SQL and Python paths produce same results.

        Args:
            expression: CEL expression string to test
            test_description: Human-readable description for error messages
        """
        profile = "registry_groups"
        base_domain = self.test_base_domain.copy()

        # Get SQL path result (normal execution - tries SQL first)
        sql_result = self.service.compile_expression(
            expression,
            profile,
            base_domain=base_domain,
        )

        # Force Python path by mocking _plan_to_sql to return None
        # Note: Patch on class, not instance (Odoo models are read-only)
        with patch.object(type(self.executor), "_plan_to_sql", return_value=None):
            python_result = self.service.compile_expression(
                expression,
                profile,
                base_domain=base_domain,
            )

        # Both must be valid
        self.assertTrue(
            sql_result["valid"],
            f"{test_description}: SQL path should be valid. Error: {sql_result.get('error')}",
        )
        self.assertTrue(
            python_result["valid"],
            f"{test_description}: Python path should be valid. Error: {python_result.get('error')}",
        )

        # IDs must match exactly (order doesn't matter)
        sql_ids = sorted(sql_result["ids"])
        python_ids = sorted(python_result["ids"])

        self.assertEqual(
            sql_ids,
            python_ids,
            f"{test_description}: SQL and Python paths must return identical IDs.\n"
            f"SQL IDs: {sql_ids}\n"
            f"Python IDs: {python_ids}",
        )

        # Counts must match
        self.assertEqual(
            sql_result["count"],
            python_result["count"],
            f"{test_description}: SQL and Python paths must return identical counts",
        )

        # Count should match ID list length
        self.assertEqual(
            sql_result["count"],
            len(sql_result["ids"]),
            f"{test_description}: Count should match number of IDs in SQL result",
        )
        self.assertEqual(
            python_result["count"],
            len(python_result["ids"]),
            f"{test_description}: Count should match number of IDs in Python result",
        )

    def test_parity_simple_domain(self):
        """Test: is_registrant == true"""
        self._assert_paths_equal("is_registrant == true", "Simple domain filter")

    def test_parity_exists_basic(self):
        """Test: members.exists(m, true)"""
        self._assert_paths_equal("members.exists(m, true)", "Basic exists - households with any members")

    def test_parity_exists_with_filter(self):
        """Test: members.exists(m, age_years(m.birthdate) < 5)"""
        self._assert_paths_equal(
            "members.exists(m, age_years(m.birthdate) < 5)",
            "Exists with filter - households with children under 5",
        )

    def test_parity_count_equals(self):
        """Test: members.count(m, true) == 2"""
        self._assert_paths_equal(
            "members.count(m, true) == 2",
            "Count equals - households with exactly 2 members",
        )

    def test_parity_count_greater_than(self):
        """Test: members.count(m, true) >= 2"""
        self._assert_paths_equal(
            "members.count(m, true) >= 2",
            "Count greater than or equal - households with 2+ members",
        )

    def test_parity_count_less_than(self):
        """Test: members.count(m, true) < 3"""
        self._assert_paths_equal(
            "members.count(m, true) < 3",
            "Count less than - households with fewer than 3 members",
        )

    def test_parity_and_combination(self):
        """Test: members.exists(m, true) && is_registrant == true"""
        self._assert_paths_equal(
            "members.exists(m, true) && is_registrant == true",
            "AND combination - households that are registrants AND have members",
        )

    def test_parity_empty_results(self):
        """Test expression that matches no records"""
        # Expression that will match no households in our test data
        # (looking for households with more than 10 members)
        self._assert_paths_equal(
            "members.count(m, true) > 10",
            "Empty result set - no households with more than 10 members",
        )


class TestSQLEdgeCases(TransactionCase):
    """Edge case tests for SQL generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.executor = cls.env["spp.cel.executor"]
        cls.translator = cls.env["spp.cel.translator"]
        cls.service = cls.env["spp.cel.service"]

        # Set up test data with edge cases

        # Household with zero members
        cls.household_empty = cls.env["res.partner"].create(
            {
                "name": "Empty Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Household with exactly one member
        cls.household_one = cls.env["res.partner"].create(
            {
                "name": "Single Member Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_one = cls.env["res.partner"].create(
            {
                "name": "Only Member",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=20 * 365),  # 20 years old
                "income": 100.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_one.id,
                "individual": cls.member_one.id,
            }
        )

        # Household with member with NULL birthdate
        cls.household_null = cls.env["res.partner"].create(
            {
                "name": "Household with NULL birthdate",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_null_birthdate = cls.env["res.partner"].create(
            {
                "name": "Member with NULL birthdate",
                "is_registrant": True,
                "is_group": False,
                "birthdate": False,  # NULL birthdate
                "income": 200.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_null.id,
                "individual": cls.member_null_birthdate.id,
            }
        )

        # Household with member with income=0
        cls.household_zero_income = cls.env["res.partner"].create(
            {
                "name": "Household with zero income",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_zero_income = cls.env["res.partner"].create(
            {
                "name": "Member with zero income",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=30 * 365),  # 30 years old
                "income": 0.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_zero_income.id,
                "individual": cls.member_zero_income.id,
            }
        )

        # Household with exactly 2 members for threshold testing
        cls.household_two = cls.env["res.partner"].create(
            {
                "name": "Two Member Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_two_a = cls.env["res.partner"].create(
            {
                "name": "Member 2A",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=25 * 365),
                "income": 150.0,
            }
        )
        cls.member_two_b = cls.env["res.partner"].create(
            {
                "name": "Member 2B",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=22 * 365),
                "income": 120.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_two.id,
                "individual": cls.member_two_a.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_two.id,
                "individual": cls.member_two_b.id,
            }
        )

        # Household with 3 members for threshold testing
        cls.household_three = cls.env["res.partner"].create(
            {
                "name": "Three Member Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_three_a = cls.env["res.partner"].create(
            {
                "name": "Member 3A",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=28 * 365),
                "income": 100.0,
            }
        )
        cls.member_three_b = cls.env["res.partner"].create(
            {
                "name": "Member 3B",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=26 * 365),
                "income": 110.0,
            }
        )
        cls.member_three_c = cls.env["res.partner"].create(
            {
                "name": "Member 3C",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=24 * 365),
                "income": 90.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_three.id,
                "individual": cls.member_three_a.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_three.id,
                "individual": cls.member_three_b.id,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_three.id,
                "individual": cls.member_three_c.id,
            }
        )

    def test_zero_matching_records(self):
        """Test expression that matches no records returns empty results."""
        # Expression that should match nothing (age > 200 years)
        expression = "members.exists(m, age_years(m.birthdate) > 200)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertEqual(result["count"], 0, "Should match zero records")
        self.assertEqual(len(result["ids"]), 0, "Should return empty ID list")

    def test_exactly_one_match(self):
        """Test expression that matches exactly one record."""
        # Expression that matches only household_empty (has zero members)
        expression = "members.count(m, true) == 0"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household_empty.id, self.household_one.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertEqual(result["count"], 1, "Should match exactly one record")
        self.assertEqual(len(result["ids"]), 1, "Should return one ID")
        self.assertIn(self.household_empty.id, result["ids"], "Should match the empty household")

    def test_count_exactly_threshold(self):
        """Test count == threshold boundary condition."""
        # Expression: exactly 2 members
        expression = "members.count(m, true) == 2"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            (
                "id",
                "in",
                [self.household_one.id, self.household_two.id, self.household_three.id],
            ),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertEqual(result["count"], 1, "Should match exactly one household")
        self.assertIn(
            self.household_two.id,
            result["ids"],
            "Should match household with exactly 2 members",
        )
        self.assertNotIn(
            self.household_one.id,
            result["ids"],
            "Should not match household with 1 member",
        )
        self.assertNotIn(
            self.household_three.id,
            result["ids"],
            "Should not match household with 3 members",
        )

    def test_count_one_below_threshold(self):
        """Test count just below threshold."""
        # Expression: >= 2 members (household_one has 1, should not match)
        expression = "members.count(m, true) >= 2"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            (
                "id",
                "in",
                [self.household_one.id, self.household_two.id, self.household_three.id],
            ),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertNotIn(
            self.household_one.id,
            result["ids"],
            "Household with 1 member should not match >= 2",
        )
        self.assertIn(
            self.household_two.id,
            result["ids"],
            "Household with 2 members should match >= 2",
        )
        self.assertIn(
            self.household_three.id,
            result["ids"],
            "Household with 3 members should match >= 2",
        )

    def test_count_one_above_threshold(self):
        """Test count just above threshold."""
        # Expression: <= 2 members (household_three has 3, should not match)
        expression = "members.count(m, true) <= 2"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            (
                "id",
                "in",
                [self.household_one.id, self.household_two.id, self.household_three.id],
            ),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertIn(
            self.household_one.id,
            result["ids"],
            "Household with 1 member should match <= 2",
        )
        self.assertIn(
            self.household_two.id,
            result["ids"],
            "Household with 2 members should match <= 2",
        )
        self.assertNotIn(
            self.household_three.id,
            result["ids"],
            "Household with 3 members should not match <= 2",
        )

    def test_household_zero_members(self):
        """Test household with no members for count operations."""
        # Expression: count all members
        expression = "members.count(m, true) > 0"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household_empty.id, self.household_one.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertNotIn(
            self.household_empty.id,
            result["ids"],
            "Empty household should not match count > 0",
        )
        self.assertIn(
            self.household_one.id,
            result["ids"],
            "Household with 1 member should match count > 0",
        )

    def test_household_one_member(self):
        """Test household with exactly one member."""
        # Expression: exists any member
        expression = "members.exists(m, true)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household_empty.id, self.household_one.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertNotIn(
            self.household_empty.id,
            result["ids"],
            "Empty household should not match exists",
        )
        self.assertIn(
            self.household_one.id,
            result["ids"],
            "Household with one member should match exists",
        )

    def test_null_birthdate_age_filter(self):
        """Test member with NULL birthdate in age filter."""
        # Expression: filter by age - NULL birthdate should be excluded
        expression = "members.exists(m, age_years(m.birthdate) > 18)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [self.household_null.id, self.household_one.id]),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        # household_null has only a member with NULL birthdate - should not match
        self.assertNotIn(
            self.household_null.id,
            result["ids"],
            "Household with NULL birthdate member should not match age filter",
        )
        # household_one has member aged 20 - should match
        self.assertIn(
            self.household_one.id,
            result["ids"],
            "Household with member > 18 should match",
        )

    def test_empty_child_filter_results(self):
        """Test when child filter returns empty results."""
        # Expression: exists member with impossible condition
        expression = "members.exists(m, m.income > 999999)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
        ]
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        # No members have income > 999999, so no households should match
        self.assertEqual(
            result["count"],
            0,
            "Should match zero households when child filter is empty",
        )
        self.assertEqual(len(result["ids"]), 0, "Should return empty ID list")

    def test_preview_limited_to_n(self):
        """Test that compile_expression respects the limit parameter."""
        # Create multiple test households to ensure we have more than the limit
        extra_households = []
        for i in range(10):
            household = self.env["res.partner"].create(
                {
                    "name": f"Extra Household {i}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            member = self.env["res.partner"].create(
                {
                    "name": f"Extra Member {i}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=25 * 365),
                    "income": 100.0,
                }
            )
            self.env["spp.group.membership"].create(
                {
                    "group": household.id,
                    "individual": member.id,
                }
            )
            extra_households.append(household.id)

        # Expression: all households with at least one member
        expression = "members.exists(m, true)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", extra_households),
        ]

        # Test with limit=5
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
            limit=5,
        )

        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertEqual(result["count"], 10, "Count should be 10 (total matching)")
        self.assertLessEqual(len(result["ids"]), 5, "Preview should be limited to 5 IDs")

    def test_count_without_loading_ids(self):
        """Test compile_expression with limit=0 returns count only."""
        # Expression: all households with members
        expression = "members.exists(m, true)"

        base_domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
        ]

        # Use compile_expression with limit=0 which should be efficient
        result = self.service.compile_expression(
            expression,
            "registry_groups",
            base_domain=base_domain,
            limit=0,
        )

        # Result should have count
        self.assertTrue(result["valid"], f"Expression should be valid: {result.get('error')}")
        self.assertIn("count", result, "Result should have count")
        self.assertIsInstance(result["count"], int, "Count should be an integer")
        self.assertGreater(result["count"], 0, "Should count some households")
