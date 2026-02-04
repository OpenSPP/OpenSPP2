# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Robustness tests for CEL SQL generation.

Tests cover:
- SQL injection prevention
- OR combinations and complex nesting
- Error handling and graceful degradation
- Boundary values and large numbers
- Unicode and special characters
"""

from datetime import date, timedelta

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSQLInjectionPrevention(TransactionCase):
    """Security tests to verify SQL injection is prevented.

    All values should be properly parameterized/escaped.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]
        cls.executor = cls.env["spp.cel.executor"]

        # Create test household with special characters in name
        cls.household = cls.env["res.partner"].create(
            {
                "name": "Test'; DROP TABLE--",  # SQL injection attempt in name
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member = cls.env["res.partner"].create(
            {
                "name": 'Member" OR "1"="1',  # Another injection pattern
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=30 * 365),
                "income": 1000.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member.id,
            }
        )

    def test_special_chars_in_existing_data_safe(self):
        """Verify expressions work safely with SQL-injection-like data."""
        # This should work normally despite injection attempts in data
        result = self.service.compile_expression(
            "members.exists(m, true)",
            "registry_groups",
            base_domain=[("id", "=", self.household.id)],
        )

        self.assertTrue(
            result["valid"],
            f"Should handle special chars safely: {result.get('error')}",
        )
        self.assertIn(self.household.id, result["ids"])

    def test_aggregation_with_special_char_data(self):
        """Verify aggregations work with injection-like data in records."""
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 500",
            "registry_groups",
            base_domain=[("id", "=", self.household.id)],
        )

        self.assertTrue(result["valid"], f"Aggregation should work safely: {result.get('error')}")
        self.assertIn(self.household.id, result["ids"])

    def test_count_with_special_char_data(self):
        """Verify count works with injection-like data."""
        result = self.service.compile_expression(
            "members.count(m, true) >= 1",
            "registry_groups",
            base_domain=[("id", "=", self.household.id)],
        )

        self.assertTrue(result["valid"], f"Count should work safely: {result.get('error')}")
        self.assertIn(self.household.id, result["ids"])


@tagged("post_install", "-at_install")
class TestORCombinations(TransactionCase):
    """Test OR combinations with SQL generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        # Household A: 3 members, high income
        cls.household_a = cls.env["res.partner"].create(
            {
                "name": "OR Test HH-A",
                "is_registrant": True,
                "is_group": True,
            }
        )
        for i in range(3):
            member = cls.env["res.partner"].create(
                {
                    "name": f"Member A-{i}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=30 * 365),
                    "income": 5000.0,  # High income
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.household_a.id,
                    "individual": member.id,
                }
            )

        # Household B: 1 member, low income
        cls.household_b = cls.env["res.partner"].create(
            {
                "name": "OR Test HH-B",
                "is_registrant": True,
                "is_group": True,
            }
        )
        member_b = cls.env["res.partner"].create(
            {
                "name": "Member B",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=25 * 365),
                "income": 100.0,  # Low income
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_b.id,
                "individual": member_b.id,
            }
        )

        # Household C: 2 members, medium income
        cls.household_c = cls.env["res.partner"].create(
            {
                "name": "OR Test HH-C",
                "is_registrant": True,
                "is_group": True,
            }
        )
        for i in range(2):
            member = cls.env["res.partner"].create(
                {
                    "name": f"Member C-{i}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=35 * 365),
                    "income": 2000.0,  # Medium income
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.household_c.id,
                    "individual": member.id,
                }
            )

        cls.test_base = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [cls.household_a.id, cls.household_b.id, cls.household_c.id]),
        ]

    def test_or_with_count_conditions(self):
        """Test OR of two count conditions."""
        # Match households with >= 3 members OR <= 1 member
        result = self.service.compile_expression(
            "members.count(m, true) >= 3 || members.count(m, true) == 1",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"OR expression should be valid: {result.get('error')}")
        # HH-A has 3 members, HH-B has 1 member
        self.assertIn(self.household_a.id, result["ids"], "Should match HH-A (3 members)")
        self.assertIn(self.household_b.id, result["ids"], "Should match HH-B (1 member)")
        self.assertNotIn(self.household_c.id, result["ids"], "Should not match HH-C (2 members)")

    def test_or_with_aggregation_conditions(self):
        """Test OR of two aggregation conditions."""
        # Match households with high total income OR low member count
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 10000 || members.count(m, true) == 1",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"OR expression should be valid: {result.get('error')}")
        # HH-A: sum=15000 >= 10000, HH-B: count=1
        self.assertIn(self.household_a.id, result["ids"], "Should match HH-A (sum >= 10000)")
        self.assertIn(self.household_b.id, result["ids"], "Should match HH-B (count == 1)")

    def test_complex_and_or_combination(self):
        """Test nested AND/OR: (A && B) || C."""
        # (has >= 2 members AND sum >= 4000) OR has 1 member
        result = self.service.compile_expression(
            "(members.count(m, true) >= 2 && members.sum(m, m.income, true) >= 4000) || members.count(m, true) == 1",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(
            result["valid"],
            f"Complex expression should be valid: {result.get('error')}",
        )
        # HH-A: count=3 >= 2, sum=15000 >= 4000 -> matches first part
        # HH-B: count=1 -> matches second part
        # HH-C: count=2 >= 2, sum=4000 >= 4000 -> matches first part
        self.assertIn(self.household_a.id, result["ids"])
        self.assertIn(self.household_b.id, result["ids"])
        self.assertIn(self.household_c.id, result["ids"])

    def test_or_with_contradictory_conditions(self):
        """Test OR where conditions are mutually exclusive."""
        # This should match all: either high income OR not high income
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 10000 || members.sum(m, m.income, true) < 10000",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Contradictory OR should be valid: {result.get('error')}")
        self.assertEqual(result["count"], 3, "All households should match (tautology)")


@tagged("post_install", "-at_install")
class TestErrorHandling(TransactionCase):
    """Test error handling and graceful degradation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

    def test_invalid_expression_syntax(self):
        """Test that syntax errors are caught gracefully."""
        result = self.service.compile_expression(
            "members.exists(m, &&)",  # Invalid syntax (operator without operand)
            "registry_groups",
        )

        self.assertFalse(result["valid"], "Should be invalid")
        self.assertIsNotNone(result["error"], "Should have error message")

    def test_unknown_symbol(self):
        """Test that unknown symbols are caught."""
        result = self.service.compile_expression(
            "unknown_symbol.exists(m, true)",  # Unknown symbol
            "registry_groups",
        )

        self.assertFalse(result["valid"], "Should be invalid")
        self.assertIn("symbol", result["error"].lower(), "Error should mention symbol")

    def test_invalid_profile(self):
        """Test that invalid profile is handled."""
        result = self.service.compile_expression(
            "members.exists(m, true)",
            "nonexistent_profile",  # Invalid profile
        )

        self.assertFalse(result["valid"], "Should be invalid")
        self.assertIsNotNone(result["error"])

    def test_empty_expression(self):
        """Test that empty expression is handled."""
        result = self.service.compile_expression(
            "",  # Empty
            "registry_groups",
        )

        self.assertFalse(result["valid"], "Should be invalid")
        self.assertIn("empty", result["error"].lower())

    def test_whitespace_only_expression(self):
        """Test that whitespace-only expression is handled."""
        result = self.service.compile_expression(
            "   \n\t  ",  # Whitespace only
            "registry_groups",
        )

        self.assertFalse(result["valid"], "Should be invalid")


@tagged("post_install", "-at_install")
class TestBoundaryValues(TransactionCase):
    """Test boundary values and edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        # Household with large income values
        cls.household_large = cls.env["res.partner"].create(
            {
                "name": "Large Value HH",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_large = cls.env["res.partner"].create(
            {
                "name": "Rich Member",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=40 * 365),
                "income": 999999999.99,  # Near max float
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_large.id,
                "individual": cls.member_large.id,
            }
        )

        # Household with zero values
        cls.household_zero = cls.env["res.partner"].create(
            {
                "name": "Zero Value HH",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_zero = cls.env["res.partner"].create(
            {
                "name": "Zero Income Member",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=25 * 365),
                "income": 0.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_zero.id,
                "individual": cls.member_zero.id,
            }
        )

        cls.test_base = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [cls.household_large.id, cls.household_zero.id]),
        ]

    def test_very_large_number_comparison(self):
        """Test comparison with very large numbers."""
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 999999999",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should handle large numbers: {result.get('error')}")
        self.assertIn(self.household_large.id, result["ids"])
        self.assertNotIn(self.household_zero.id, result["ids"])

    def test_zero_boundary_sum(self):
        """Test sum comparison at zero boundary."""
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) == 0",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should handle zero: {result.get('error')}")
        self.assertIn(self.household_zero.id, result["ids"])
        self.assertNotIn(self.household_large.id, result["ids"])

    def test_decimal_precision(self):
        """Test decimal precision in comparisons."""
        # Create member with precise decimal
        household = self.env["res.partner"].create(
            {
                "name": "Decimal Test HH",
                "is_registrant": True,
                "is_group": True,
            }
        )
        member = self.env["res.partner"].create(
            {
                "name": "Decimal Member",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=30 * 365),
                "income": 1000.50,
            }
        )
        self.env["spp.group.membership"].create(
            {
                "group": household.id,
                "individual": member.id,
            }
        )

        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 1000.50",
            "registry_groups",
            base_domain=[("id", "=", household.id)],
        )

        self.assertTrue(result["valid"], f"Should handle decimals: {result.get('error')}")
        self.assertIn(household.id, result["ids"])


@tagged("post_install", "-at_install")
class TestUnicodeHandling(TransactionCase):
    """Test Unicode and special character handling."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        # Household with unicode name
        cls.household_unicode = cls.env["res.partner"].create(
            {
                "name": "日本語テスト世帯",  # Japanese
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_arabic = cls.env["res.partner"].create(
            {
                "name": "عضو عربي",  # Arabic (RTL)
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=35 * 365),
                "income": 2500.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_unicode.id,
                "individual": cls.member_arabic.id,
            }
        )

        # Household with emoji
        cls.household_emoji = cls.env["res.partner"].create(
            {
                "name": "Family Home 🏠👨‍👩‍👧",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.member_emoji = cls.env["res.partner"].create(
            {
                "name": "Happy Member 😊",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - timedelta(days=28 * 365),
                "income": 3000.0,
            }
        )
        cls.env["spp.group.membership"].create(
            {
                "group": cls.household_emoji.id,
                "individual": cls.member_emoji.id,
            }
        )

        cls.test_base = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("id", "in", [cls.household_unicode.id, cls.household_emoji.id]),
        ]

    def test_unicode_data_exists(self):
        """Test exists with unicode data."""
        result = self.service.compile_expression(
            "members.exists(m, true)",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should handle unicode: {result.get('error')}")
        self.assertIn(self.household_unicode.id, result["ids"])
        self.assertIn(self.household_emoji.id, result["ids"])

    def test_unicode_data_aggregation(self):
        """Test aggregation with unicode data."""
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 2000",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(
            result["valid"],
            f"Should handle unicode in aggregation: {result.get('error')}",
        )
        self.assertIn(self.household_unicode.id, result["ids"])
        self.assertIn(self.household_emoji.id, result["ids"])

    def test_unicode_data_count(self):
        """Test count with unicode data."""
        result = self.service.compile_expression(
            "members.count(m, true) >= 1",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should handle unicode in count: {result.get('error')}")
        self.assertEqual(result["count"], 2)


@tagged("post_install", "-at_install")
class TestMultipleAggregations(TransactionCase):
    """Test multiple aggregations in same expression."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["spp.cel.service"]

        # Household with varied income members
        cls.household = cls.env["res.partner"].create(
            {
                "name": "Multi-Agg Test HH",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # Create members with varied incomes: 1000, 2000, 3000
        for income in [1000.0, 2000.0, 3000.0]:
            member = cls.env["res.partner"].create(
                {
                    "name": f"Member Income {income}",
                    "is_registrant": True,
                    "is_group": False,
                    "birthdate": date.today() - timedelta(days=30 * 365),
                    "income": income,
                }
            )
            cls.env["spp.group.membership"].create(
                {
                    "group": cls.household.id,
                    "individual": member.id,
                }
            )

        cls.test_base = [("id", "=", cls.household.id)]

    def test_sum_and_count(self):
        """Test SUM AND COUNT together."""
        # sum=6000, count=3
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 6000 && members.count(m, true) >= 3",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should combine sum and count: {result.get('error')}")
        self.assertIn(self.household.id, result["ids"])

    def test_min_and_max(self):
        """Test MIN AND MAX together."""
        # min=1000, max=3000
        result = self.service.compile_expression(
            "members.min(m, m.income, true) >= 1000 && members.max(m, m.income, true) <= 3000",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should combine min and max: {result.get('error')}")
        self.assertIn(self.household.id, result["ids"])

    def test_avg_and_count_and_sum(self):
        """Test AVG AND COUNT AND SUM together."""
        # avg=2000, count=3, sum=6000
        result = self.service.compile_expression(
            (
                "members.avg(m, m.income, true) >= 2000 && "
                "members.count(m, true) == 3 && "
                "members.sum(m, m.income, true) == 6000"
            ),
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(result["valid"], f"Should combine 3 aggregations: {result.get('error')}")
        self.assertIn(self.household.id, result["ids"])

    def test_contradictory_aggregations(self):
        """Test impossible combination - should return empty."""
        # Cannot have sum >= 10000 AND sum < 5000
        result = self.service.compile_expression(
            "members.sum(m, m.income, true) >= 10000 && members.sum(m, m.income, true) < 5000",
            "registry_groups",
            base_domain=self.test_base,
        )

        self.assertTrue(
            result["valid"],
            f"Should be valid even if impossible: {result.get('error')}",
        )
        self.assertEqual(result["count"], 0, "Impossible condition should match nothing")
